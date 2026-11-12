const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
function target(extra={}){
 const handlers={};
 return Object.assign({dataset:{},value:'',hidden:false,disabled:false,isConnected:true,
  addEventListener(type,fn){(handlers[type]??=[]).push(fn);},
  dispatchEvent(e){e.target??=this;for(const fn of handlers[e.type]||[])fn(e);if(e.bubbles)this.parent?.dispatchEvent(e);},
  setAttribute(){},reportValidity(){return true;},focus(){},classList:{toggle(){}}},extra);
}
const rows=[],list=target({querySelectorAll(){return rows;},appendChild(row){rows.push(row);},get children(){return rows;}}),add=target();
function makeRow(){
 const fields={};
 for(const selector of ['[data-field="seed"]','[data-field="minutes"]','[data-field="seconds"]','textarea','.clip-reset-seed','.clip-new-seed','.clip-regenerate','.clip-remove','.clip-seed-controls','.clip-seed-note','.clip-operation-status']) fields[selector]=target();
 const row=target({querySelector(s){return fields[s];}});for(const item of Object.values(fields))item.parent=row;
 return row;
}
const singleSeed=target(),singleNew=target(),singleControls=target(),checkbox=target({checked:false});
const shared=target({value:'42',closest(){return {classList:{toggle(){}}};}});
const single=target({querySelector(s){return s==='[data-field="seed"]'?singleSeed:s==='.clip-new-seed'?singleNew:singleControls;}});
const panel={querySelector(s){return s.includes('checkbox')?checkbox:shared;}};
const element={querySelector(s){return s==='.clip-list'?list:add;}};
const window=target();
const document={querySelector:()=>shared,createElement:makeRow,getElementById(id){return id==='generate-panel'?panel:id==='single-clip-seed'?single:null;}};
let random=7;
const props={value:[{id:'one',minutes:0,seconds:0,text:'First'},{id:'two',minutes:0,seconds:1,text:'Second'}]};
const events=[];
const context={window,document,element,props,Uint32Array,crypto:{getRandomValues(a){a[0]=random;return a;},randomUUID(){return 'id'+rows.length;}},
 Event:class{constructor(type,options={}){this.type=type;Object.assign(this,options);}},requestAnimationFrame:fn=>fn(),
 MutationObserver:class{observe(){}},trigger:(type,data)=>events.push({type,data}),matchMedia:()=>({matches:true})};
