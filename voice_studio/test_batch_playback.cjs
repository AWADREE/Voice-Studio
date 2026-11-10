const fs=require('fs'),vm=require('vm'),assert=require('assert');let mutation,nodes=[],clicks=[],rootDisplay='block',observed=[];
function player(name,time=7){
  const handlers=new Map();
  const media={emit(event){for(const f of [...(handlers.get(event)||[])])f()},currentSrc:'blob:fixture-'+name,readyState:4,getAttribute:()=>null,querySelector:()=>null,currentTime:time,paused:true,addEventListener:(event,f)=>{if(!handlers.has(event))handlers.set(event,new Set());handlers.get(event).add(f)},removeEventListener:(event,f)=>handlers.get(event)?.delete(f),pause(){this.paused=true;for(const f of handlers.get('pause')||[])f()},play(){this.paused=false;for(const f of handlers.get('play')||[])f();clicks.push([name,this.currentTime]);return Promise.resolve()},end(){this.paused=true;for(const f of [...(handlers.get('ended')||[])])f()}};
  const dummy={currentSrc:'',readyState:0,getAttribute:()=>null,querySelector:()=>null,currentTime:0,paused:true,pause(){this.paused=true},play(){throw Error('Unsourced placeholder must never play')}};
  const shadow={querySelectorAll:selector=>selector==='audio'?[media]:[]};
  return {name,media,dummy,querySelectorAll:selector=>selector==='audio'?[dummy]:[{shadowRoot:shadow}]};
}
const root={isConnected:true};const window={};const document={querySelectorAll:()=>nodes,getElementById:id=>id==='batch-output'?root:{}};
vm.runInNewContext('('+fs.readFileSync('batch-playback.js','utf8')+')()',{window,document,setTimeout:()=>1,clearTimeout(){},getComputedStyle:()=>({display:rootDisplay}),MutationObserver:class{constructor(f){mutation=f}observe(target,options){observed.push(options)}}});
const api=window.voxoverBatchPlayback;
// Real Gradio coexistence: empty direct placeholder and ready blob audio in open shadow.
nodes=[player('old0'),player('old1',20)];api.play();assert.deepStrictEqual(clicks,[['old0',0]]);nodes[0].media.end();assert.deepStrictEqual(clicks,[['old0',0],['old1',0]]);api.finished(0);assert.equal(clicks.length,2,'late Gradio stop must not advance twice');nodes[1].media.end();assert(nodes.every(p=>p.media.paused));
api.play();const old=nodes[0];nodes=[player('new0'),player('new1')];mutation();assert(old.media.paused,'replacement stops old media');api.finished(0);old.media.end();assert.equal(clicks.length,3,'stale completion must not play replacement batch');
api.play();assert.deepStrictEqual(clicks.at(-1),['new0',0]);api.stop();nodes[0].media.end();assert.equal(clicks.length,4);api.play();root.isConnected=false;mutation();assert(nodes[0].media.paused);root.isConnected=true;nodes=[player('not-ready')];nodes[0].media.currentSrc='';api.play();assert(nodes[0].media.paused,'unsourced players must not start');
nodes[0].media.getAttribute=name=>name==='src'?'blob:loading':null;nodes[0].media.readyState=0;api.play();assert.deepStrictEqual(clicks.at(-1),['not-ready',0],'explicit src is usable before currentSrc metadata arrives');api.stop();
console.log('PASS Play all resets every clip, ordered native-ended progression, sourced shadow audio over dummy light-DOM placeholder, stop, detached root, replacement and stale completion');

// CSS track order can differ from native render order after row removal/reorder.
nodes=[player('later'),player('first'),player('previous')];
[4,2,8].forEach((track,i)=>nodes[i].closest=()=>({style:{gridRow:String(track)}}));
api.play();assert.deepStrictEqual(clicks.at(-1),['first',0]);nodes[1].media.end();assert.deepStrictEqual(clicks.at(-1),['later',0]);nodes[0].media.end();assert.deepStrictEqual(clicks.at(-1),['previous',0]);api.stop();
console.log('PASS Play all follows visual shared-row order, with Previous clips last');

assert(observed.some(options=>options.attributes&&!options.subtree&&options.attributeFilter.includes('class')),'ancestor workflow class must be observed');
api.play();assert(!nodes[1].media.paused);rootDisplay='none';mutation();assert(nodes.every(p=>p.media.paused),'switching to Single/Clone/Design stops hidden Play all');rootDisplay='block';mutation();assert(nodes.every(p=>p.media.paused),'returning to Multiple does not unexpectedly resume playback');
console.log('PASS ancestor mode visibility stops playback and never auto-resumes');

