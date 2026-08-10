/**
 * app.js —— 交互与页面装配
 */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

/* ---------------- 架构节点说明 ---------------- */
const NODE_INFO = {
  in1:{n:'领域问题描述',a:'输入',d:'用户以自然语言给出的开放式科学议题。系统不要求问题已被良构化——把模糊问题转成可研究问题正是 S1 的职责。',io:['输入：自由文本','输出：原始问题串']},
  in2:{n:'文献 / 论文 PDF',a:'输入',d:'领域文献集合。经切片、嵌入后进入向量库，并保留 page/offset 偏移量，使后续每一条断言都能回溯到具体段落。',io:['输入：PDF / 结构化摘要','输出：带偏移量的文献切片']},
  in3:{n:'多模态实测数据',a:'输入',d:'观测、实验、临床或行为/交易数据。与文献通道并行进入 S3，是"假设可验证"的物质基础——没有数据通道的系统只能产出无法检验的想法。',io:['输入：表格 / 时序 / 影像','输出：标准化特征矩阵']},
  in4:{n:'规则 / 法规约束',a:'输入',d:'人文社科方向的法规、监管政策文本，或自然科学方向的标准与伦理约束。被编译成 S5 生成阶段的硬性禁止项。',io:['输入：法条 / 标准文本','输出：约束规则集']},

  S1:{n:'问题理解 Agent',a:'ProblemParser',d:'把开放议题拆解为：核心变量、边界条件、当前不确定性来源。同时加载领域约束 Prompt（禁绝对化、区分相关与因果、强制场景限定），这些约束会一路传递到后续所有智能体。',io:['输入：原始问题 + 约束模板','输出：结构化问题陈述 + 变量清单']},
  S2:{n:'文献挖掘与事实提取',a:'LiteratureMiner',d:'向量检索 + 事实抽取。关键设计是"无来源即丢弃"——任何不能绑定到具体文献编号的陈述在本阶段就被过滤掉，从源头压制幻觉，这也是防断章取义的第一道防线。',io:['输入：问题变量 + 向量库','输出：带来源编号的事实条目']},
  S3:{n:'知识整合与图谱构建',a:'KnowledgeSynthesizer',d:'把事实条目分为"已验证共识 / 存在争议 / 研究空白"三层。遇到文献间冲突时不做取舍，而是标注为争议——这一点很重要，取其一会让系统产生虚假的确定感。',io:['输入：事实条目','输出：三层证据图谱 + 冲突标注']},
  S4:{n:'跨域关联发现',a:'LinkDiscoverer',d:'在非本领域文献中寻找结构同构的解决范式，做技术迁移。这是假设"新颖性"的主要来源——同领域内的组合往往已被穷举，真正的创新常来自跨学科的结构映射。',io:['输入：证据图谱 + 跨域语料','输出：迁移路径 + 迁移论证']},
  S5:{n:'假设生成',a:'HypothesisGenerator',d:'归纳（从共识抽取规律）+ 演绎（推出可检验的新预测）。生成时强制绑定引用编号，并接收来自三重闸门的修订指令做迭代重写。',io:['输入：图谱 + 迁移线索 + 修订指令','输出：假设 + 引用绑定']},
  S6:{n:'双辩论智能体对抗',a:'Proponent / Opponent / Judge',d:'正方与反方分别举证，裁判统计反方有效论据数量。达到阈值即判定假设片面，自动收窄结论范围并回传重写。被消解的反方意见不会消失，而是转化为最终成果里的"适用范围声明"。',io:['输入：候选假设 + 证据库','输出：裁决 + 范围收窄指令']},
  S7:{n:'原文溯源校验',a:'GroundingVerifier',d:'程序自动检索向量库中对应内容，逐段比对假设表述与原文是否冲突。冲突则标记漏洞回传思辨 Agent 重写——注意是重写而非删除，删除会丢失信息。',io:['输入：断言 + 引用编号','输出：重合度评分 + 漏洞标记']},
  S8:{n:'因果量化检验',a:'CausalValidator',d:'解决循环论证与无依据猜想。提取数据集指标，自动执行相关性与分组显著性检验；数据不支持则直接判定假设无效，引导更换研究变量重新生成。显著但效应量小的情形会被降级为"弱关联"。',io:['输入：假设变量 + 数据集','输出：统计量 + 通过/降级/否决']},
  S9:{n:'人在回路复核',a:'HumanInTheLoop',d:'研究者在此注入领域约束（如"排除动物实验外推"），系统把约束写回 S5 的生成提示并重跑闭环。人机协作辩论的显式入口。',io:['输入：闸门状态 + 待确认清单','输出：人工约束 / 放行']},
  S10:{n:'研究计划输出',a:'PlanReporter',d:'汇编赛题要求的 10 个标准化字段，并把 S8 的实测统计结果写入"实验结果"字段，使产出的是可执行研究计划而非空想。',io:['输入：通过闸门的假设 + 统计结果','输出：10 字段结构化文档']},
  S11:{n:'评分自检',a:'RubricSelfChecker',d:'对照赛题评分标准逐项自评，定位薄弱环节。同时输出运行留痕（种子、轮次、模式），保证可复现性。',io:['输入：完整运行记录','输出：自评分 + 复现清单']},

  B1:{n:'Qwen 基座模型',a:'百炼平台',d:'全部自然语言生成由 Qwen 系列开源模型承担，通过阿里云百炼平台 API 调用。系统设计为"模型只负责生成，校验全部在本地"，因此模型换代不影响可核查性。',io:['接口：OpenAI 兼容模式','模型：qwen-plus / max / turbo']},
  B2:{n:'文献向量库',a:'Vector Store',d:'文献切片 + 嵌入 + 偏移量索引。S2 检索、S7 溯源比对共用同一份索引，保证"检索到的"和"被核对的"是同一段文字。',io:['存储：切片 + 向量 + 偏移','服务：检索 / 回查']},
  B3:{n:'约束 Prompt 层',a:'Guardrail',d:'低成本基础修正手段：禁止脱离依据主观推断、区分相关性与因果性、结论必须限定适用场景、禁止绝对化表述。作为 system prompt 注入每一个智能体。',io:['输入：领域规则','输出：注入式约束']},
  B4:{n:'统计检验工具箱',a:'Stats Engine',d:'浏览器内实现的 Pearson 相关、Welch t 检验、Cohen\'s d 与不完全贝塔函数 p 值计算。统计量都是对数据真实计算的，不是预写死的数字。',io:['输入：数据矩阵','输出：统计量 + 判定']},
  B5:{n:'运行留痕与复现',a:'Provenance',d:'记录随机种子、迭代轮次、模型配置与全链路日志，支持 Markdown / JSON 一键导出。相同配置下结果可完整复现，对应评分标准中的可复现性维度。',io:['输入：全链路事件','输出：留痕文档 / 导出包']}
};

