const assert = require('node:assert/strict');
const M = require('./model.js');
function simulate(overrides, seconds=12) {
  const p={...M.defaults,...overrides},s=M.create(p),samples=[];
  for(let i=0;i<seconds*240;i++) {
    M.step(s,p);
    for(const [k,v] of Object.entries(s))if(v!==null)assert.ok(Number.isFinite(v),`${k} finite`);
    assert.ok(s.q>=0&&s.q<=120*M.rad,'joint bounds');
    assert.ok(s.pf>=0&&s.pe>=0&&s.pf<=250.0001&&s.pe<=250.0001,'pressure bounds');
    if(i>240)samples.push({...s});
  }
  return {s,p,samples};
}
const assist=simulate({}),off=simulate({assist:false});
const rms=(a,key)=>Math.sqrt(a.reduce((sum,d)=>sum+d[key]*d[key],0)/a.length);
const error=a=>Math.sqrt(a.reduce((sum,d)=>sum+(d.q/M.rad-d.target)**2,0)/a.length);
assert.ok(error(assist.samples)<8,'assisted cycle tracks within conceptual tolerance');
assert.ok(error(off.samples)<3,'unassisted ideal wearer follows target');
assert.ok(rms(assist.samples,'human')<rms(off.samples,'human'),'assistance reduces model wearer demand');
assert.equal(off.s.pf,0);assert.equal(off.s.pe,0);
const relaxed=simulate({mode:'manual',target:30});
assert.ok(relaxed.s.q/M.rad>80&&relaxed.s.q/M.rad<100,'gravity lowers relaxed shank');
const extended=simulate({mode:'manual',target:60,manualExt:250});
assert.ok(extended.s.q<relaxed.s.q,'extension pressure straightens shank');
const flexed=simulate({mode:'manual',target:60,manualFlex:250});
assert.ok(flexed.s.q>relaxed.s.q,'flexion pressure bends shank');
const co=simulate({mode:'manual',manualExt:100,manualFlex:100});
assert.ok(Math.abs(co.s.pf-100)<1e-8&&Math.abs(co.s.pe-100)<1e-8,'independent banks');
const p={...M.defaults,mode:'manual',manualExt:120},lag=M.create(p);
for(let i=0;i<60;i++)M.step(lag,p);
assert.ok(Math.abs(lag.pe-120*(1-Math.exp(-1)))<1e-9,'pressure reaches 63.2% after one time constant');
p.assist=false;const before=lag.pe;M.step(lag,p);assert.ok(lag.pe<before&&lag.pe>0,'assistance off vents gradually');
for(const mode of ['cycle','hold','manual'])for(const mass of [1,8])for(const gain of [.02,.3])for(const lag of [.05,1]) {
  simulate({mode,mass,gain,lag,supply:250,manualFlex:250,manualExt:250,period:3},20);
}
console.log(JSON.stringify({passed:true,assistedAngleRMSEdeg:error(assist.samples),unassistedAngleRMSEdeg:error(off.samples),assistedHumanRMSNm:rms(assist.samples,'human'),unassistedHumanRMSNm:rms(off.samples,'human'),extremeTrials:24},null,2));