// Disclosure visibility controls both sequencing and independent native audio.
const matched=player('matched'),matchedNext=player('matched-next'),previous=player('hidden-previous');
const matchedCard={hidden:false,style:{gridRow:'2'}},nextCard={hidden:false,style:{gridRow:'3'}},previousCard={hidden:true,style:{gridRow:'5'}};
matched.closest=()=>matchedCard;matchedNext.closest=()=>nextCard;previous.closest=()=>previousCard;
nodes=[previous,matchedNext,matched];api.play();assert.deepStrictEqual(clicks.at(-1),['matched',0]);
matched.media.end();assert.deepStrictEqual(clicks.at(-1),['matched-next',0]);
const beforeEnd=clicks.length;matchedNext.media.end();assert.equal(clicks.length,beforeEnd,'collapsed cards are excluded from Play all');
previousCard.hidden=false;api.play();previous.media.play();previousCard.hidden=true;mutation();
assert(previous.media.paused,'collapse pauses independently played orphan');assert(!matched.media.paused,'collapse preserves visible active batch audio');
matched.media.end();assert.deepStrictEqual(clicks.at(-1),['matched-next',0],'visible batch sequence continues after collapse');api.stop();
previousCard.hidden=false;api.play();matched.media.end();matchedNext.media.end();assert(!previous.media.paused);
matched.media.play();previousCard.hidden=true;mutation();assert(previous.media.paused,'collapse stops active batch orphan');assert(!matched.media.paused,'collapse does not stop independently playing matched audio');
const beforeStale=clicks.length;previous.media.end();assert.equal(clicks.length,beforeStale,'hidden completion cannot advance stale batch');
previousCard.hidden=false;mutation();assert(previous.media.paused,'expansion does not resume old audio');api.stop();
assert(observed.some(options=>options.attributeFilter.includes('hidden')),'observe disclosure hidden changes');
console.log('PASS collapsed players excluded, independent orphan paused, visible audio preserved, sequence repaired, and no unexpected resume');

// Repeated Play all is a new run from the first clip, not a disabled/busy action.
nodes=[player('restart-first'),player('restart-second')];api.play();nodes[0].media.end();assert(!nodes[1].media.paused);api.play();assert(nodes[1].media.paused);assert.deepStrictEqual(clicks.at(-1),['restart-first',0]);api.play();assert.deepStrictEqual(clicks.at(-1),['restart-first',0]);api.stop();
// A replacement keeps stable paragraph IDs: later replacements must not stop
// the current clip, and replacing the active clip resumes at its playhead.
const stableCard=(p,id)=>{p.closest=()=>({id,hidden:false,style:{gridRow:id==='a'?'2':'3'}});return p;};
nodes=[stableCard(player('stable-a'),'a'),stableCard(player('stable-b'),'b')];api.play();
const stableFirst=nodes[0];stableFirst.media.currentTime=3;
nodes[1]=stableCard(player('replaced-b'),'b');mutation();assert(!stableFirst.media.paused,'replacing another row must not stop Play all');
stableFirst.media.end();assert.deepStrictEqual(clicks.at(-1),['replaced-b',0]);
nodes[1].media.currentTime=2;nodes[1]=stableCard(player('new-active-b'),'b');mutation();assert.deepStrictEqual(clicks.at(-1),['new-active-b',2],'active replacement keeps its playhead');
api.stop();console.log('PASS same-ID replacement preserves active playback and selects latest remaining clips');
// Independent native playback survives a same-paragraph source remount too.
nodes=[stableCard(player('independent-old'),'a')];mutation();nodes[0].media.play();nodes[0].media.currentTime=4;
const independentlyPlaying=nodes[0];independentlyPlaying.isConnected=false;independentlyPlaying.media.isConnected=false;
nodes=[stableCard(player('independent-new'),'a')];mutation();assert.deepStrictEqual(clicks.at(-1),['independent-new',4]);assert(!nodes[0].media.paused);api.stop();
console.log('PASS independently playing clip carries playhead through replacement');