const MODULES = [
  {n:'双辩论智能体对抗',b:'S6',s:['正方 Agent 与反方 Agent 分别检索证据库并举证，提示词互相不可见，避免观点趋同','裁判 Agent 统计反方有效论据数量，达到阈值即判定假设片面','触发片面判定后自动生成"范围收窄指令"，回传 S5 重写而非直接丢弃','第 2 轮中被范围限定消解的反方意见，转写为成果中的适用边界声明']},
  {n:'原文溯源校验',b:'S7',s:['假设生成时强制绑定引用编号，未绑定的断言不进入校验队列','程序自动检索向量库对应切片，逐条计算断言与原文的重合度','低于阈值判定为"支持不足"或"与原文冲突"，标记漏洞回传','重写策略是把断言改写为与原文一致的限定表述，而不是删除断言']},
  {n:'因果量化检验',b:'S8',s:['从数据集提取自变量、因变量与分组因子三类指标','自动执行 Pearson 相关检验与 Welch 分组 t 检验，计算效应量','数据不支持关联则直接判定假设无效，引导更换研究变量','显著但 |r| < 0.3 时结论强制降级为"弱关联"，禁止因果表述']},
  {n:'约束 Prompt 层',b:'B3',s:['禁止脱离依据的主观推断，无证据时必须明说"当前证据不足"','严格区分相关性与因果性，未做因果识别不得使用因果动词','结论必须限定适用场景（人群 / 时间窗 / 数据来源 / 模型规模）','禁止"必然""一定""所有""彻底"等绝对化表述']},
  {n:'前端展示与留痕',b:'B5',s:['流水线 11 阶段实时动画 + 逐阶段日志，可点击回看任意阶段','研究计划 10 字段结构化呈现，支持 Markdown / JSON / PDF 导出','记录随机种子与配置，相同参数下结果可完整复现','评分自检面板对照赛题评分标准，定位薄弱维度']}
];

