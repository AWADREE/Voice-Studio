const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let mutation=null,frames=[],writes=0,rows=[],cards=[];
const listeners=new Map();
const style=()=>({setProperty(key,value){this[key]=value;}});
class Node {
 constructor(id=''){this.id=id;this.dataset={};this.style=style();this.children=[];this._text='';this.attributes={};this.events={};}
 set textContent(text){this._text=text;writes++;if(this.parent===host)mutation?.();}
 get textContent(){return this._text;}
 appendChild(node){node.parent=this;this.children.push(node);mutation?.();return node;}
 remove(){this.parent.children=this.parent.children.filter(n=>n!==this);mutation?.();}
 setAttribute(name,value){this.attributes[name]=value;}
 addEventListener(name,fn){this.events[name]=fn;}
 removeAttribute(name){if(name==='data-previous')delete this.dataset.previous;}
}
const workspace=new Node('production-workspace'),host=new Node(),add=new Node(),output=new Node('batch-output');
const mobile={matches:false,addEventListener(type,fn){this.changed=fn;}};
const document={
 getElementById(id){return id===workspace.id?workspace:id===output.id?output:host.children.find(n=>n.id===id)||null;},
 querySelector(selector){return selector==='#clip-placeholders .clip-placeholders'?host:selector==='#clip-editor .clip-add'?add:null;},
 querySelectorAll(selector){return selector==='#clip-editor .clip-row'?rows:selector==='#batch-output .batch-clip'?cards:[];},
 createElement(){return new Node();}
};
const window={addEventListener(name,fn){listeners.set(name,fn);}};
function row(id){const n=new Node();n.dataset.clipId=id;return n;}
function card(id){return new Node('generated-clip-'+id);}
function flush(){let count=0;while(frames.length){assert(++count<8,'reconciliation must settle, not loop on placeholder child mutations');frames.shift()();}return count;}
function change(){listeners.get('voxover-rows')();flush();}
rows=[row('b'),row('a'),row('new')];cards=[card('a'),card('b'),card('removed')];
const originals=[...cards];
const context={window,document,matchMedia:()=>mobile,requestAnimationFrame:fn=>frames.push(fn),MutationObserver:class{constructor(fn){mutation=fn;}observe(){}}};
const source=fs.readFileSync('clip-alignment.js','utf8');vm.runInNewContext('('+source+')()',context);flush();
assert.deepEqual(rows.map(r=>r.style.gridRow),['2','3','4']);
assert.deepEqual(cards.map(r=>r.style.gridRow),['3','2','6'],'matches use IDs, not DOM order or duplicate text');
const heading=host.children.find(n=>n.id==='previous-clips-heading'),toggle=heading.children[0];
assert.equal(toggle.type,'button');assert.equal(toggle.textContent,'Previous clips (1)');
assert.equal(toggle.attributes['aria-expanded'],'false');assert.equal(toggle.attributes['aria-controls'],'generated-clip-removed');
assert.equal(cards[2].hidden,true,'previous clips start collapsed');assert.equal(workspace.style['--clip-track-count'],'5','collapsed cards reserve no tracks');
assert.equal(cards[0].hidden,false);assert.equal(cards[1].hidden,false);
toggle.events.click();flush();assert.equal(cards[2].hidden,false);assert.equal(toggle.attributes['aria-expanded'],'true');
assert.equal(workspace.style['--clip-track-count'],'6','expanded cards add exactly their visible tracks');
assert.equal(cards[2].dataset.previous,'true');assert.equal(add.style['grid-row'],'5');
const placeholder=host.children.find(n=>n.dataset.clipId==='new');assert(placeholder);assert.equal(placeholder.style.gridRow,'4');
assert.equal(host.children.find(n=>n.id==='previous-clips-heading').style.gridRow,'5');
const steadyWrites=writes;change();assert.equal(writes,steadyWrites,'unchanged placeholders must not rewrite text nodes');assert.equal(host.children.find(n=>n.dataset.clipId==='new'),placeholder);
assert.deepEqual(cards,originals,'native cards remain in place and retain identity');
mobile.matches=true;mobile.changed();flush();
assert.deepEqual(rows.map(r=>r.style.gridRow),['3','5','7']);assert.deepEqual(cards.map(r=>r.style.gridRow),['6','4','11']);assert.equal(placeholder.style.gridRow,'8');assert.equal(add.style['grid-row'],'9');
assert.equal(host.children.find(n=>n.id==='previous-clips-heading').style.gridRow,'10','mobile Previous clips must follow Add clip on a distinct track');
assert.equal(workspace.style['--clip-track-count'],'11','mobile track count includes separate previous heading and native orphan without an empty trailing track');
toggle.events.click();flush();assert.equal(cards[2].hidden,true);assert.equal(workspace.style['--clip-track-count'],'10');
assert.equal(add.style['grid-row'],'9');assert.equal(heading.style.gridRow,'10');
// During fade-out, the removing row still reserves its shared track.
rows[0].dataset.removing='true';change();assert.equal(cards[1].style.gridRow,'4');
rows=rows.slice(1);change();assert.equal(cards[1].dataset.previous,'true');assert.equal(cards[0].style.gridRow,'4');assert.equal(toggle.textContent,'Previous clips (2)');assert.equal(cards[1].hidden,true);
// Undo/reorder reconnects the same native card, never recreating its audio.
rows=[row('removed'),row('b'),row('a')];change();assert(cards.every(c=>!c.dataset.previous));assert.equal(host.children.find(n=>n.id==='previous-clips-heading').hidden,true);assert(!host.children.some(n=>n.dataset.clipId==='new'));
assert(cards.every(c=>c.hidden===false),'undo unhides matched native players even while previous clips are collapsed');
assert.deepEqual(cards,originals);assert.deepEqual(cards.map(r=>r.style.gridRow),['8','6','4']);
mobile.matches=false;mobile.changed();flush();assert.deepEqual(cards.map(r=>r.style.gridRow),['4','3','2']);
const callback=listeners.get('voxover-rows');vm.runInNewContext('('+source+')()',context);assert.equal(listeners.get('voxover-rows'),callback,'initialization is idempotent');
console.log('PASS accessible collapse/count/track sizing, stable-ID alignment, new placeholders, orphan/undo/reorder, fade track retention, mobile pairing, native identity, and bounded mutation reconciliation');