nodes=[stableCard(player('paused-old'),'a')];mutation();nodes[0].media.play();nodes[0].media.pause();nodes[0].isConnected=false;nodes[0].media.isConnected=false;
const beforePaused=clicks.length;nodes=[stableCard(player('paused-new'),'a')];mutation();assert.equal(clicks.length,beforePaused,'explicitly paused audio must not resume on replacement');
// A deliberate native Pause inside Play all must survive a source remount.
nodes=[stableCard(player('paused-playall-old'),'a')];api.play();nodes[0].media.currentTime=5;nodes[0].media.pause();nodes[0].isConnected=false;nodes[0].media.isConnected=false;
const pausedPlayallCalls=clicks.length;nodes=[stableCard(player('paused-playall-new'),'a')];mutation();assert.equal(clicks.length,pausedPlayallCalls);assert(nodes[0].media.paused);api.stop();
// Gradio can unmount a row before mounting its new native media in a later task.
nodes=[stableCard(player('remount-old-a'),'a'),stableCard(player('remount-old-b'),'b')];api.play();nodes[0].media.currentTime=6;
window.voxoverGenerationGuard={pending:'b'};nodes=[];mutation();nodes=[stableCard(player('remount-new-a'),'a'),stableCard(player('remount-new-b'),'b')];mutation();assert.deepStrictEqual(clicks.at(-1),['remount-new-a',6]);api.stop();window.voxoverGenerationGuard=null;
console.log('PASS explicit active Pause and transient Gradio remount');
// A shorter replacement must not advance a deliberately paused Play all run.
nodes=[stableCard(player('paused-long'),'a'),stableCard(player('paused-next'),'b')];api.play();nodes[0].media.currentTime=20;nodes[0].media.pause();nodes[0].isConnected=false;nodes[0].media.isConnected=false;
const short=stableCard(player('paused-short'),'a');short.media.duration=10;const beforeShort=clicks.length;nodes[0]=short;mutation();assert.equal(clicks.length,beforeShort);assert(short.media.paused);api.stop();

// WaveSurfer can reload a blob on the SAME connected media object. Its reset
// timeupdate/pause fire before the new blob URL becomes current.
nodes=[stableCard(player('reload-in-place'),'a'),stableCard(player('reload-next'),'b')];api.play();
const reloaded=nodes[0].media;reloaded.currentTime=12;reloaded.emit('timeupdate');
reloaded.readyState=0;reloaded.currentTime=0;reloaded.emit('timeupdate');reloaded.pause();reloaded.emit('emptied');reloaded.emit('loadstart');mutation();
reloaded.currentSrc='blob:new-source';reloaded.readyState=4;reloaded.emit('loadedmetadata');
assert(!reloaded.paused,'connected source-reset pause is not user Pause');assert.equal(reloaded.currentTime,12);api.stop();
nodes=[stableCard(player('native-reload'),'a')];mutation();const nativeReload=nodes[0].media;nativeReload.play();nativeReload.currentTime=8;nativeReload.emit('timeupdate');
nativeReload.readyState=0;nativeReload.currentTime=0;nativeReload.emit('timeupdate');nativeReload.pause();nativeReload.emit('emptied');nativeReload.currentSrc='blob:native-new';nativeReload.readyState=4;nativeReload.emit('loadedmetadata');
assert(!nativeReload.paused);assert.equal(nativeReload.currentTime,8);api.stop();
// A real Pause before reload remains an explicit pause.
nodes=[stableCard(player('paused-reload'),'a')];api.play();const pausedReload=nodes[0].media;pausedReload.currentTime=9;pausedReload.emit('timeupdate');pausedReload.pause();
pausedReload.readyState=0;pausedReload.currentTime=0;pausedReload.emit('timeupdate');pausedReload.emit('emptied');pausedReload.currentSrc='blob:paused-new';pausedReload.readyState=4;pausedReload.emit('loadedmetadata');assert(pausedReload.paused);assert.equal(pausedReload.currentTime,9);api.stop();
console.log('PASS same-node blob reload restores Play all/native offsets and respects explicit Pause');

// Stopping Play all must retain the independent native metadata subscription.
nodes=[stableCard(player('stop-then-native'),'a')];api.play();api.stop();const stoppedNative=nodes[0].media;stoppedNative.play();stoppedNative.currentTime=8;stoppedNative.emit('timeupdate');stoppedNative.readyState=0;stoppedNative.currentTime=0;stoppedNative.emit('timeupdate');stoppedNative.pause();stoppedNative.emit('emptied');stoppedNative.currentSrc='blob:after-stop';stoppedNative.readyState=4;stoppedNative.emit('loadedmetadata');assert(!stoppedNative.paused);assert.equal(stoppedNative.currentTime,8);api.stop();
// A stale rejected play promise cannot stop a newer binding on the same media.
nodes=[stableCard(player('rejected-old-play'),'a')];let rejectOld;const originalPlay=nodes[0].media.play;nodes[0].media.play=function(){originalPlay.call(this);return {catch(fn){rejectOld=fn;}}};api.play();nodes[0].media.play=originalPlay;nodes[0].media.currentTime=6;nodes[0].media.emit('timeupdate');nodes[0].media.readyState=0;nodes[0].media.emit('emptied');nodes[0].media.currentSrc='blob:latest-binding';nodes[0].media.readyState=4;nodes[0].media.emit('loadedmetadata');rejectOld();assert(!nodes[0].media.paused);api.stop();
console.log('PASS native listener ownership after Stop and stale same-node play rejection');