/* ---------------- 初始化 ---------------- */
let currentRun = null;
let selectedStage = null;

function initTabs(){
  $$('.tab').forEach(t=>t.addEventListener('click',()=>{
    $$('.tab').forEach(x=>x.classList.remove('active'));
    $$('.panel-tab').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    $('#tab-'+t.dataset.tab).classList.add('active');
  }));
}
function goTab(name){
  $$('.tab').forEach(x=>x.classList.toggle('active', x.dataset.tab===name));
  $$('.panel-tab').forEach(x=>x.classList.toggle('active', x.id==='tab-'+name));
}

function initArch(){
  $$('[data-node]').forEach(n=>n.addEventListener('click',()=>{
    $$('[data-node]').forEach(x=>x.classList.remove('sel'));
    n.classList.add('sel');
    const info = NODE_INFO[n.dataset.node];
    if(!info) return;
    $('#nodeTitle').textContent = info.n;
    $('#nodeDesc').innerHTML = `
      <div class="tagline"><span class="tag">${esc(info.a)}</span></div>
      <p>${esc(info.d)}</p>
      <h4>接口</h4>
      ${info.io.map(x=>`<div class="kv"><b></b><span>${esc(x)}</span></div>`).join('')}`;
  }));
  $('#modGrid').innerHTML = MODULES.map(m=>`
    <div class="mod-card">
      <h4><span class="mod-badge">${m.b}</span>${esc(m.n)}</h4>
      <ol>${m.s.map(x=>`<li>${esc(x)}</li>`).join('')}</ol>
    </div>`).join('');
}

/* ---------------- 问答 ---------------- */
function matchTopic(q){
  let best = null, bestScore = 0;
  KB.forEach(t=>{
    let s = 0;
    t.keywords.forEach(k=>{ if(q.toLowerCase().includes(k.toLowerCase())) s += k.length >= 4 ? 3 : 2; });
    if(q.includes(String(t.id))) s += 6;
    const j = jaccard(q, t.title);
    s += j * 12;
    if(s > bestScore){ bestScore = s; best = t; }
  });
  return bestScore >= 2.2 ? {topic:best, score:bestScore} : null;
}

function offlineAnswer(topic){
  const li = arr => arr.map(x=>`<li>${esc(x.t)}${refChips(x.refs)}</li>`).join('');
  const usedRefs = new Set();
  [...topic.consensus,...topic.disputes,...topic.gaps].forEach(e=>(e.refs||[]).forEach(r=>usedRefs.add(r)));
  return `
    <div class="tagline"><span class="tag">${topic.code}</span>
      <span class="tag tag-ok">共识 ${topic.consensus.length}</span>
      <span class="tag tag-warn">争议 ${topic.disputes.length}</span>
      <span class="tag tag-gap">空白 ${topic.gaps.length}</span></div>
    <p>${esc(topic.summary)}</p>
    <h4><span class="tag tag-ok">已验证</span>目前站得住的结论</h4><ul>${li(topic.consensus)}</ul>
    <h4><span class="tag tag-warn">有争议</span>尚无定论的部分</h4><ul>${li(topic.disputes)}</ul>
    <h4><span class="tag tag-gap">研究空白</span>还没人解决的问题</h4><ul>${li(topic.gaps)}</ul>
    <h4>核心技术瓶颈</h4>
    ${topic.barriers.map(b=>`<div class="kv"><b>${esc(b.name)}</b><span>${esc(b.t)}</span></div>`).join('')}
    <h4>可能的突破口（跨域迁移）</h4>
    <p>${esc(topic.crossLink.insight)}</p>
    <div class="reflist"><b>本回答引用的文献</b>
      ${[...usedRefs].map(r=>`<div>[${r}] ${esc(refText(r))}</div>`).join('')}</div>
    <div class="chat-actions">
      <button class="btn btn-primary" onclick="runFromChat(${topic.id})">▶ 生成可验证科学假设</button>
      <button class="btn btn-ghost" onclick="askFaq(${topic.id},0)">${esc(topic.faq[0].q)}</button>
      ${topic.faq[1]?`<button class="btn btn-ghost" onclick="askFaq(${topic.id},1)">${esc(topic.faq[1].q)}</button>`:''}
    </div>`;
}

