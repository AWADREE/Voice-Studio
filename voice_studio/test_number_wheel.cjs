// Contract tests for the wheel guard; native scrolling is additionally checked in the browser.
const fs = require('fs'), vm = require('vm'), assert = require('node:assert/strict');
const path = require('path');
const filename = path.join(__dirname, 'number-wheel.js');
const source = fs.existsSync(filename) ? fs.readFileSync(filename, 'utf8') : '() => {}';
const listeners = new Map(), frames = [];
const document = {addEventListener(type, handler, options) {
  const entries = listeners.get(type) || [];
  entries.push({handler, options}); listeners.set(type, entries);
}};
const window = {};
const context = {window, document, requestAnimationFrame: callback => frames.push(callback)};
const install = () => vm.runInNewContext('(' + source + ')()', context);
const input = (type = 'number', readOnly = false) => ({
  tagName: 'INPUT', type, readOnly, value: '42', disabled: false,
  blur() { assert.fail('Wheel must not move keyboard focus'); },
});
function dispatch(type, target, extra = {}) {
  const event = {target, ctrlKey: false, deltaX: 0, deltaY: 100,
    composedPath: () => [target, document], defaultPrevented: false, stopped: false,
    preventDefault() { this.defaultPrevented = true; },
    stopImmediatePropagation() { this.stopped = true; }, ...extra};
  for (const {handler} of listeners.get(type) || []) handler(event);
  return event;
}
const flush = () => { const pending = frames.splice(0); pending.forEach(callback => callback()); };
install(); install();
assert.equal(listeners.get('wheel')?.length, 1, 'App load must install exactly one wheel guard');
assert.equal(listeners.get('wheel')[0].options.capture, true, 'Guard must precede component wheel handlers');
assert.equal(listeners.get('wheel')[0].options.passive, true, 'Wheel default scrolling must remain native');
for (const focused of [false, true]) {
  const field = input(); document.activeElement = focused ? field : null;
  const event = dispatch('wheel', field);
  assert.equal(field.readOnly, true, 'Number must not be natively stepped during wheel dispatch');
  assert.equal(field.value, '42'); assert.equal(event.defaultPrevented, false);
  assert.equal(event.stopped, true, 'Component wheel handlers must not step the value either');
  assert.equal(document.activeElement, focused ? field : null);
  flush(); assert.equal(field.readOnly, false, 'Field must be editable after wheel default processing');
}
// Newly created controls and open shadow-root retargeting need no scan or observer.
const lateField = input(), host = {tagName:'DIV'};
dispatch('wheel', host, {composedPath: () => [lateField, {}, host, document]});
assert.equal(lateField.readOnly, true); flush(); assert.equal(lateField.readOnly, false);
// Multiple wheel events share protection until the next paint.
dispatch('wheel', lateField); dispatch('wheel', lateField); flush();
assert.equal(lateField.readOnly, false);
// Typing/clicking before the next animation frame immediately restores editability.
for (const type of ['keydown', 'beforeinput', 'pointerdown', 'focusout']) {
  dispatch('wheel', lateField); dispatch(type, lateField);
  assert.equal(lateField.readOnly, false, `${type} must not wait for a paint`); flush();
}
// An older restoration callback must not undo a subsequent wheel guard.
dispatch('wheel', lateField); dispatch('keydown', lateField); dispatch('wheel', lateField);
frames.shift()(); assert.equal(lateField.readOnly, true); flush(); assert.equal(lateField.readOnly, false);
for (const field of [input('range'), input('text'), input('number', true), {...input(),disabled:true}]) {
  const original = field.readOnly, event = dispatch('wheel', field);
  assert.equal(field.readOnly, original); assert.equal(event.defaultPrevented, false);
  assert.equal(event.stopped, false, 'Other control behavior must be untouched'); flush();
}
const field = input();
const zoom = dispatch('wheel', field, {ctrlKey:true});
assert.equal(field.readOnly, false); assert.equal(zoom.stopped, false); flush();
const activeSeed=input();dispatch('wheel',activeSeed);
activeSeed.dataset={generationReadonly:'true'};flush();
assert.equal(activeSeed.readOnly,true,'wheel cleanup must retain an active regeneration lock');
console.log('PASS number wheel: focused/unfocused, native scroll, focus, dynamic/shadow controls, repeated events, immediate typing, sliders, readonly, disabled, zoom, and idempotence');
