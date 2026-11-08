const fs=require('fs'),vm=require('vm'),assert=require('assert');let mutation,nodes=[],clicks=[];
function player(name,time=7){
  const handlers=new Set();
  const media={currentSrc:'blob:fixture-'+name,readyState:4,getAttribute:()=>null,querySelector:()=>null,currentTime:time,paused:true,addEventListener:(event,f)=>handlers.add(f),removeEventListener:(event,f)=>handlers.delete(f),pause(){this.paused=true},play(){this.paused=false;clicks.push([name,this.currentTime]);return Promise.resolve()},end(){this.paused=true;for(const f of [...handlers])f()}};
  const dummy={currentSrc:'',readyState:0,getAttribute:()=>null,querySelector:()=>null,currentTime:0,paused:true,pause(){this.paused=true},play(){throw Error('Unsourced placeholder must never play')}};
  const shadow={querySelectorAll:selector=>selector==='audio'?[media]:[]};
  return {name,media,dummy,querySelectorAll:selector=>selector==='audio'?[dummy]:[{shadowRoot:shadow}]};
}
const root={isConnected:true};const window={};const document={querySelectorAll:()=>nodes,getElementById:id=>id==='batch-output'?root:{}};
vm.runInNewContext('('+fs.readFileSync('batch-playback.js','utf8')+')()',{window,document,getComputedStyle:()=>({display:'block'}),MutationObserver:class{constructor(f){mutation=f}observe(){}}});
const api=window.voiceStudioBatchPlayback;
// Real Gradio coexistence: empty direct placeholder and ready blob audio in open shadow.
nodes=[player('old0'),player('old1',20)];api.play();assert.deepStrictEqual(clicks,[['old0',0]]);nodes[0].media.end();assert.deepStrictEqual(clicks,[['old0',0],['old1',0]]);api.finished(0);assert.equal(clicks.length,2,'late Gradio stop must not advance twice');nodes[1].media.end();assert(nodes.every(p=>p.media.paused));
api.play();const old=nodes[0];nodes=[player('new0'),player('new1')];mutation();assert(old.media.paused,'replacement stops old media');api.finished(0);old.media.end();assert.equal(clicks.length,3,'stale completion must not play replacement batch');
api.play();assert.deepStrictEqual(clicks.at(-1),['new0',0]);api.stop();nodes[0].media.end();assert.equal(clicks.length,4);api.play();root.isConnected=false;mutation();assert(nodes[0].media.paused);root.isConnected=true;nodes=[player('not-ready')];nodes[0].media.currentSrc='';api.play();assert(nodes[0].media.paused,'unsourced players must not start');
nodes[0].media.getAttribute=name=>name==='src'?'blob:loading':null;nodes[0].media.readyState=0;api.play();assert.deepStrictEqual(clicks.at(-1),['not-ready',0],'explicit src is usable before currentSrc metadata arrives');api.stop();
console.log('PASS Play all resets every clip, ordered native-ended progression, sourced shadow audio over dummy light-DOM placeholder, stop, detached root, replacement and stale completion');