function pushMsg(who, html){
  const d = document.createElement('div');
  d.className = 'msg ' + (who==='user'?'msg-user':'msg-ai');
  d.innerHTML = `<div class="avatar">${who==='user'?'我':'AI'}</div><div class="bubble">${html}</div>`;
  $('#chatScroll').appendChild(d);
  $('#chatScroll').scrollTop = $('#chatScroll').scrollHeight;
  return d;
}

async function handleAsk(q){
  if(!q.trim()) return;
  pushMsg('user', `<p>${esc(q)}</p>`);
  const holder = pushMsg('ai', `<span class="typing"><i></i><i></i><i></i></span> <span class="muted small">${LLM.enabled?'Qwen 推理中':'检索证据库'}…</span>`);
  const m = matchTopic(q);

  await new Promise(r=>setTimeout(r, 320));

  if(!m){
    if(LLM.enabled){
      try{
        const out = await LLM.chat('人工智能议题问答智能体',
          `【任务】回答下面这个人工智能相关问题。你没有可引用的文献清单，因此不得给出任何具体文献引用，并须在开头说明"以下为一般性说明，未经文献溯源"。\n问题：${q}`);
        holder.querySelector('.bubble').innerHTML = mdToHtml(out) +
          `<div class="reflist muted">本回答未经证据库溯源。若想获得带文献引用与可验证假设的完整分析，请选择左侧 118–125 号议题。</div>`;
      }catch(e){
        holder.querySelector('.bubble').innerHTML = `<p class="muted">调用 Qwen 失败：${esc(e.message)}</p><p class="muted small">可在「模型配置」中检查 API Key，或改用离线演示模式（内置 8 个议题）。</p>`;
      }
    }else{
      holder.querySelector('.bubble').innerHTML = `
        <p>这个问题没有命中内置证据库。当前处于<b>离线演示模式</b>，为保证"不虚构、可溯源"，我不会凭空作答。</p>
        <p class="muted">两个选择：① 从左侧选择 118–125 号议题，我会给出带文献引用的完整分析；② 在「模型配置」中填入百炼 API Key，切换为 Qwen 真实调用模式后可回答开放问题。</p>
        <div class="chat-actions">${KB.slice(0,4).map(t=>
          `<button class="btn btn-ghost" onclick="askTopic(${t.id})">${esc(t.short)}</button>`).join('')}</div>`;
    }
    return;
  }

  const t = m.topic;
  if(LLM.enabled){
    try{
      const out = await LLM.chat('人工智能议题问答智能体',
        `${LLM.buildEvidenceContext(t)}\n\n【任务】基于上述文献清单回答用户问题。要求：\n1. 明确区分"已验证共识""存在争议""研究空白"三类陈述并标注；\n2. 每个关键判断后用 [R编号] 标注来源，只能用清单内编号；\n3. 指出核心技术瓶颈；\n4. 400 字以内，不要客套话。\n\n用户问题：${q}\n议题背景：${t.summary}`);
      holder.querySelector('.bubble').innerHTML =
        `<div class="tagline"><span class="tag">${t.code}</span><span class="tag">Qwen ${esc(LLM.cfg.model)}</span></div>`
        + mdToHtml(out)
        + `<div class="chat-actions"><button class="btn btn-primary" onclick="runFromChat(${t.id})">▶ 生成可验证科学假设</button></div>`;
    }catch(e){
      holder.querySelector('.bubble').innerHTML =
        `<p class="muted small">Qwen 调用失败（${esc(e.message)}），已回退到离线证据库作答。</p>` + offlineAnswer(t);
    }
  }else{
    holder.querySelector('.bubble').innerHTML = offlineAnswer(t);
  }
  $('#chatScroll').scrollTop = $('#chatScroll').scrollHeight;
}

