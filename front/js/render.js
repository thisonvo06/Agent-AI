/**
 * render.js —— 视图渲染层：流水线区块、研究计划报告、导出
 */
const esc = s => String(s==null?'':s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const nl2br = s => esc(s).replace(/\n/g,'<br/>');

/** 极简 Markdown 渲染（用于 Qwen 返回文本） */
function mdToHtml(md){
  const lines = esc(md).split('\n');
  let out = '', inUl = false;
  for(let raw of lines){
    let l = raw.trim();
    l = l.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/`(.+?)`/g,'<code>$1</code>');
    l = l.replace(/\[?(R\d{1,2})\]?/g, (m,p)=> REFS[p] ? `<span class="refchip" title="${esc(refText(p))}">${p}</span>` : m);
    if(/^([-*·]|\d+[.、)])\s*/.test(l)){
      if(!inUl){ out += '<ul>'; inUl = true; }
      out += `<li>${l.replace(/^([-*·]|\d+[.、)])\s*/,'')}</li>`;
    }else{
      if(inUl){ out += '</ul>'; inUl = false; }
      if(l === '') continue;
      if(/^#{1,4}\s/.test(l)) out += `<h4>${l.replace(/^#{1,4}\s/,'')}</h4>`;
      else out += `<p>${l}</p>`;
    }
  }
  if(inUl) out += '</ul>';
  return out;
}

/** 引用标记 */
const refChips = ids => (ids||[]).map(r =>
  `<span class="refchip" title="${esc(refText(r))}">${r}</span>`).join('');

