/**
 * llm.js —— Qwen（阿里云百炼）模型适配层
 * ------------------------------------------------------------------
 * 两种运行模式：
 *  1) 离线演示模式：无 API Key，全部推理由内置证据库 + 本地统计引擎驱动；
 *  2) 真实模型模式：填入百炼 API Key 后，各智能体的自然语言生成交由 Qwen 完成，
 *     证据检索、溯源比对与统计检验仍在本地执行（保证可核查、可复现）。
 *
 * 浏览器直连若被 CORS 拦截，可运行 `node server.js`，把接口地址改为 /api，
 * 由本地代理转发，API Key 不出本机。
 */
const LLM = {
  cfg: {
    key: localStorage.getItem('ais_key') || '',
    model: localStorage.getItem('ais_model') || 'qwen-plus',
    base: localStorage.getItem('ais_base') || 'https://dashscope.aliyuncs.com/compatible-mode/v1'
  },
  get enabled(){ return !!this.cfg.key || this.cfg.base.startsWith('/api'); },

  save(key, model, base){
    this.cfg = { key, model, base };
    localStorage.setItem('ais_key', key);
    localStorage.setItem('ais_model', model);
    localStorage.setItem('ais_base', base);
  },
  clear(){
    this.cfg = { key:'', model:'qwen-plus', base:'https://dashscope.aliyuncs.com/compatible-mode/v1' };
    localStorage.removeItem('ais_key');
    localStorage.removeItem('ais_model');
    localStorage.removeItem('ais_base');
  },

  /** 全局约束 Prompt（赛题要求的"配套约束"低成本修正手段） */
  systemPrompt(role){
    return [
      '你是国产开源大模型 Qwen 驱动的 AI Scientist 系统中的一个专职智能体。',
      `当前角色：${role}。`,
      '必须遵守以下硬约束：',
      '1. 严禁虚构文献、作者、期刊、DOI 或数据。只能引用用户消息中显式提供的文献条目，引用时使用其编号（如 R12）。',
      '2. 严格区分"相关性"与"因果性"，未经因果识别设计不得使用"导致""决定""证明"等因果表述。',
      '3. 所有结论必须限定适用场景（人群/时间窗/数据来源/模型规模等），禁止"必然""一定""所有""彻底"等绝对化表述。',
      '4. 区分"已验证事实""存在争议""研究空白"三类陈述，并在文中显式标注。',
      '5. 若证据不足以支撑某判断，必须明说"当前证据不足"，不得用流畅表述掩盖不确定性。',
      '6. 使用简体中文，表达紧凑，不使用客套开场白。'
    ].join('\n');
  },

  /** 调用 Qwen chat completion */
  async chat(role, userContent, {temperature=0.7, maxTokens=1600} = {}){
    const base = this.cfg.base.replace(/\/$/,'');
    const url = base.startsWith('/api') ? `${base}/chat` : `${base}/chat/completions`;
    const headers = { 'Content-Type':'application/json' };
    if(this.cfg.key) headers['Authorization'] = `Bearer ${this.cfg.key}`;

    const res = await fetch(url, {
      method:'POST',
      headers,
      body: JSON.stringify({
        model: this.cfg.model,
        messages: [
          { role:'system', content: this.systemPrompt(role) },
          { role:'user', content: userContent }
        ],
        temperature,
        max_tokens: maxTokens
      })
    });
    if(!res.ok){
      const txt = await res.text().catch(()=> '');
      throw new Error(`HTTP ${res.status} ${txt.slice(0,300)}`);
    }
    const data = await res.json();
    return data?.choices?.[0]?.message?.content?.trim() || '';
  },

  /** 连通性测试 */
  async test(){
    const t0 = performance.now();
    const out = await this.chat('连通性测试助手', '请只回复两个字：正常。', {temperature:0, maxTokens:16});
    return { ms: Math.round(performance.now()-t0), out };
  },

  /** 把证据库打包成给模型的上下文（防止模型自由发挥引用） */
  buildEvidenceContext(topic){
    const ids = new Set();
    [...topic.consensus, ...topic.disputes, ...topic.gaps,
     ...topic.debate.pro, ...topic.debate.con].forEach(e => (e.refs||[]).forEach(r=>ids.add(r)));
    (topic.hypothesis.refs||[]).forEach(r=>ids.add(r));
    const lines = [...ids].map(id => {
      const r = REFS[id];
      return `[${id}] ${r.a} 《${r.t}》 ${r.v}, ${r.y}。要点：${r.d}`;
    });
    return `【可引用文献清单（只能引用这些，不得新增）】\n${lines.join('\n')}`;
  }
};
