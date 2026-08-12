/**
 * measure.js —— 测量 S7 溯源闸门可用的真实 Jaccard 分布
 * 运行： node measure.js
 */
const fs = require('fs'), path = require('path');
global.localStorage = { _d:{}, getItem(k){return this._d[k]||null;}, setItem(k,v){this._d[k]=v;}, removeItem(k){delete this._d[k];} };
global.performance = { now: () => Date.now() };
global.fetch = async () => { throw new Error('offline'); };
const vm = require('vm');
const load = f => vm.runInThisContext(fs.readFileSync(path.join(__dirname,'js',f),'utf8'), {filename:f});
['refs.js','kb.js','stats.js','llm.js','pipeline.js'].forEach(load);

function bigrams(s){
  const t = (s||'').replace(/[\s，。、；：""''（）()《》,.;:!?]/g,'');
  const set = new Set();
  for(let i=0;i<t.length-1;i++) set.add(t.slice(i,i+2));
  return set;
}
function jaccard(a,b){
  const A = bigrams(a), B = bigrams(b);
  if(!A.size || !B.size) return 0;
  let inter = 0;
  A.forEach(g => { if(B.has(g)) inter++; });
  return inter / (A.size + B.size - inter);
}

const scores = [];
const perTopic = {};
KB.forEach(t => {
  perTopic[t.code] = { premiseScores: [], dangling: [] };
  // 假设引用的文献前提：共识 + 争议 + 空白 陈述，各自绑定 ref
  [...t.consensus, ...t.disputes, ...t.gaps].forEach(e => {
    (e.refs||[]).forEach(r => {
      if(!REFS[r]){ perTopic[t.code].dangling.push(r); return; }
      const s = jaccard(e.t, REFS[r].d);
      scores.push(s);
      perTopic[t.code].premiseScores.push(s);
    });
  });
});

scores.sort((a,b)=>a-b);
const pct = p => scores[Math.min(scores.length-1, Math.floor(p*scores.length))];
console.log('前提陈述(共识/争议/空白) 对 其引用文献.d 的 Jaccard 分布');
console.log(`  n=${scores.length}`);
console.log(`  p10=${ (pct(0.10)*100).toFixed(1)}%  p25=${(pct(0.25)*100).toFixed(1)}%  p50=${(pct(0.50)*100).toFixed(1)}%  p75=${(pct(0.75)*100).toFixed(1)}%  p90=${(pct(0.90)*100).toFixed(1)}%`);
const le = th => scores.filter(s=>s<th).length;
console.log(`  < 3.5% : ${le(0.035)} 条 (${((le(0.035)/scores.length)*100).toFixed(0)}%)`);
console.log(`  < 7.5% : ${le(0.075)} 条 (${((le(0.075)/scores.length)*100).toFixed(0)}%)`);

console.log('\n每个议题的前提溯源得分（最低 3 条）：');
KB.forEach(t => {
  const ps = perTopic[t.code].premiseScores;
  ps.sort((a,b)=>a-b);
  const low = ps.slice(0,3).map(s=>(s*100).toFixed(1)+'%').join(', ');
  console.log(`  ${t.code}  n=${ps.length}  最低: ${low}  悬空引用: ${perTopic[t.code].dangling.length}`);
});

// 假设自身引用的文献是否都真实
console.log('\n假设 h.refs 完整性：');
KB.forEach(t => {
  const bad = (t.hypothesis.refs||[]).filter(r=>!REFS[r]);
  console.log(`  ${t.code}  refs=${t.hypothesis.refs.length}  悬空=${bad.length}`);
});