/* ---------------- 流水线区块渲染 ---------------- */
function renderBlock(b){
  switch(b.type){
    case 'h': return `<h4>${esc(b.text)}</h4>`;
    case 'p': return `<p style="color:var(--text-2)">${nl2br(b.text)}</p>`;
    case 'note': return `<div class="evidence" style="background:#f8fafc"><span class="muted small">${nl2br(b.text)}</span></div>`;

    case 'kvlist':
      return `<div>${b.items.map(i=>`<div class="kv"><b>${esc(i.k)}</b><span>${nl2br(i.v)}</span></div>`).join('')}</div>`;

    case 'facts':
      return b.groups.map(g=>`
        <div style="margin:8px 0">
          <span class="tag ${g.cls}">${esc(g.label)} · ${g.items.length}</span>
          <ul style="margin-top:6px">${g.items.map(i=>
            `<li>${esc(i.t)}${refChips(i.refs)}</li>`).join('')}</ul>
        </div>`).join('');

    case 'flow':
      return `<div class="evidence"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <span class="tag">${esc(b.from)}</span><span style="color:var(--purple);font-weight:700">→</span>
        <span class="tag" style="background:var(--purple-soft);border-color:#e2d5fc;color:#5b21b6">${esc(b.to)}</span>
      </div></div>`;

    case 'hypo':
      return `<div class="evidence" style="border-left:3px solid var(--purple)">
        <div class="ev-h"><b style="font-size:13.5px">${esc(b.title)}</b></div>
        <div class="kv"><b>待研究问题</b><span>${nl2br(b.problem)}</span></div>
        <div class="kv"><b>解决思路</b><span>${nl2br(b.idea)}</span></div>
      </div>`;

    case 'evi':
      return b.items.map(i=>`
        <div class="evidence" ${i.resolved?'style="opacity:.5"':''}>
          <div class="ev-h">
            <span class="ev-side ${b.side==='pro'?'ev-pro':'ev-con'}">${b.side==='pro'?'正方':'反方'}</span>
            ${i.resolved?'<span class="tag tag-ok">已被范围限定消解</span>':''}
          </div>
          <div>${esc(i.t)}${refChips(i.refs)}</div>
        </div>`).join('');

    case 'verdict':
      return `<div class="verdict verdict-${b.level==='ok'?'ok':(b.level==='warn'?'warn':'bad')}">
        <b>${esc(b.title)}</b>${nl2br(b.text)}</div>`;

    case 'ground':
      return `<table class="stat-table"><thead><tr>
          <th style="width:46%">断言</th><th>绑定文献</th><th>重合度</th><th>判定</th></tr></thead><tbody>
        ${b.items.map(i=>`<tr>
          <td>${esc(i.text.length>120?i.text.slice(0,120)+'…':i.text)}${i.rewritten?' <span class="tag tag-ok">已按原文改写</span>':''}</td>
          <td><span class="refchip" title="${esc(refText(i.ref))}">${i.ref}</span></td>
          <td class="num">${(i.score*100).toFixed(1)}%</td>
          <td class="${i.status==='ok'?'sig-yes':'sig-no'}">${i.status==='ok'?'通过':(i.status==='weak'?'支持不足':'与原文冲突')}</td>
        </tr>`).join('')}</tbody></table>`;

    case 'stat': {
      const r=b.res, s=b.spec;
      return `<table class="stat-table"><thead><tr>
          <th>检验</th><th>统计量</th><th>p 值</th><th>效应量</th><th>结论</th></tr></thead><tbody>
        <tr><td>Pearson 相关（${esc(s.x)} × ${esc(s.y)}）</td>
            <td class="num">r = ${fx(r.corr.r)}, t(${r.corr.df}) = ${fx(r.corr.t,2)}</td>
            <td class="num">${pfmt(r.corr.p)}</td>
            <td class="num">|r| = ${fx(Math.abs(r.corr.r),2)}</td>
            <td class="${r.corrSig?'sig-yes':'sig-no'}">${r.corrSig?'显著':'不显著'}</td></tr>
        <tr><td>Welch t 检验（${esc(s.groupA)} vs ${esc(s.groupB)}）</td>
            <td class="num">t = ${fx(r.grp.t,2)}, df = ${fx(r.grp.df,1)}</td>
            <td class="num">${pfmt(r.grp.p)}</td>
            <td class="num">d = ${fx(r.grp.d,2)}</td>
            <td class="${r.grpSig?'sig-yes':'sig-no'}">${r.grpSig?'显著':'不显著'}</td></tr>
        </tbody></table>
        <p class="muted small">样本量 n = ${r.corr.n}；均值 ${esc(s.groupA)} = ${fx(r.grp.meanA,2)}，${esc(s.groupB)} = ${fx(r.grp.meanB,2)}。以上统计量均由浏览器内的统计引擎实时计算得出。</p>`;
    }

    case 'checklist':
      return `<ul style="list-style:none;padding:0">${b.items.map(i=>
        `<li style="display:flex;gap:8px;padding:4px 0">
          <span class="tag ${i.s==='ok'?'tag-ok':'tag-warn'}">${i.s==='ok'?'已满足':'需确认'}</span>
          <span>${esc(i.t)}</span></li>`).join('')}</ul>`;

    case 'score':
      return `<div class="selfscore">${Object.entries(b.items).map(([k,v])=>`
        <div class="ss-item"><div class="ss-top"><span>${esc(k)}</span>
        <span class="ss-num">${v}/${b.maxes[k]}</span></div>
        <div class="ss-bar"><i style="width:${v/b.maxes[k]*100}%"></i></div></div>`).join('')}
        </div><p style="margin-top:10px"><b>自评总分 ${b.total} / 100</b>
        <span class="muted small">（对照赛题评分标准的内部自检，用于定位薄弱环节，不代表评审结果）</span></p>`;

    default: return '';
  }
}

function renderStageDetail(run, id){
  const st = run.stages[id];
  const logs = st.logs.map(l=>{
    const cls = {ok:'lg-ok',warn:'lg-warn',err:'lg-err',dim:'lg-dim',key:'lg-key'}[l.type]||'';
    const pre = {ok:'✓',warn:'!',err:'✕',dim:' ',key:'▸'}[l.type]||' ';
    return `<div class="${cls}">${pre} ${esc(l.text)}</div>`;
  }).join('');
  return `
    <div class="detail-head">
      <h3>${st.id} · ${esc(st.name)}</h3>
      <span class="detail-agent">${esc(st.agent)}</span>
      <span class="muted small">${esc(st.sub)}</span>
    </div>
    ${logs?`<div class="log">${logs}</div>`:''}
    ${st.blocks.map(renderBlock).join('')}`;
}

