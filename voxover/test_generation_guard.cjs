const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let capture,hasBatch=false,hasSingle=false,multiple=true,submitted=0,stopped=0,focused=0,mutation,highlighted=null,scrolled=0;
const handlers={};
const element=()=>({textContent:'',addEventListener:(name,fn)=>{handlers[name]=fn;}});
const cancel=element(),confirm=element(),description=element();
const editor={inert:false};
const root={classList:{contains:()=>multiple},dispatchEvent(){}};
const dialog={open:false,setAttribute(){},querySelector:s=>s==='[data-cancel]'?cancel:s==='[data-confirm]'?confirm:description,
  addEventListener(name,fn){this[name]=fn;},showModal(){this.open=true;},close(){this.open=false;this.closeEvent?.();}};
dialog.addEventListener=(name,fn)=>{dialog[name==='close'?'closeEvent':name]=fn;};
function control(){const result={};return {addEventListener:(name,fn)=>result[name]=fn,result};}
const cancelControl=control(),confirmControl=control();
dialog.querySelector=s=>s==='[data-cancel]'?cancelControl:s==='[data-confirm]'?confirmControl:description;
const button={textContent:'Generate',disabled:false,focus(){focused++;},click(){const event=clickEvent();capture(event);if(!event.stopped)submitted++;}};
function clickEvent(){return {target:{closest:()=>button},stopped:false,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};}
const document={body:{appendChild(){}},createElement:()=>dialog,getElementById:id=>({'generate-commentary':button,'clip-editor':editor,'production-workspace':root,'listen-panel':{}}[id]),
  querySelector:s=>s.includes('.batch-audio')?hasBatch:s.includes('.studio-wav-output')?hasSingle:s==='.batch-clip-updated'?highlighted:null,
  addEventListener:(name,fn)=>{capture=fn;}};
const windowHandlers={};
const window={addEventListener:(name,fn)=>{windowHandlers[name]=fn;},dispatchEvent(event){windowHandlers[event.type]?.();},voxoverBatchPlayback:{stop(){stopped++;}}};
const context={window,document,Event:class{},MutationObserver:class{constructor(fn){mutation=fn;}observe(){}},matchMedia:()=>({matches:true})};
const code='('+fs.readFileSync('generation-guard.js','utf8')+')()';vm.runInNewContext(code,context);
const guard=window.voxoverGenerationGuard;
button.click();assert.equal(submitted,1);assert(!dialog.open);assert(guard.busy());assert(!editor.inert, "generation must not make the whole editor inert");assert.equal(stopped,1);
button.click();assert.equal(submitted,1,'double click cannot submit twice');
guard.finish();button.disabled=false;assert(!editor.inert);
hasBatch=true;button.click();assert(dialog.open);assert.equal(submitted,1);assert(!guard.busy());assert(!editor.inert);assert.match(description.textContent,/paragraph/);
cancelControl.result.click();assert(!dialog.open);assert.equal(submitted,1);assert(!guard.busy());assert.equal(stopped,1,'cancel must not stop existing audio');
button.click();confirmControl.result.click();assert.equal(submitted,2);assert(guard.busy());assert(!dialog.open);assert(!editor.inert, "generation must not make the whole editor inert");
guard.finish();button.disabled=false;guard.start('paragraph-id');assert.equal(stopped,2,'individual regeneration must preserve playing audio');button.click();assert.equal(submitted,2);assert.equal(guard.pending,'paragraph-id');assert(!editor.inert, "generation must not make the whole editor inert");
guard.finish();button.disabled=false;hasBatch=false;hasSingle=true;multiple=false;button.click();assert(dialog.open);assert(!description.textContent.includes('paragraph'));cancelControl.result.click();
vm.runInNewContext(code,context);assert.equal(window.voxoverGenerationGuard,guard,'reinitialization preserves the guard');
assert(focused>=2);
highlighted={id:'generated-clip-second',scrollIntoView(){scrolled++;}};mutation();assert.equal(scrolled,0);
window.voxoverBatchMetadata={version:'batch:1',highlight_id:'second'};
windowHandlers['voxover-batch']?.();assert.equal(scrolled,1,'metadata arriving after render must still reveal the replacement');
mutation();assert.equal(scrolled,1,'unrelated render must not repeatedly scroll');
const jobs=[];
assert(guard.enqueue('first',()=>jobs.push('first'),{seed:101}));
assert.equal(guard.pending,'first');assert.deepEqual(jobs,['first']);
assert(guard.enqueue('second',()=>jobs.push('second'),{seed:202}));
assert(guard.enqueue('third',()=>jobs.push('third'),{seed:303}));
assert(!guard.enqueue('second',()=>jobs.push('duplicate'),{seed:999}));
assert.equal(guard.position('second'),1);assert.equal(guard.position('third'),2);
assert.equal(guard.job('second').seed,202);assert.equal(jobs.length,1);
assert(!editor.inert);guard.finish();
assert.equal(guard.pending,'second');assert.deepEqual(jobs,['first','second']);
assert.equal(guard.position('third'),1);
guard.cancel('third');assert.equal(guard.position('third'),0);
guard.finish();assert(!guard.busy());assert.equal(jobs.length,2);
guard.start('full');assert(!guard.enqueue('fourth',()=>jobs.push('fourth')));guard.finish();
assert(guard.enqueue('removed',()=>jobs.push('removed'),{},()=>false));
assert(!guard.busy());assert.equal(jobs.length,2,'removed queued rows are skipped');
console.log('PASS serial FIFO, duplicate rejection, cancellation, captured seed, removed row skipping, unlocked full/clip editors; initial Generate, confirmation cancel/confirm, Single copy, duplicate click/regen guard, selective editor access, focus return, and idempotence');

