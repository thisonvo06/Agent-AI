/**
 * stats.js —— 因果量化检验模块的统计引擎
 * ------------------------------------------------------------------
 * 说明：本文件中的统计量（Pearson r、独立样本 t 检验、效应量 Cohen's d、
 * 线性回归）都是在浏览器内对数据真实计算得出的，不是预先写死的数字。
 * 演示模式下的数据由固定种子的随机数发生器按预设效应量合成，
 * 因此结果可复现；接入真实数据时只需替换 buildDataset 的数据源。
 */

/** 可复现的伪随机数发生器（mulberry32） */
function makeRNG(seed){
  let a = seed >>> 0;
  return function(){
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/** Box-Muller 标准正态 */
function gauss(rng){
  let u = 0, v = 0;
  while(u === 0) u = rng();
  while(v === 0) v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

const mean = a => a.reduce((s,x)=>s+x,0) / a.length;
const sd = a => { const m = mean(a); return Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0) / (a.length-1)); };

/** Pearson 相关系数 */
function pearson(x,y){
  const mx = mean(x), my = mean(y);
  let num=0, dx=0, dy=0;
  for(let i=0;i<x.length;i++){
    const a=x[i]-mx, b=y[i]-my;
    num+=a*b; dx+=a*a; dy+=b*b;
  }
  return num / Math.sqrt(dx*dy);
}

/** 简单一元线性回归，返回斜率与截距 */
function linreg(x,y){
  const mx=mean(x), my=mean(y);
  let num=0, den=0;
  for(let i=0;i<x.length;i++){ num+=(x[i]-mx)*(y[i]-my); den+=(x[i]-mx)**2; }
  const slope = num/den;
  return { slope, intercept: my - slope*mx };
}

/** 学生 t 分布的双侧 p 值（Lentz 连分式实现的不完全贝塔函数） */
function betacf(a,b,x){
  const FPMIN=1e-300, EPS=3e-12;
  const qab=a+b, qap=a+1, qam=a-1;
  let c=1, d=1-qab*x/qap;
  if(Math.abs(d)<FPMIN) d=FPMIN;
  d=1/d; let h=d;
  for(let m=1;m<=200;m++){
    const m2=2*m;
    let aa=m*(b-m)*x/((qam+m2)*(a+m2));
    d=1+aa*d; if(Math.abs(d)<FPMIN) d=FPMIN;
    c=1+aa/c; if(Math.abs(c)<FPMIN) c=FPMIN;
    d=1/d; h*=d*c;
    aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2));
    d=1+aa*d; if(Math.abs(d)<FPMIN) d=FPMIN;
    c=1+aa/c; if(Math.abs(c)<FPMIN) c=FPMIN;
    d=1/d; const del=d*c; h*=del;
    if(Math.abs(del-1)<EPS) break;
  }
  return h;
}
function lngamma(z){
  const g=[76.18009172947146,-86.50532032941677,24.01409824083091,
           -1.231739572450155,0.1208650973866179e-2,-0.5395239384953e-5];
  let x=z, y=z, tmp=x+5.5;
  tmp-=(x+0.5)*Math.log(tmp);
  let ser=1.000000000190015;
  for(let j=0;j<6;j++) ser+=g[j]/++y;
  return -tmp+Math.log(2.5066282746310005*ser/x);
}
function betai(a,b,x){
  if(x<=0) return 0;
  if(x>=1) return 1;
  const bt=Math.exp(lngamma(a+b)-lngamma(a)-lngamma(b)+a*Math.log(x)+b*Math.log(1-x));
  return x < (a+1)/(a+b+2) ? bt*betacf(a,b,x)/a : 1-bt*betacf(b,a,1-x)/b;
}
/** 双侧 p 值 */
function tToP(t,df){
  return betai(df/2, 0.5, df/(df + t*t));
}

/** 相关系数显著性检验 */
function corrTest(x,y){
  const r = pearson(x,y);
  const n = x.length, df = n-2;
  const t = r * Math.sqrt(df / (1 - r*r));
  return { r, t, df, p: tToP(t, df), n };
}

/** 独立样本 t 检验（Welch 校正） */
function welchT(a,b){
  const ma=mean(a), mb=mean(b), va=sd(a)**2, vb=sd(b)**2;
  const na=a.length, nb=b.length;
  const t=(ma-mb)/Math.sqrt(va/na + vb/nb);
  const df=Math.pow(va/na+vb/nb,2) / (Math.pow(va/na,2)/(na-1) + Math.pow(vb/nb,2)/(nb-1));
  const sp=Math.sqrt(((na-1)*va + (nb-1)*vb)/(na+nb-2));
  return { t, df, p: tToP(t,df), meanA: ma, meanB: mb, d: (ma-mb)/sp, nA: na, nB: nb };
}

/**
 * 按议题的因果检验配置合成数据集
 * spec: { n, effect, noise, groupDelta, groupNoise }
 */
function buildDataset(spec, seed){
  const rng = makeRNG(seed);
  const x = [], y = [], gA = [], gB = [];
  const n = spec.n;
  for(let i=0;i<n;i++){
    const xi = rng()*10;
    // y = effect * x + 噪声   (effect 已按标准化尺度给出)
    const yi = spec.effect * xi + gauss(rng) * spec.noise * 3 + 5;
    x.push(xi); y.push(yi);
  }
  const half = Math.floor(n/2);
  for(let i=0;i<half;i++){
    gA.push(spec.groupDelta + gauss(rng)*spec.groupNoise);
    gB.push(gauss(rng)*spec.groupNoise);
  }
  return { x, y, gA, gB };
}

/** 执行完整的因果量化检验，返回结构化结论 */
function runCausalCheck(spec, seed){
  const ds = buildDataset(spec, seed);
  const corr = corrTest(ds.x, ds.y);
  const grp = welchT(ds.gA, ds.gB);

  const strength = Math.abs(corr.r);
  const corrSig = corr.p < 0.05;
  const grpSig = grp.p < 0.05;

  let level, verdict, advice;
  if(!corrSig && !grpSig){
    level = 'bad';
    verdict = '数据不支持假设所述的变量关联：相关性与分组差异均不显著。';
    advice = '按闸门规则判定假设无效，需更换研究变量或重新界定测量口径后重新生成。';
  }else if(corrSig && strength < 0.3){
    level = 'warn';
    verdict = '关联统计显著但效应量偏小（|r| < 0.3），不足以支撑强因果表述。';
    advice = '结论必须降级为"存在弱关联"，并在假设中显式标注需要工具变量或准实验设计来识别因果。';
  }else if(corrSig && !grpSig){
    level = 'warn';
    verdict = '连续变量关联显著，但分组对照未见显著差异，存在混杂或调节变量的可能。';
    advice = '需补充分层分析与协变量控制，结论适用范围应限定在已观测的分组条件内。';
  }else{
    level = 'ok';
    verdict = '相关性与分组差异双双显著，且效应量达到可解释量级，假设通过量化闸门。';
    advice = '仍需注意：统计关联不等于因果，正式研究须补充因果识别策略（工具变量 / DID / 随机化）。';
  }
  return { ds, corr, grp, level, verdict, advice, corrSig, grpSig };
}

/** 数字格式化 */
const fx = (v,d=3) => (Math.abs(v) < 0.001 && v !== 0) ? v.toExponential(2) : v.toFixed(d);
const pfmt = p => p < 0.001 ? '< 0.001' : p.toFixed(4);
