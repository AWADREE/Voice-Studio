const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
function target(extra={}) {
  const handlers={};
  return Object.assign({dataset:{},value:'',hidden:false,disabled:false,isConnected:true,
    addEventListener(type,fn){(handlers[type]??=[]).push(fn);},
    dispatchEvent(e){e.target??=this;for(const fn of handlers[e.type]||[])fn(e);if(e.bubbles)this.parent?.dispatchEvent(e);},
    setAttribute(){},focus(){},reportValidity:()=>true},extra);
}
function editor(initial, options={}) {
  const shared=options.shared===null?null:target({value:options.shared ?? '42'});
  let rows=[],identity=0;
  const seedVisibilityAtInsertion=[];
  const list=target({querySelectorAll(){return rows.filter(row=>!row.dataset.removing);},appendChild(row){seedVisibilityAtInsertion.push(!row.querySelector('.clip-seed-controls').hidden);rows.push(row);},
    replaceChildren(){rows=[];},get children(){return rows;}}),add=target();
  const imports={};
  for(const key of ['.clip-source','.clip-split','.clip-confirm','.clip-import-status','.clip-undo','.clip-replace','.clip-cancel'])imports[key]=target();
  imports['.clip-confirm'].hidden=true;
  function makeRow(){
    const fields={};
    for(const key of ['[data-field="seed"]','[data-field="minutes"]','[data-field="seconds"]','textarea','.clip-reset-seed','.clip-new-seed','.clip-regenerate','.clip-remove','.clip-seed-controls','.clip-seed-note','.clip-operation-status'])fields[key]=target();
    const row=target({querySelector(s){return fields[s];},remove(){rows=rows.filter(r=>r!==row);}});
    Object.defineProperty(row,'innerHTML',{set(html){
      const opening=html.match(/<div\s+class="clip-seed-controls"[^>]*>/)?.[0];
      assert(opening,'Every rendered clip has its seed controls.');
      fields['.clip-seed-controls'].hidden=/\shidden(?:[\s=>])/.test(opening);
    }});
    for(const field of Object.values(fields))field.parent=row;
    return row;
  }
  const props={value:initial},window=target(),triggered=[];
  const context={window,props,trigger:(type,data)=>triggered.push({type,data}),Uint32Array,element:{querySelector:s=>s==='.clip-list'?list:add},
    document:{createElement:makeRow,querySelector:selector=>selector==='#generate-panel .shared-seed input'?shared:null,getElementById:id=>id==='clip-import'?{querySelector:s=>imports[s]}:null},
    crypto:{randomUUID:()=>String(++identity),getRandomValues:array=>{array[0]=123;return array;}},Event:class{constructor(type,options={}){this.type=type;Object.assign(this,options);}},
    requestAnimationFrame:fn=>fn(),matchMedia:()=>({matches:true})};
  vm.runInNewContext(fs.readFileSync('clip-seeds.js','utf8')+'\n'+(fs.existsSync('clip-timing.js')?fs.readFileSync('clip-timing.js','utf8'):'')+'\n'+fs.readFileSync('paragraph-timing.js','utf8')+'\n'+fs.readFileSync('clip-editor.js','utf8'),context);
  const click=el=>el.dispatchEvent({type:'click'});
  return {props,window,imports,triggered,shared,seedVisibilityAtInsertion,reset:index=>click(rows[index].querySelector('.clip-reset-seed')),regenerate:index=>click(rows[index].querySelector('.clip-regenerate')),get rows(){return rows;},add:()=>click(add),
    split(){imports['.clip-source'].value='A'.repeat(100)+'\n\nSecond';click(imports['.clip-split']);},
    cancel:()=>click(imports['.clip-cancel']),
    remove(index){click(rows[index].querySelector('.clip-remove'));},
    edit(index,seconds){const field=rows[index].querySelector('[data-field="seconds"]');field.value=String(seconds);field.dispatchEvent({type:'input',bubbles:true});},
    times:()=>Array.from(props.value,r=>[r.minutes,r.seconds])};
}
let e=editor([]);
e.add();assert.deepEqual(e.times(),[[0,1]],'the first manual row added to an empty list starts at 0:01');
e.add();assert.deepEqual(e.times(),[[0,1],[0,6]],'later manual rows advance five seconds');
e.edit(0,7);e.window.dispatchEvent({type:'voxover-batch'});e.add();
assert.deepEqual(e.times(),[[0,7],[0,6],[0,11]],'refreshing and adding cannot reset edited starts');
e.remove(0);assert.deepEqual(e.times(),[[0,6],[0,11]],'removing the first row cannot retime later rows');
e.remove(0);e.remove(0);e.add();assert.deepEqual(e.times(),[[0,1]],'a new first row starts at one second after all clips are removed');
e=editor([{minutes:0,seconds:1,text:''}]);e.split();
assert.equal(e.imports['.clip-confirm'].hidden,true,'a pristine first row does not need replacement confirmation');
assert.deepEqual(e.times(),[[0,1],[0,9]],'split timing retains character-based spacing');
e=editor([{minutes:0,seconds:1,text:''}]);e.edit(0,0);e.split();
assert.equal(e.imports['.clip-confirm'].hidden,false,'a manually changed start at zero still needs confirmation');
assert.deepEqual(e.times(),[[0,0]]);e.cancel();assert.deepEqual(e.times(),[[0,0]],'cancel preserves the edited zero start');
e=editor([{minutes:2,seconds:15,text:'Saved first'},{minutes:3,seconds:20,text:'Saved second'}]);
assert.deepEqual(e.times(),[[2,15],[3,20]],'mounting existing rows preserves their saved timestamps');
console.log('PASS first/manual defaults, later-row defaults, edited and saved timestamps, remove/re-add, pristine import, retimed-row confirmation and cancel');