assert.equal(typeof guard.confirmAction,'function','destructive per-clip and timestamp actions need confirmation');

let confirmations=0,originFocus=0;
const options={title:'Replace paragraph 2 audio?',description:'This replaces only paragraph 2.',confirmLabel:'Replace & regenerate',origin:{focus(){originFocus++;}},action:()=>confirmations++};
assert(guard.confirmAction(options));assert(dialog.open);assert.equal(confirmations,0);
assert(!guard.confirmAction({...options,action:()=>confirmations+=100}),'an open modal cannot be overwritten');
cancelControl.result.click();assert.equal(confirmations,0);assert.equal(originFocus,1);
guard.confirmAction(options);dialog.close();assert.equal(confirmations,0,'Escape/native dismissal has no action');
guard.confirmAction(options);confirmControl.result.click();assert.equal(confirmations,1);confirmControl.result.click();assert.equal(confirmations,1,'repeat confirmation cannot dispatch twice');
assert.equal(stopped,3,'only confirmed full generation can stop current playback');
console.log('PASS shared replacement modal cancel, Escape, focus return, duplicate open and duplicate confirm');

window.voxoverBatchMetadata={batch_id:'old',streaming:true,ids:['done'],pending_ids:['later']};
guard.start('full');assert(!guard.enqueue('done',()=>jobs.push('stale')),'stale pre-start metadata cannot enqueue');
window.voxoverBatchMetadata={batch_id:'new',streaming:true,ids:['done'],pending_ids:['later']};
assert(guard.enqueue('done',()=>jobs.push('stream-done'),{batch_id:'new'}));
assert(!guard.enqueue('later',()=>jobs.push('unfinished')));
assert(guard.enqueue('added',()=>jobs.push('stream-added'),{batch_id:'new'}));
assert(!guard.enqueue('done',()=>jobs.push('duplicate')));
assert.equal(guard.pending,'full');assert(!jobs.includes('stream-done'));
window.voxoverBatchMetadata={...window.voxoverBatchMetadata,streaming:false,pending_ids:[]};
assert.equal(guard.pending,'full','final metadata alone cannot release FIFO');
guard.finish();assert.equal(guard.pending,'done');assert.equal(jobs.at(-1),'stream-done');
guard.finish();assert.equal(guard.pending,'added');assert.equal(jobs.at(-1),'stream-added');guard.finish();
console.log('PASS fresh-stream-only FIFO, unfinished and duplicate rejection, final metadata holds until finish');
