/**
 * selftest.js —— 无浏览器环境下的流水线自检
 * 运行： node selftest.js
 * 用途：CI / 提交前验证 11 阶段闭环、三重闸门、统计引擎与 10 字段输出均正常。
 */
const fs = require('fs'), path = require('path');

// 极简浏览器环境垫片
global.localStorage = { _d:{}, getItem(k){return this._d[k]||null;}, setItem(k,v){this._d[k]=v;}, removeItem(k){delete this._d[k];} };
global.performance = { now: () => Date.now() };
global.fetch = async () => { throw new Error('offline'); };

const vm = require('vm');
const load = f => vm.runInThisContext(fs.readFileSync(path.join(__dirname,'js',f),'utf8'), {filename:f});
['refs.js','kb.js','stats.js','llm.js','pipeline.js'].forEach(load);

(async () => {
  console.log('AI Scientist 原型 · 流水线自检\n' + '='.repeat(62));
  let pass = 0, fail = 0;
  const check = (ok, msg) => { ok ? pass++ : fail++; console.log(`  ${ok?'✓':'✗'} ${msg}`); };

  check(KB.length === 8, `知识库载入 ${KB.length} 个议题（期望 8）`);
  check(Object.keys(REFS).length >= 40, `文献索引 ${Object.keys(REFS).length} 条`);

  // 所有引用编号必须存在于文献库（防虚构引用）
  let badRef = [];
  KB.forEach(t => {
    const all = new Set();
    [...t.consensus,...t.disputes,...t.gaps,...t.debate.pro,...t.debate.con]
      .forEach(e => (e.refs||[]).forEach(r => all.add(r)));
    (t.hypothesis.refs||[]).forEach(r => all.add(r));
    all.forEach(r => { if(!REFS[r]) badRef.push(`${t.id}:${r}`); });
  });
  check(badRef.length === 0, `引用完整性校验（悬空引用 ${badRef.length} 条）${badRef.length?' → '+badRef.join(','):''}`);

  // 统计引擎正确性：构造强相关数据应显著
  const rng = makeRNG(42);
  const xs=[], ys=[];
  for(let i=0;i<50;i++){ const x=rng()*10; xs.push(x); ys.push(2*x + gauss(rng)*0.5); }
  const ct = corrTest(xs, ys);
  check(ct.r > 0.95 && ct.p < 0.001, `统计引擎：强相关检出 r=${ct.r.toFixed(3)}, p=${ct.p.toExponential(1)}`);
  const wt = welchT([5,5.2,4.8,5.1,5.3,4.9,5.0,5.2], [1,1.2,0.8,1.1,1.3,0.9,1.0,1.2]);
  check(wt.p < 0.001 && wt.d > 3, `统计引擎：分组差异检出 t=${wt.t.toFixed(2)}, d=${wt.d.toFixed(2)}`);

  console.log('\n  逐议题跑通 11 阶段闭环：');
  for(const topic of KB){
    const run = await PIPELINE.execute(topic, {maxIter:2, conThreshold:3}, async()=>{});
    const stagesDone = Object.values(run.stages).filter(s=>s.state==='done'||s.state==='warn').length;
    const f = run.report.fields;
    const tenFields = ['problem','idea','tech','dataset','title','abstract','methodology','experiment','results','refs']
      .every(k => f[k] && (Array.isArray(f[k]) ? f[k].length : (typeof f[k]==='object' ? f[k].source&&f[k].target : String(f[k]).length>10)));
    const ok = stagesDone === 11 && tenFields && run.selfScore.total > 0;
    check(ok, `${topic.code} 阶段 ${stagesDone}/11 · 迭代 ${run.round} 轮 · 闸门[辩${run.gates.debate?'✓':'×'} 溯${run.gates.grounding?'✓':'×'} 量${run.gates.causal?'✓':'×'}] · 10字段${tenFields?'完整':'缺失'} · 自评 ${run.selfScore.total}/100`);
  }

  console.log('\n' + '='.repeat(62));
  console.log(`  通过 ${pass} 项，失败 ${fail} 项`);
  process.exit(fail ? 1 : 0);
})();