// Timing confirmation acts on the live editor and cannot overwrite a newer draft.
e=editor([{id:'a',minutes:0,seconds:1,text:'A',seed:5},{id:'b',minutes:4,seconds:9,text:'B',seed:6}]);
assert.equal(typeof e.window.voxoverClipEditor.alignTimestamps,'function','editor timing action must exist');
let confirmation,busy=false,message='';
e.window.voxoverGenerationGuard={busy:()=>busy,position:()=>0,job:()=>null,confirmAction(options){confirmation=options;}};
e.window.voxoverBatchMetadata={version:'batch:0',timing:{clips:[{id:'a',text:'A',frames:24001,sample_rate:24000},{id:'b',text:'B',frames:24000,sample_rate:24000}]}};
const retime=()=>e.window.voxoverClipEditor.alignTimestamps({},text=>message=text);
retime();assert.deepEqual(e.times(),[[0,1],[4,9]],'open and cancel leave all timestamps unchanged');assert.match(confirmation.description,/first/);
confirmation.action();assert.equal(e.props.value[1].seconds,2+1/24000);assert.equal(e.props.value[1].seed,6);
e.edit(1,9);retime();e.edit(1,8);confirmation.action();assert.equal(e.props.value[1].seconds,8,'confirmation cannot overwrite subsequent edits');assert.match(message,/changed/);
retime();e.window.voxoverBatchMetadata.version='batch:1';confirmation.action();assert.equal(e.props.value[1].seconds,8,'regeneration invalidates pending timestamp confirmation');
retime();busy=true;confirmation.action();assert.equal(e.props.value[1].seconds,8,'queued generation invalidates pending timestamp confirmation');
confirmation=null;retime();assert.equal(confirmation,null,'timestamp alignment waits for active and queued generations');
console.log('PASS timestamp cancel, apply, seed preservation, edited-row/version races, and queued-generation lock');

// Every individual replacement, even another job queued behind an active one,
// must be confirmed before consuming seeds or dispatching work.
e=editor([{id:'a',minutes:0,seconds:1,text:'A',seed:5},{id:'b',minutes:4,seconds:9,text:'B',seed:6}]);
e.window.voxoverBatchMetadata={batch_id:'batch',ids:['a','b']};
const queued=[];confirmation=null;
e.window.voxoverGenerationGuard={pending:'a',position:id=>queued.findIndex(j=>j.id===id)+1,job:()=>null,confirmAction:o=>confirmation=o,enqueue:(id,run,data,valid)=>queued.push({id,run,data,valid})};
e.window.voxoverSeedRandomizer={enabled:true};
e.regenerate(1);assert(confirmation);assert.equal(queued.length,0);assert.equal(e.props.value[1].seed,6,'cancelling preserves even a randomized seed');
e.regenerate(1);confirmation.action();assert.equal(queued.length,1);assert.equal(queued[0].data.seed,6);assert.equal(e.rows[1].querySelector('[data-field="seed"]').dataset.seedReady,'false');assert.equal(e.triggered.length,0,'a queued confirmation does not immediately synthesize');
assert(queued[0].valid());queued[0].run();assert.equal(e.triggered.length,1);assert.equal(e.triggered[0].data.id,'b');
confirmation=null;e.regenerate(1);assert.equal(confirmation,null,'duplicate queued request is ignored');
queued.length=0;e.regenerate(1);e.window.voxoverBatchMetadata.batch_id='new';confirmation.action();assert.equal(queued.length,0,'new batch invalidates open regeneration confirmation');
console.log('PASS individual queued regeneration confirmation, cancel preserves seed/audio, duplicate and replaced-batch guards');