function askTopic(id){
  const t = KB.find(x=>x.id===id);
  $$('.topic-item').forEach(x=>x.classList.toggle('on', +x.dataset.id===id));
  handleAsk(t.title);
}
function askFaq(id, i){
  const t = KB.find(x=>x.id===id);
  const faq = t.faq[i];
  pushMsg('user', `<p>${esc(faq.q)}</p>`);
  pushMsg('ai', `<p>${esc(faq.a)}</p>
    <div class="chat-actions"><button class="btn btn-primary" onclick="runFromChat(${t.id})">▶ 生成可验证科学假设</button></div>`);
}
function runFromChat(id){
  $('#pipeTopic').value = String(id);
  goTab('pipe');
  runPipeline();
}

function initChat(){
  $('#topicList').innerHTML = KB.map(t=>`
    <div class="topic-item" data-id="${t.id}" onclick="askTopic(${t.id})">
      <span class="tid">${t.id}</span> ${esc(t.title)}
    </div>`).join('');
  $('#btnSend').addEventListener('click',()=>{
    const v = $('#chatInput').value; $('#chatInput').value=''; $('#chatInput').style.height='auto'; handleAsk(v);
  });
  $('#chatInput').addEventListener('keydown',e=>{
    if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); $('#btnSend').click(); }
  });
  $('#chatInput').addEventListener('input',e=>{
    e.target.style.height='auto'; e.target.style.height=Math.min(e.target.scrollHeight,140)+'px';
  });
}

/* ---------------- 流水线 ---------------- */
function initPipe(){
  $('#pipeTopic').innerHTML = KB.map(t=>`<option value="${t.id}">${t.id} · ${esc(t.title)}</option>`).join('');
  renderRail(null);
  $('#btnRun').addEventListener('click', runPipeline);
  $('#btnReset').addEventListener('click', ()=>{
    currentRun = null; selectedStage = null; renderRail(null);
    $('#stageDetail').innerHTML = `<div class="empty-state"><div class="empty-icon">⚗</div>
      <h3>流水线待运行</h3><p class="muted">选择议题后点击「运行流水线」。</p></div>`;
    $('#reportBody').innerHTML=''; $('#reportTitle').textContent='尚未生成研究计划';
    $('#reportMeta').textContent='请先在「假设生成流水线」中运行一次任务';
  });
}

function renderRail(run){
  $('#stageRail').innerHTML = PIPELINE.STAGES.map(s=>{
    const st = run ? run.stages[s.id] : {state:'idle'};
    const label = {idle:'待运行',run:'执行中',done:'完成',warn:'需修正'}[st.state] || '待运行';
    return `<div class="stage ${selectedStage===s.id?'sel':''}" data-state="${st.state}" data-id="${s.id}">
      <span class="stage-idx">${s.id}</span>
      <span class="stage-name">${esc(s.name)}<span class="stage-sub">${esc(s.sub)}</span></span>
      <span class="stage-state">${label}</span></div>`;
  }).join('') + `<div class="progress"><i id="progBar"></i></div>`;

  $$('.stage').forEach(el=>el.addEventListener('click',()=>{
    if(!currentRun) return;
    selectedStage = el.dataset.id;
    renderRail(currentRun);
    $('#stageDetail').innerHTML = renderStageDetail(currentRun, selectedStage);
  }));
}