// Observed live WaveSurfer order: still readyState=4, paused time=0, then
// timeupdate/pause, and only afterward emptied/loadstart/new blob.
nodes=[stableCard(player('ready-reset'),'a')];api.play();const readyReset=nodes[0].media;readyReset.currentTime=15;readyReset.emit('timeupdate');readyReset.currentTime=0;readyReset.paused=true;readyReset.emit('timeupdate');readyReset.emit('pause');readyReset.emit('timeupdate');readyReset.readyState=0;readyReset.emit('emptied');readyReset.emit('loadstart');readyReset.currentSrc='blob:ready-reset';readyReset.readyState=4;readyReset.emit('loadedmetadata');assert(!readyReset.paused);assert.equal(readyReset.currentTime,15);api.stop();
nodes=[stableCard(player('native-ready-reset'),'a')];mutation();const nativeReady=nodes[0].media;nativeReady.play();nativeReady.currentTime=11;nativeReady.emit('timeupdate');nativeReady.currentTime=0;nativeReady.paused=true;nativeReady.emit('timeupdate');nativeReady.emit('pause');nativeReady.readyState=0;nativeReady.emit('emptied');nativeReady.currentSrc='blob:native-ready';nativeReady.readyState=4;nativeReady.emit('loadedmetadata');assert(!nativeReady.paused);assert.equal(nativeReady.currentTime,11);api.stop();
console.log('PASS observed readyState=4 reset-before-load ordering for sequential/native playback');

// WaveSurfer finalizes asynchronously AFTER metadata and resets again without
// another load event. Retain recovery intent until genuine media advancement.
nodes=[stableCard(player('decode-reset'),'a')];api.play();const decodeReset=nodes[0].media;decodeReset.currentTime=12;decodeReset.emit('timeupdate');decodeReset.readyState=0;decodeReset.currentTime=0;decodeReset.emit('timeupdate');decodeReset.pause();decodeReset.emit('emptied');decodeReset.currentSrc='blob:decode-new';decodeReset.readyState=4;decodeReset.emit('loadedmetadata');assert.equal(decodeReset.currentTime,12);
decodeReset.currentTime=0;decodeReset.paused=true;decodeReset.emit('timeupdate');decodeReset.emit('pause');mutation();assert.equal(decodeReset.currentTime,12);assert(!decodeReset.paused);api.stop();
// Stop cancels all source recovery, even between the zero reset and load event.
nodes=[stableCard(player('stop-reset'),'a')];api.play();const stopReset=nodes[0].media;stopReset.currentTime=12;stopReset.emit('timeupdate');stopReset.currentTime=0;stopReset.paused=true;stopReset.emit('timeupdate');stopReset.emit('pause');api.stop();stopReset.readyState=0;stopReset.emit('emptied');stopReset.currentSrc='blob:stopped-new';stopReset.readyState=4;stopReset.emit('loadedmetadata');assert(stopReset.paused);api.stop();
console.log('PASS post-metadata waveform reset and Stop during source replacement');
// Streamed full-batch output remains playable while new native cards arrive.
function withId(node,id){node.closest=()=>({id,hidden:false,style:{gridRow:'2'}});return node;}
window.voxoverGenerationGuard={pending:'full',streaming:()=>true};
nodes=[withId(player('stream-first'),'stream-a')];api.play();
const streamed=nodes[0];streamed.media.currentTime=3;streamed.media.emit('timeupdate');
nodes.push(withId(player('stream-second'),'stream-b'));mutation();
assert(!streamed.media.paused);assert.equal(streamed.media.currentTime,3);
streamed.media.end();assert.deepStrictEqual(clicks.at(-1),['stream-second',0]);
api.stop();const stoppedCount=clicks.length;
nodes.push(withId(player('stream-third'),'stream-c'));mutation();assert.equal(clicks.length,stoppedCount,'new streamed cards must never undo Stop');
console.log('PASS full-batch streamed playback, sequence extension, playhead retention and Stop preservation');