e=editor([{id:'new-a',minutes:0,seconds:1,text:'First new clip'},{id:'new-b',minutes:0,seconds:5,text:'Second new clip'}],{shared:null});
const firstJobs=[];confirmation=null;
e.window.voxoverGenerationGuard={pending:null,position:()=>0,job:()=>null,confirmAction:o=>confirmation=o,enqueue:(id,run,data,valid)=>firstJobs.push({id,run,data,valid})};
assert.equal(e.rows[0].querySelector('.clip-regenerate').textContent,'Generate');assert(!e.rows[0].querySelector('.clip-regenerate').hidden);
e.regenerate(0);assert.equal(confirmation,null,'first generation never asks to replace nonexistent audio');assert.equal(firstJobs.length,1);assert.equal(firstJobs[0].data.seed,undefined,'new clip inherits server shared seed even with settings unmounted');firstJobs[0].run();
const draft=e.triggered[0].data.draft_id;assert(draft);assert.equal(e.triggered[0].data.batch_id,null);assert(!('seed' in e.triggered[0].data));
e.regenerate(1);const queuedFirst=firstJobs[1];assert(queuedFirst.valid());
e.window.voxoverBatchMetadata={batch_id:'created',origin_draft_id:draft,ids:['new-a']};assert(queuedFirst.valid(),'first-time queued clips continue in the batch created by this draft');
e.window.voxoverBatchMetadata={batch_id:'unrelated',ids:['other']};assert(!queuedFirst.valid(),'full batch replacement cannot absorb an old first-time request');
e.window.dispatchEvent({type:'voxover-clip-result',detail:{id:'new-b',status:'Generation failed: choose a valid .pt voice.'}});
assert.equal(e.rows[1].querySelector('.clip-operation-status').textContent,'Generation failed: choose a valid .pt voice.');
console.log('PASS standalone Generate, shared seed inheritance, draft queue continuity, replacement rejection, row-local error');

// Manual rows inherit the current shared seed, but randomize allocates distinct drafts.
e=editor([{id:'last',minutes:2,seconds:58,text:'Previous'}]);
e.add();assert.deepEqual(e.times(),[[2,58],[3,3]]);
assert.equal(e.props.value[1].seed,42);assert.equal(e.rows[1].querySelector('.clip-seed-controls').hidden,false);
e.edit(1,57);e.add();assert.deepEqual(e.times(),[[2,58],[3,57],[4,2]]);
e.window.voxoverSeedRandomizer={enabled:true};e.add();
assert.notEqual(e.props.value[3].seed,42);assert.equal(e.rows[3].querySelector('.clip-seed-controls').hidden,false);
console.log('PASS manual seed visibility/inheritance/randomize and edited preceding timestamp rollover');

// Completed streaming rows can queue; unfinished rows and pre-start metadata cannot.
e=editor([{id:'done',minutes:0,seconds:1,text:'Done',seed:5},{id:'waiting',minutes:0,seconds:6,text:'Waiting',seed:6}]);
let streaming=false;const streamJobs=[];
e.window.voxoverBatchMetadata={batch_id:'stream',streaming:true,ids:['done'],pending_ids:['waiting']};
e.window.voxoverGenerationGuard={pending:'full',streaming:()=>streaming,canEnqueue:id=>streaming&&id!=='waiting',position:()=>0,job:()=>null,confirmAction:o=>confirmation=o,enqueue:(id,run,data,valid)=>streamJobs.push({id,run,data,valid})};
confirmation=null;e.regenerate(0);assert.equal(confirmation,null);
streaming=true;e.window.dispatchEvent({type:'voxover-batch'});
assert.equal(e.rows[0].querySelector('.clip-regenerate').disabled,false);
assert.equal(e.rows[1].querySelector('.clip-regenerate').disabled,true);
assert.equal(e.rows[0].querySelector('.clip-remove').disabled,false);
assert.equal(e.rows[1].querySelector('.clip-remove').disabled,true);
e.regenerate(0);confirmation.action();assert.equal(streamJobs.length,1);assert.equal(streamJobs[0].data.batch_id,'stream');
e.regenerate(1);assert.equal(streamJobs.length,1);assert.equal(e.triggered.length,0);
console.log('PASS streaming row eligibility, guarded pre-start, removal lock and captured batch identity');

