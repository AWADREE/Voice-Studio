const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function target() {
  const listeners = {};
  return {
    addEventListener(type, fn) { (listeners[type] ??= []).push(fn); },
    dispatch(type, detail = {}) { for (const fn of listeners[type] ?? []) fn(detail); },
    count(type) { return (listeners[type] ?? []).length; }
  };
}
const root = target(), attrs = {'aria-describedby':'existing-help'};
root.dataset = {};
const checkbox = {getAttribute:name=>attrs[name], setAttribute:(name,value)=>{attrs[name]=value;}};
const tooltip = {hidden:true, setAttribute(name,value){this[name]=value;}};
root.appendChild = tip => { root.tooltip = tip; };
root.contains = node => node === checkbox || node === tooltip;
root.querySelector = selector => selector === 'input[type="checkbox"]' ? checkbox : tooltip;
let available=false, mountObserver, disconnected=false;
const doc = Object.assign(target(), {querySelector:()=>available?root:null,getElementById:()=>({}),createElement:()=>tooltip});
const context = {document:doc,
  MutationObserver:class{constructor(fn){mountObserver=fn;}observe(){}disconnect(){disconnected=true;}}};
const source = fs.readFileSync('seed-help.js','utf8');
const run = () => vm.runInNewContext('('+source+')()',context);
run();
assert.equal(tooltip.hidden,true,'Help remains hidden before deferred components mount.');
available=true;mountObserver();assert(disconnected,'The deferred observer disconnects after mounting.');
assert.equal(attrs['aria-describedby'],'existing-help voxover-randomize-help','Checkbox describes its tooltip without discarding existing descriptions.');
assert.equal(root.tooltip,tooltip);assert.equal(tooltip.role,'tooltip');assert.match(tooltip.innerHTML,/Seed/);
assert.equal(root.count('focusin'),1);run();assert.equal(root.count('focusin'),1,'Repeated app initialization does not duplicate listeners.');
assert.equal(tooltip.hidden, true, 'Help is not permanently visible.');
root.dispatch('pointerenter');assert.equal(tooltip.hidden, false, 'Hovering the Randomize label or checkbox reveals help.');
doc.dispatch('keydown',{key:'Escape',stopPropagation(){}});
assert.equal(tooltip.hidden,true,'Escape dismisses hover-only help while keyboard focus is elsewhere.');
root.dispatch('pointerleave');root.dispatch('pointerenter');
root.dispatch('pointerleave');assert.equal(tooltip.hidden, true, 'Leaving without focus closes it.');
root.dispatch('focusin');assert.equal(tooltip.hidden, false, 'Keyboard focus on Randomize reveals help.');
root.dispatch('pointerenter');root.dispatch('pointerleave');
assert.equal(tooltip.hidden, false, 'Moving the pointer away does not hide keyboard-focused help.');
doc.dispatch('keydown', {key:'Escape',stopPropagation(){}});
assert.equal(tooltip.hidden, true, 'Escape dismisses without losing focus.');
root.dispatch('focusout',{relatedTarget:null});root.dispatch('focusin');
assert.equal(tooltip.hidden, false, 'Returning focus reopens help after dismissal.');
root.dispatch('focusout',{relatedTarget:tooltip});assert.equal(tooltip.hidden,false,'Moving within the help surface keeps it open.');
root.dispatch('focusout',{relatedTarget:null});assert.equal(tooltip.hidden,true);
console.log('PASS Randomize tooltip: deferred mount, idempotence, aria-describedby, hidden default, label/checkbox hover, keyboard focus, Escape, persistent focus, reopening.');
