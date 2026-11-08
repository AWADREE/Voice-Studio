const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('night-sky.js','utf8');
new Function('return '+source);
const handler=source.slice(source.indexOf('const modeNav ='),source.indexOf('// Original procedural backdrop'));
for(const narrow of [false,true])for(const reduced of [false,true]){
 const classes=new Set();let timer,delay,cancelled=0,refreshed=0,listener;
 const buttons=['clone','generate'].map(mode=>({dataset:{voiceMode:mode},setAttribute(k,v){this[k]=v;}}));
 const nav={dataset:{},addEventListener(t,f){listener=f},querySelectorAll(){return buttons}};
 const picker={};const cache=new WeakMap([[picker,{animation:{cancel(){cancelled++}},bodyAnimation:{cancel(){cancelled++}}}]]);
 const workspace={clientWidth:1000,classList:{contains:n=>classes.has(n),add:n=>classes.add(n),remove:n=>classes.delete(n),toggle(n,v){v?classes.add(n):classes.delete(n)}},style:{setProperty(k,v){this[k]=v;}}};
 const reference={querySelectorAll(){return[picker]},setAttribute(k,v){this[k]=v;}};
 vm.runInNewContext(handler,{document:{querySelector:s=>s==='#voice-mode-tabs'?nav:s==='#voice-mode-workspace'?workspace:reference},matchMedia:q=>({matches:q.includes('800')?narrow:reduced}),pickerGeometry:cache,setTimeout(f,d){timer=f;delay=d;return 1},clearTimeout(){},requestAnimationFrame:f=>f(),animatePickerGeometry(){refreshed++}});
 const click=i=>listener({target:{closest:()=>buttons[i]}});
 click(1);assert(classes.has('generate-mode'));assert(classes.has('mode-transitioning'));assert(reference.inert);assert.equal(cancelled,2);assert.equal(delay,reduced?0:260);assert.equal(workspace.style['--reference-content-width'],narrow?'952px':'440px');
 click(0);assert(!classes.has('generate-mode'));assert(classes.has('mode-transitioning'));assert(!reference.inert);assert.equal(reference['aria-hidden'],'false');timer();assert(!classes.has('mode-transitioning'));assert.equal(refreshed,1);
}
assert(source.includes("if(referenceLayoutBusy(el))return;"));
assert(source.includes("|| referenceLayoutBusy(el))return;"));
console.log('PASS: four viewport/motion combinations, cancellation, rapid reversal, stable width, cleanup, inert state and child guards');
