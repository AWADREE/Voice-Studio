const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('night-sky.js','utf8');
const code=source.slice(source.indexOf('    const referenceLayoutBusy'),source.indexOf('  const drawerAnimations='));
let geometry=120,parentHeight=120,ownDisplay='block';const animations=[];
const el={isConnected:true,dataset:{},inert:false,
 parentElement:{closest(){return null},getBoundingClientRect(){return {height:parentHeight}}},
 closest(selector){return selector==='#reference-panel'?{}:null},
 matches(){return false},getBoundingClientRect(){return {height:geometry}},
 style:{setProperty(){},removeProperty(){}},
 animate(frames){const animation={frames,playState:'running'};animations.push(animation);return animation;}};
const context={document:{querySelectorAll(){return [el]},querySelector(){return {matches(){return false}}},addEventListener(){}},
 getComputedStyle(){return {display:ownDisplay,opacity:'1'}},
 matchMedia(){return {matches:false}},requestAnimationFrame(){}};
vm.createContext(context);vm.runInContext(code,context);
vm.runInContext('animatePresence()',context);
geometry=0;parentHeight=0;vm.runInContext('animatePresence()',context);
geometry=120;parentHeight=120;vm.runInContext('animatePresence()',context);
assert.equal(animations.length,0,'an ancestor mode switch must not toggle the transcript itself');
ownDisplay='none';geometry=0;vm.runInContext('animatePresence()',context);
assert.equal(animations.length,1,'turning off Include reference transcript still animates its exit');
assert.equal(animations[0].frames[1].height,'0px');
animations[0].onfinish();
ownDisplay='block';geometry=120;vm.runInContext('animatePresence()',context);
assert.equal(animations.length,2,'turning the transcript back on still animates its entrance');
assert.equal(animations[1].frames[0].height,'0px');
console.log('PASS transcript visibility follows its own toggle, not hidden workflow geometry');