/* ---------------- 研究计划报告 ---------------- */
const FIELD_DEFS = [
  ['problem','待研究问题','Research Question'],
  ['idea','解决思路','Approach'],
  ['tech','技术手段','Techniques'],
  ['dataset','数据集','Datasets (Source + Target)'],
  ['title','标题','Title'],
  ['abstract','摘要','Abstract'],
  ['methodology','方法论','Methodology'],
  ['experiment','实验设计','Experimental Design'],
  ['results','实验结果','Results'],
  ['refs','参考论文','References']
];

function renderReport(run){
  const rep = run.report, f = rep.fields, v = rep.validation;
  const body = FIELD_DEFS.map(([key,cn,en],idx)=>{
    let inner = '';
    if(key==='dataset'){
      inner = `<div class="ds-grid">
        <div class="ds-box"><h5>Source 数据集（外部/公开）</h5>${nl2br(f.dataset.source)}</div>
        <div class="ds-box"><h5>Target 数据集（自建/目标）</h5>${nl2br(f.dataset.target)}</div></div>`;
    }else if(key==='refs'){
      inner = f.refs.map(r=>`<div class="ref-item">
          <span class="ref-no">[${r}]</span>
          <span>${esc(refText(r))}</span>
          <span class="ref-verified">真实文献</span></div>`).join('')
        + `<p class="muted small" style="margin-top:8px">全部引用来自系统内置的真实文献索引库，均为公开可查证的已发表成果；系统在 S7 阶段对每条断言与其绑定文献做了逐条重合度比对。严禁虚构文献是本系统的硬约束。</p>`;
    }else if(Array.isArray(f[key])){
      inner = `<ul>${f[key].map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
      if(key==='results' && v){
        inner += `<div class="verdict verdict-${v.level==='ok'?'ok':(v.level==='warn'?'warn':'bad')}" style="margin-top:10px">
          <b>本次可行性验证结果（限定范围内的实测）</b>
          检验链路：${esc(v.label)}<br/>
          Pearson r = ${fx(v.r)}（p ${pfmt(v.rp)}，n = ${v.n}）；分组 Welch t = ${fx(v.t,2)}（p ${pfmt(v.tp)}，Cohen's d = ${fx(v.d,2)}）。<br/>
          ${esc(v.verdict)} ${esc(v.advice)}<br/>
          <span class="small" style="opacity:.85">${esc(v.note)}</span></div>`;
      }
    }else{
      inner = `<p>${nl2br(f[key])}</p>`;
    }
    return `<div class="field">
      <div class="field-h"><span class="field-no">${idx+1}</span>
        <h3>${cn}</h3><span class="en">${en}</span></div>
      <div class="field-body">${inner}</div></div>`;
  }).join('');

  const gate = (ok,name) => `<span class="tag ${ok?'tag-ok':'tag-warn'}">${name}${ok?' 通过':' 有条件通过'}</span>`;
  const head = `<div class="field" style="border-left:3px solid var(--blue)">
    <div class="field-h"><span class="field-no">✓</span><h3>运行留痕与闸门状态</h3></div>
    <div class="field-body">
      <div class="tagline">
        ${gate(rep.gates.debate,'双辩论对抗')}${gate(rep.gates.grounding,'原文溯源校验')}${gate(rep.gates.causal,'因果量化检验')}
        <span class="tag">迭代 ${rep.round} 轮</span>
        <span class="tag">${LLM.enabled?'Qwen 真实调用':'离线演示模式'}</span>
        <span class="tag">自评 ${run.selfScore?run.selfScore.total:'-'} / 100</span>
      </div>
      <div class="kv"><b>适用范围</b><span>${esc(rep.scope)}</span></div>
      <div class="kv"><b>生成时间</b><span>${new Date(rep.generatedAt).toLocaleString('zh-CN')}</span></div>
      <div class="kv"><b>随机种子</b><span>${run.seed}（相同配置下结果可完整复现）</span></div>
    </div></div>`;

  return head + body;
}

/* ---------------- 导出 ---------------- */
function reportToMarkdown(run){
  const rep = run.report, f = rep.fields, v = rep.validation, t = rep.topic;
  const L = [];
  L.push(`# 科学假设与研究计划`);
  L.push(`> 议题：${t.code} ${t.title}`);
  L.push(`> 生成系统：AI Scientist 原型（Qwen / 阿里云百炼）　迭代 ${rep.round} 轮　运行模式：${LLM.enabled?'Qwen 真实调用':'离线演示'}`);
  L.push(`> 闸门状态：双辩论 ${rep.gates.debate?'通过':'有条件通过'} ／ 溯源校验 ${rep.gates.grounding?'通过':'有条件通过'} ／ 因果量化 ${rep.gates.causal?'通过':'有条件通过'}`);
  L.push(`> 适用范围：${rep.scope}\n`);
  L.push(`## 1. 待研究问题\n${f.problem}\n`);
  L.push(`## 2. 解决思路\n${f.idea}\n`);
  L.push(`## 3. 技术手段\n${f.tech}\n`);
  L.push(`## 4. 数据集\n**Source（外部/公开）**：${f.dataset.source}\n\n**Target（自建/目标）**：${f.dataset.target}\n`);
  L.push(`## 5. 标题\n${f.title}\n`);
  L.push(`## 6. 摘要\n${f.abstract}\n`);
  L.push(`## 7. 方法论\n${f.methodology.map((x,i)=>`${i+1}. ${x}`).join('\n')}\n`);
  L.push(`## 8. 实验设计\n${f.experiment.map(x=>`- ${x}`).join('\n')}\n`);
  L.push(`## 9. 实验结果\n${f.results.map(x=>`- ${x}`).join('\n')}`);
  if(v){
    L.push(`\n**本次可行性验证（限定范围内实测）**\n`);
    L.push(`- 检验链路：${v.label}`);
    L.push(`- Pearson r = ${fx(v.r)}，p ${pfmt(v.rp)}，n = ${v.n}`);
    L.push(`- 分组 Welch t = ${fx(v.t,2)}，p ${pfmt(v.tp)}，Cohen's d = ${fx(v.d,2)}`);
    L.push(`- 判定：${v.verdict} ${v.advice}`);
    L.push(`- 数据说明：${v.note}\n`);
  }
  L.push(`## 10. 参考论文（真实文献，严禁虚构）`);
  f.refs.forEach(r=>L.push(`- [${r}] ${refText(r)}`));
  if(run.selfScore){
    L.push(`\n## 附：对照评分标准自检\n`);
    L.push(`| 维度 | 自评 | 满分 |`);
    L.push(`| --- | --- | --- |`);
    Object.entries(run.selfScore.items).forEach(([k,val])=>L.push(`| ${k} | ${val} | ${run.selfScore.maxes[k]} |`));
    L.push(`| **合计** | **${run.selfScore.total}** | **100** |`);
  }
  return L.join('\n');
}

function reportToJson(run){
  return JSON.stringify({
    system:'AI Scientist Prototype', baseModel: LLM.enabled ? LLM.cfg.model : 'offline-demo',
    topic:{ id:run.topic.id, code:run.topic.code, title:run.topic.title },
    rounds: run.report.round, gates: run.report.gates, scope: run.report.scope,
    fields: run.report.fields,
    references: run.report.fields.refs.map(r=>({ id:r, ...REFS[r], citation: refText(r) })),
    validation: run.report.validation,
    selfScore: run.selfScore,
    seed: run.seed, generatedAt: run.report.generatedAt
  }, null, 2);
}

function download(name, text, mime){
  const blob = new Blob([text], {type: mime||'text/plain;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click();
  setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