vm.createContext(context);
const helpers=fs.readFileSync('clip-seeds.js','utf8');
vm.runInContext(helpers+'\n'+fs.readFileSync('clip-editor.js','utf8'),context);
vm.runInContext('('+fs.readFileSync('seed-randomizer.js','utf8').replace('// SEED_HELPERS',helpers)+')()',context);
const api=window.voxoverSeedRandomizer;
const seed=i=>rows[i].querySelector('[data-field="seed"]');
const click=el=>el.dispatchEvent({type:'click'});
const toggle=checked=>{checkbox.checked=checked;checkbox.dispatchEvent({type:'change'});};
const edit=(input,value)=>{input.value=String(value);input.dispatchEvent({type:'input',bubbles:true});};
const batch=()=>api.prepare(['generate','batch',props.value,...Array(9).fill(null),42]);
const take=(workflow='generate')=>api.prepare([workflow,'single',props.value,...Array(9).fill(null),42]);
assert(!shared.disabled);assert(singleControls.hidden);assert(rows.every(r=>!r.querySelector('.clip-seed-controls').hidden),'draft seed controls stay available before generation');
toggle(true);
assert(shared.disabled);assert.equal(shared.value,'42');assert(!singleControls.hidden);
assert(rows.every(r=>!r.querySelector('.clip-seed-controls').hidden));
assert(rows.every((_,i)=>Number(seed(i).value)!==42),'Enabling Randomize replaces untouched main-seed defaults.');
let shown=rows.map((_,i)=>Number(seed(i).value));assert.equal(new Set(shown).size,2);
assert(rows.every(r=>!r.querySelector('.clip-regenerate').hidden && r.querySelector('.clip-regenerate').textContent==='Generate'),'new clips can be generated individually');
let request=batch();assert.deepEqual(Array.from(request[2],r=>r.seed),shown,'first request uses exactly displayed seeds');
let repeated=batch();let next=Array.from(repeated[2],r=>r.seed);assert(next.every((v,i)=>v!==shown[i]));assert.equal(new Set(next).size,2);
edit(seed(0),123);request=batch();assert.equal(request[2][0].seed,123,'explicit next take must win');
edit(seed(0),456);
window.voxoverBatchMetadata={batch_id:'batch',ids:['one','two'],seeds:{one:123,two:7}};
window.dispatchEvent({type:'voxover-batch'});assert.equal(seed(0).value,'456','late results cannot overwrite drafts');
request=batch();assert.equal(request[2][0].seed,456);
click(rows[0].querySelector('.clip-new-seed'));const newSeed=Number(seed(0).value);request=batch();assert.equal(request[2][0].seed,newSeed);
// The real queue's FIFO/cancellation behavior is covered by test_generation_guard.cjs.
let captured,run;
window.voxoverGenerationGuard={pending:null,position:()=>0,job:()=>captured,confirmAction:options=>options.action(),enqueue(id,fn,data){captured=data;run=fn;return true;}};
click(rows[0].querySelector('.clip-regenerate'));const queued=captured.seed;
click(rows[0].querySelector('.clip-new-seed'));const future=Number(seed(0).value);assert.notEqual(future,queued);
run();assert.equal(events.at(-1).data.seed,queued,'queued seed must not follow draft changes');
window.dispatchEvent({type:'voxover-batch'});assert.equal(Number(seed(0).value),future);
// Reset prepares a future take and never rewrites the already accepted job.
shared.value='96';click(rows[0].querySelector('.clip-reset-seed'));
assert.equal(Number(seed(0).value),96);assert.equal(captured.seed,queued);
run();assert.equal(events.at(-1).data.seed,queued,'Reset cannot change a queued snapshot.');
window.dispatchEvent({type:'voxover-batch'});assert.equal(Number(seed(0).value),96,'Late generated seeds cannot overwrite Reset.');
window.voxoverGenerationGuard.pending='one';
window.dispatchEvent({type:'voxover-operation'});assert(seed(0).readOnly);
shared.value='97';click(rows[0].querySelector('.clip-reset-seed'));
assert.equal(Number(seed(0).value),97,'Reset during active generation prepares only the future draft.');
assert.equal(captured.seed,queued);
window.voxoverGenerationGuard=null;
request=batch();assert.equal(request[2][0].seed,97,'Reset wins for the next randomized take.');
assert.notEqual(batch()[2][0].seed,97,'The following take randomizes again.');
shared.value='42';
const firstSingle=Number(singleSeed.value);assert.equal(take()[12],firstSingle);assert.notEqual(take()[12],firstSingle);
edit(singleSeed,321);assert.equal(take('design')[12],321);assert.notEqual(take('clone')[12],321);
click(singleNew);const prepared=Number(singleSeed.value);assert.equal(take()[12],prepared);
edit(singleSeed,-1);assert(take()[12]>=0,'Randomize must resolve -1 to an inspectable numeric seed');
edit(seed(0),808);toggle(false);assert(!shared.disabled);assert.equal(shared.value,'42');assert(singleControls.hidden);
assert(rows.every(r=>!r.querySelector('.clip-seed-controls').hidden),'fixed overrides remain visible after Randomize is switched off');
request=batch();assert.equal(request[2][0].seed,808);assert.equal(take()[12],42,'Randomize off restores shared seed for singles');
const offSeeds=Array.from(request[2],r=>r.seed);assert.deepEqual(Array.from(batch()[2],r=>r.seed),offSeeds,'off does not randomize batch overrides');
click(add);assert.equal(props.value.length,3);assert.equal(props.value[2].seed,42,'new off-mode clip displays its inherited shared seed');
edit(seed(0),999);toggle(true);assert.equal(Number(seed(0).value),999,'enabling preserves manual draft');assert('seed' in props.value[2]);
assert(!rows[2].querySelector('.clip-seed-controls').hidden);
random=4294967295;assert.equal(vm.runInContext('newClipSeed(4294967295,[0,1])',context),2);
edit(singleSeed,'');assert.equal(take()[12],'','invalid edit reaches normal server failure cleanup');
console.log('PASS Randomize UI and exact snapshot: initial/repeat single, Clone, Design, distinct batches, explicit edits, New seed, late response, queued capture, toggle off/on, added rows, collision, invalid draft');

// Gradio can mount Number/Checkbox modules after app.load callbacks.
let deferred, disconnected=false, ready=false;
const delayedWindow=target();
const delayedPanel={querySelector(selector){return ready?panel.querySelector(selector):null;}};
const delayedContext={...context,window:delayedWindow,
 document:{...document,getElementById(id){return id==='generate-panel'?delayedPanel:document.getElementById(id);}},
 MutationObserver:class{constructor(fn){deferred=fn;}observe(){}disconnect(){disconnected=true;}}};
vm.runInNewContext('('+fs.readFileSync('seed-randomizer.js','utf8').replace('// SEED_HELPERS',helpers)+')()',delayedContext);
assert.equal(delayedWindow.voxoverSeedRandomizer,undefined,'do not publish a partially mounted API');
ready=true;deferred();assert(delayedWindow.voxoverSeedRandomizer);assert(disconnected);
console.log('PASS deferred Gradio module mount and one-time listener initialization');