async function runPipeline(){
  const id = +$('#pipeTopic').value;
  const topic = KB.find(t=>t.id===id);
  const opts = { maxIter:+$('#pipeIter').value, conThreshold:+$('#pipeThreshold').value };
  $('#btnRun').disabled = true; $('#btnRun').textContent='运行中…';
  selectedStage = null;

  let done = 0;
  const total = PIPELINE.STAGES.length;
  const onStage = async (run, sid, phase) => {
    currentRun = run;
    if(phase==='start'){
      selectedStage = sid; renderRail(run);
      $('#stageDetail').innerHTML = renderStageDetail(run, sid);
      await new Promise(r=>setTimeout(r, LLM.enabled?120:420));
    }else if(phase==='end'){
      done++; renderRail(run);
      $('#stageDetail').innerHTML = renderStageDetail(run, sid);
      const bar = $('#progBar'); if(bar) bar.style.width = Math.min(100, done/total*100)+'%';
      await new Promise(r=>setTimeout(r, LLM.enabled?80:260));
    }else if(phase==='loop'){
      done = Math.max(0, done-4); renderRail(run);
      await new Promise(r=>setTimeout(r, 500));
    }
  };

  try{
    const run = await PIPELINE.execute(topic, opts, onStage);
    currentRun = run;
    selectedStage = 'S11'; renderRail(run);
    $('#stageDetail').innerHTML = renderStageDetail(run, 'S11');
    const bar = $('#progBar'); if(bar) bar.style.width='100%';
    // 报告
    $('#reportTitle').textContent = run.report.fields.title;
    $('#reportMeta').textContent =
      `${topic.code}　迭代 ${run.report.round} 轮　自评 ${run.selfScore.total}/100　` +
      `模式：${LLM.enabled?('Qwen '+LLM.cfg.model):'离线演示'}　生成于 ${new Date().toLocaleString('zh-CN')}`;
    $('#reportBody').innerHTML = renderReport(run);
  }catch(e){
    $('#stageDetail').innerHTML = `<div class="verdict verdict-bad"><b>运行异常</b>${esc(e.message)}</div>`;
    console.error(e);
  }finally{
    $('#btnRun').disabled = false; $('#btnRun').textContent='▶ 运行流水线';
  }
}

/* ---------------- 导出 ---------------- */
function initExport(){
  $('#btnExportMd').addEventListener('click',()=>{
    if(!currentRun || !currentRun.report) return alert('请先运行一次流水线');
    download(`科学假设与研究计划_${currentRun.topic.code}.md`, reportToMarkdown(currentRun), 'text/markdown;charset=utf-8');
  });
  $('#btnExportJson').addEventListener('click',()=>{
    if(!currentRun || !currentRun.report) return alert('请先运行一次流水线');
    download(`ai_scientist_run_${currentRun.topic.code}.json`, reportToJson(currentRun), 'application/json');
  });
  $('#btnPrint').addEventListener('click',()=>{
    if(!currentRun || !currentRun.report) return alert('请先运行一次流水线');
    window.print();
  });
}

/* ---------------- 设置 ---------------- */
function refreshMode(){
  const on = LLM.enabled;
  $('#modeText').textContent = on ? `Qwen 真实模式 · ${LLM.cfg.model}` : '离线演示模式';
  $('#modePill').querySelector('.dot').className = 'dot ' + (on?'dot-online':'dot-offline');
}
function initSettings(){
  $('#inpKey').value = LLM.cfg.key;
  $('#inpModel').value = LLM.cfg.model;
  $('#inpBase').value = LLM.cfg.base;
  $('#btnSettings').addEventListener('click',()=>$('#modalMask').classList.add('show'));
  $('#modalMask').addEventListener('click',e=>{ if(e.target.id==='modalMask') $('#modalMask').classList.remove('show'); });
  $('#btnSaveKey').addEventListener('click',()=>{
    LLM.save($('#inpKey').value.trim(), $('#inpModel').value, $('#inpBase').value.trim());
    refreshMode(); $('#modalMask').classList.remove('show');
  });
  $('#btnClearKey').addEventListener('click',()=>{
    LLM.clear(); $('#inpKey').value=''; $('#inpBase').value=LLM.cfg.base;
    refreshMode(); $('#testResult').textContent='';
  });
  $('#btnTest').addEventListener('click', async ()=>{
    const r = $('#testResult'); r.textContent = '测试中…'; r.style.color='var(--muted)';
    LLM.save($('#inpKey').value.trim(), $('#inpModel').value, $('#inpBase').value.trim());
    try{
      const res = await LLM.test();
      r.textContent = `连通正常（${res.ms} ms）：${res.out.slice(0,20)}`; r.style.color='var(--green)';
      refreshMode();
    }catch(e){
      r.textContent = `失败：${e.message.slice(0,90)}`; r.style.color='var(--red)';
    }
  });
  refreshMode();
}

/* ---------------- 启动 ---------------- */
window.addEventListener('DOMContentLoaded',()=>{
  initTabs(); initArch(); initChat(); initPipe(); initExport(); initSettings();
  document.querySelector('[data-node="S6"]').click();
});