// Seed controls are visible at insertion, before generation-state refresh runs.
e=editor([{id:'initial',minutes:0,seconds:1,text:''}]);
assert.deepEqual(e.seedVisibilityAtInsertion,[true],'Initial seed and New seed controls must be visible on their first render.');
e.add();assert(e.seedVisibilityAtInsertion.every(Boolean),'Added clip seeds are visible before any Randomize or generation event.');
e=editor([{id:'initial',minutes:0,seconds:1,text:''}]);e.split();
assert.equal(e.seedVisibilityAtInsertion.length,3);
assert(e.seedVisibilityAtInsertion.every(Boolean),'Every split clip exposes seed controls immediately.');
const visibleSeeds=()=>e.rows.every(row=>!row.querySelector('.clip-seed-controls').hidden);
assert(visibleSeeds());
e.window.voxoverSeedRandomizer={enabled:true};e.window.dispatchEvent({type:'voxover-randomize'});assert(visibleSeeds());
e.window.voxoverSeedRandomizer.enabled=false;e.window.dispatchEvent({type:'voxover-randomize'});assert(visibleSeeds());
const clipId=e.rows[0].dataset.clipId;
e.window.voxoverGenerationGuard={pending:clipId,busy:()=>true,position:()=>0,job:()=>({seed:123})};
e.window.dispatchEvent({type:'voxover-operation'});assert(visibleSeeds(),'Active generation does not hide seed controls.');
assert(e.rows[0].querySelector('[data-field="seed"]').readOnly,'Active seed keeps its existing read-only protection.');
e.window.voxoverGenerationGuard.pending=null;
e.window.voxoverBatchMetadata={ids:[clipId],seeds:{[clipId]:123}};
e.window.dispatchEvent({type:'voxover-batch'});assert(visibleSeeds(),'Generated clips retain visible seed controls.');
console.log('PASS seed controls visible immediately for initial, added, split, Randomize on/off, active and completed clips');

// New drafts copy the current main seed without replacing saved/manual drafts.
e=editor([{id:'default',minutes:0,seconds:1,text:''}],{shared:'73'});
assert.equal(Number(e.rows[0].querySelector('[data-field="seed"]').value),73,'Initial clips display the current main seed.');
assert.equal(e.props.value[0].seed,73,'The displayed default is captured in the generation draft.');
e.shared.value='84';e.add();
assert.deepEqual(Array.from(e.props.value,r=>r.seed),[73,84],'New clips use the latest main seed without rewriting existing overrides.');
e.reset(0);assert.equal(e.props.value[0].seed,84,'Reset copies the current main seed.');
e.shared.value='-1';e.reset(0);assert.equal(e.props.value[0].seed,-1,'Reset preserves the supported random sentinel.');
for(const invalid of ['', '-2', '1.5', '9007199254740992']){
  e.shared.value=invalid;e.reset(0);assert.equal(e.props.value[0].seed,-1,'Invalid main seeds cannot destroy the current clip draft.');
  assert.equal(e.rows[0].querySelector('.clip-operation-status').hidden,false);
}
e.shared.value='0';e.reset(0);assert.equal(e.props.value[0].seed,0,'Zero is a valid reset seed.');
assert.equal(e.rows[0].querySelector('.clip-operation-status').hidden,true);
e=editor([{id:'saved',minutes:0,seconds:1,text:'',seed:999}],{shared:'73'});
assert.equal(e.props.value[0].seed,999,'Restored explicit seeds are never defaulted again.');
e=editor([{id:'pristine',minutes:0,seconds:1,text:''}],{shared:'85'});e.split();
assert.deepEqual(Array.from(e.props.value,r=>r.seed),[85,85],'Every split clip starts from the current main seed.');
e=editor([{id:'delayed',minutes:0,seconds:1,text:''}],{shared:''});
assert(!('seed' in e.props.value[0]));e.shared.value='86';e.window.dispatchEvent({type:'voxover-randomize'});
assert.equal(e.props.value[0].seed,86,'Late main input mounting initializes untouched drafts.');
console.log('PASS main-seed defaults for initial/added/split/late rows, preserved saved drafts, current-value reset and invalid/zero/random bounds');
