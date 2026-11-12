const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('commentary-tabs.js','utf8');
for(const reduced of [false,true]){
 let click,mutate,height=200,frames=[],cancelled=0;
 const animations=[];const active={getAttribute:()=> 'tabpanel',classList:{contains:()=>true},animate:()=>({})};
 const root={dataset:{},children:[active],addEventListener:(e,cb)=>click=cb,getBoundingClientRect:()=>({height}),animate:(f,t)=>{const a={cancel:()=>cancelled++};animations.push({f,t,a});return a;}};
 const ctx={document:{getElementById:()=>root},matchMedia:()=>({matches:reduced}),getComputedStyle:()=>({display:'block'}),MutationObserver:class{constructor(fn){mutate=fn}observe(){}},requestAnimationFrame:fn=>frames.push(fn)};
 vm.runInNewContext('('+source+')()',ctx);
 const button={getAttribute:()=> 'false'};
 click({target:{closest:()=>button}});height=500;mutate();frames.splice(0).forEach(fn=>fn());
 assert.equal(animations.length,reduced?0:1);
 if(!reduced){assert.equal(animations[0].f[0].height,'200px');assert.equal(animations[0].f[1].height,'500px');assert.equal(animations[0].t.duration,220);}
 click({target:{closest:()=>button}});height=200;mutate();frames.splice(0).forEach(fn=>fn());
 if(!reduced){assert.equal(animations[1].f[0].height,'500px');assert.equal(animations[1].f[1].height,'200px');assert.equal(cancelled,1);}
}
console.log('PASS commentary tab expand/collapse, cancellation, reduced motion');
