const fs=require('fs'),vm=require('vm'),assert=require('assert');
let writes=0,callback,frames=[];const dialogs=[],headers={},hosts={},triggers={};
function node(){return {attrs:{},dataset:{},isConnected:true,getAttribute(k){return this.attrs[k]??null},setAttribute(k,v){writes++;this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]},addEventListener(k,f){this.listener=f},focus(){this.focused=true}}}
for(const kind of ['api','settings']){const h=headers[kind]=node();h.open=false;h.classList={contains:()=>h.open};h.click=()=>{h.open=!h.open};const host=hosts[kind]=node();host.append=d=>{host.child=d};const t=triggers[kind]=node();t.textContent=kind==='api'?'Use via API':'Settings';t.closest=()=>null;t.click=()=>{t.clicks=(t.clicks||0)+1};}
const body={style:{overflow:'hidden'}};const document={body,getElementById(id){const kind=id.includes('-api-')?'api':'settings';return id.endsWith('-host')?hosts[kind]:{querySelector:()=>headers[kind]}},querySelectorAll(q){if(q==='button')return Object.values(triggers);return dialogs.filter(d=>d.getAttribute('role')==='dialog')}};
const window={};const ctx={document,window,MutationObserver:class{constructor(cb){callback=cb}observe(){}disconnect(){}},requestAnimationFrame:f=>{frames.push(f);return frames.length}};vm.runInNewContext('('+fs.readFileSync('inline-utilities.js','utf8')+')()',ctx);
const initial=writes;callback();callback();assert.equal(frames.length,1);frames.shift()();assert.equal(writes,initial,'idle refresh must not write attributes');
for(const kind of ['api','settings']){
 headers[kind].click();window.voiceStudioUtilities.open(kind);assert.equal(triggers[kind].clicks,1);
 const d=node(),close=node();d.attrs={role:'dialog','aria-label':kind==='api'?'Use via API':'Settings','aria-modal':'true'};d.querySelector=()=>close;dialogs.push(d);callback();frames.shift()();assert.strictEqual(hosts[kind].child,d);assert.equal(d.attrs.role,'region');assert(!('aria-modal' in d.attrs));assert.equal(body.style.overflow,'');
 window.voiceStudioUtilities.open(kind);assert.equal(triggers[kind].clicks,1,'opening existing native utility must not toggle it off');
 close.listener({preventDefault(){},stopImmediatePropagation(){}});assert.equal(headers[kind].open,false);assert(headers[kind].focused);assert(d.isConnected,'collapse preserves native content');
 headers[kind].click();d.isConnected=false;callback();frames.shift()();assert.equal(headers[kind].open,false,'native recorder close syncs accordion');
}
console.log('PASS inline utility native identity, independent mounting, retained collapse, native close sync, focus, idempotence and coalesced observer');
