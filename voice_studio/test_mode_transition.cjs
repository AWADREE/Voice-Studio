const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('night-sky.js','utf8');
new Function('return '+source);
const handler=source.slice(source.indexOf('const modeNav ='),source.indexOf('if (window.__qwenSkyCleanup)'));
for(const narrow of [false,true])for(const reduced of [false,true]){
 const classes=new Set();let viewportNarrow=narrow,timer,delay,pickerCancels=0,refreshed=0,listener;
 const animations=[];
 const animate=(owner,frames,options)=>{const a={owner,frames,options,cancelled:false,cancel(){this.cancelled=true}};animations.push(a);return a};
 const buttons=['clone','design','generate'].map(mode=>({dataset:{voiceMode:mode},setAttribute(k,v){this[k]=v;}}));
 const nav={dataset:{},addEventListener(t,f){listener=f},querySelectorAll(){return buttons}};
 const picker={};const cache=new WeakMap([[picker,{animation:{cancel(){pickerCancels++}},bodyAnimation:{cancel(){pickerCancels++}}}]]);
 const style=()=>{const values={};return {values,setProperty(k,v){values[k]=v},removeProperty(k){delete values[k]},get height(){return values.height},set height(v){values.height=v}}};
 const clone={id:'clone',style:style(),inert:false,value:'Preserved transcript',getBoundingClientRect(){return {width:viewportNarrow?958:438}},animate(frames,options){return animate(this.id,frames,options)}};
 const design={id:'design',style:style(),inert:false,value:'Gentle alto',getBoundingClientRect(){return {width:viewportNarrow?958:438}},animate(frames,options){return animate(this.id,frames,options)}};
 const delivery={id:'delivery',style:style(),inert:false,value:'Preserved delivery',parentElement:{},getBoundingClientRect(){return {height:classes.has('design-mode')&&!this.style.values.display?0:95}},animate(frames,options){return animate(this.id,frames,options)}};
 const workspace={clientWidth:1000,classList:{contains:n=>classes.has(n),add:n=>classes.add(n),remove:n=>classes.delete(n),toggle(n,v){v?classes.add(n):classes.delete(n)}},style:style(),dispatchEvent(){}};
 const reference={style:style(),inert:false,getBoundingClientRect(){return {height:this.style.height&&this.style.height!=='auto'?parseFloat(this.style.height):classes.has('design-mode')?250:600}},animate(frames,options){return animate('panel',frames,options)},querySelectorAll(){return[picker]},setAttribute(k,v){this[k]=v}};
 reference.nextElementSibling={id:'shared-panel'};
 const workflow={value:'clone',dispatchEvent(){}};
 const sharedText={value:'Keep this commentary'};
 vm.runInNewContext(handler,{document:{querySelector:s=>s==='#voice-mode-tabs'?nav:s==='#voice-mode-workspace'?workspace:s==='#reference-panel'?reference:s==='#clone-inputs'?clone:s==='#design-inputs'?design:s==='#base-delivery-instruction'?delivery:s.startsWith('#workflow-mode')?workflow:null},Event:class{},getComputedStyle:e=>({opacity:animations.length>=4&&e===clone?'0.6':animations.length>=4&&e===design?'0.4':'1',transform:animations.length>=4&&(e===clone||e===design)?'matrix(1, 0, 0, 1, 0, 5)':'none',paddingTop:'24px',paddingBottom:'24px',paddingLeft:e===reference&&classes.has('generate-mode')?'0px':viewportNarrow?'20px':'24px',paddingRight:e===reference&&classes.has('generate-mode')?'0px':viewportNarrow?'20px':'24px',borderLeftWidth:e===reference&&classes.has('generate-mode')?'0px':'1px',borderRightWidth:e===reference&&classes.has('generate-mode')?'0px':'1px',rowGap:'20px',marginBottom:animations.length>=4&&e===delivery?'-10px':'0px'}),matchMedia:q=>({matches:q.includes('800')?viewportNarrow:reduced}),pickerGeometry:cache,setTimeout(f,d){timer=f;delay=d;return 1},clearTimeout(){},requestAnimationFrame:f=>f(),animatePickerGeometry(){refreshed++}});
 const click=i=>listener({target:{closest:()=>buttons[i]}});
 click(1);
 assert(classes.has('design-mode'));assert(!reference.inert);assert.equal(workflow.value,'design');
 if(!reduced){
  assert.deepEqual(animations.map(a=>a.owner),['delivery','panel','clone','design']);
  assert.equal(animations[0].frames[0].height,'95px');assert.equal(animations[0].frames[1].height,'0px');assert.equal(animations[0].frames[1].marginBottom,'-20px');
  assert.equal(animations[1].frames[0].height,'600px');assert.equal(animations[1].frames[1].height,'250px');
  assert.equal(clone.style.values.display,'flex');assert.equal(clone.style.values.position,'absolute');assert(clone.inert);
  assert.equal(clone.style.values.width,viewportNarrow?'958px':'438px','outgoing Clone fields keep their measured width');
  assert.equal(animations[3].frames[0].opacity,0);
  click(0);assert(animations.slice(0,4).every(a=>a.cancelled),'rapid reversal cancels old motion');
  assert.deepEqual(animations.slice(4).map(a=>a.owner),['delivery','panel','design','clone']);
  assert.equal(clone.style.values.width,undefined,'rapid reversal clears the old absolute width');
  assert.equal(design.style.values.width,viewportNarrow?'958px':'438px');
  assert.equal(animations[4].frames[0].marginBottom,'-10px');
  assert.equal(animations[7].frames[0].opacity,0.6);assert.equal(animations[7].frames[0].transform,'matrix(1, 0, 0, 1, 0, 5)');
  animations[4].onfinish();animations[5].onfinish();assert.equal(reference.style.height,undefined);assert.equal(design.style.values.display,undefined);assert.equal(design.style.values.width,undefined);assert(!design.inert);
  click(1);animations[8].onfinish();animations[9].onfinish();
 }else{
  assert.equal(animations.length,0);assert.equal(reference.style.height,undefined);assert.equal(clone.style.values.display,undefined);
 }
 const deliveryBeforeGenerate=animations.filter(a=>a.owner==='delivery').length;
 click(2);assert(classes.has('generate-mode'));assert(!classes.has('design-mode'));assert(classes.has('mode-transitioning'));assert(reference.inert);assert.equal(pickerCancels,2);assert.equal(delay,reduced?0:260);assert.equal(workspace.style.values['--reference-content-width'],narrow?'958px':'438px');assert.equal(workflow.value,'generate');
 assert.equal(animations.filter(a=>a.owner==='delivery').length,deliveryBeforeGenerate+(reduced?0:1),'Design to Generate reveals the exact delivery field');
 if(!reduced){const a=animations.filter(a=>a.owner==='delivery').at(-1);assert.equal(a.frames[0].height,'0px');assert.equal(a.frames[1].height,'95px');}
 click(0);assert(!classes.has('generate-mode'));assert(classes.has('mode-transitioning'));assert(!reference.inert);assert.equal(reference['aria-hidden'],'false');timer();assert(!classes.has('mode-transitioning'));assert.equal(refreshed,1);assert.equal(workflow.value,'clone');assert.equal(sharedText.value,'Keep this commentary');assert.equal(clone.value,'Preserved transcript');assert.equal(design.value,'Gentle alto');assert.equal(delivery.value,'Preserved delivery');
 const deliveryBeforeUnchanged=animations.filter(a=>a.owner==='delivery').length;
 click(2);assert.equal(animations.filter(a=>a.owner==='delivery').length,deliveryBeforeUnchanged,'Clone to Generate keeps the shared delivery field');
 click(1);assert.equal(animations.filter(a=>a.owner==='delivery').length,deliveryBeforeUnchanged+(reduced?0:1),'Generate to Design hides the exact delivery field');
 if(!reduced){const a=animations.filter(a=>a.owner==='delivery').at(-1);assert.equal(a.frames[1].height,'0px');assert.equal(a.frames[1].marginBottom,'-20px');}
 click(2);viewportNarrow=!narrow;click(0);
 assert.equal(workspace.style.values['--reference-content-width'],viewportNarrow?'958px':'438px','Generate to Clone must use current viewport padding after a resize');
}
assert(source.includes('|| referenceLayoutBusy(el))return;'));
const css=fs.readFileSync('theme.css','utf8');
assert(css.includes('.studio-panel .form>.block:not(#base-delivery-instruction){margin:0!important}#base-delivery-instruction{margin:0}'),'the Delivery field must allow its gap margin to animate');
console.log('PASS: Clone/Design entrance, exit and height motion, rapid reversal, reduced motion, both viewports and preserved inputs');
