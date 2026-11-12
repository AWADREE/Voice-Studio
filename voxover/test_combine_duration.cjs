const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('app.py', 'utf8');
const js = name => source.match(new RegExp(name + ' = """([\\s\\S]*?)"""'))[1];
let row = {dataset: {}};
global.document = {getElementById: id => id === 'timeline-duration-fields' ? row : null};
const edit = eval('(' + js('TIMELINE_DURATION_EDIT_JS') + ')');
const apply = eval('(' + js('TIMELINE_DURATION_APPLY_JS') + ')');
assert.deepEqual(apply([1, 5], 0, 0), [1, 5]);
// The server's candidate was computed before this edit but arrives afterward.
edit();
for (const value of [0, null, 50]) {
  assert.deepEqual(apply([1, 5], 2, value), [2, value]);
}
assert.equal(row.dataset.durationEdited, 'true');
row = {dataset: {}};
assert.deepEqual(apply([{__type__: 'update'}, {__type__: 'update'}], 2, 50), [2, 50]);
assert.deepEqual(apply(null, 2, 50), [2, 50]);
assert.deepEqual(apply([2, 29], 2, 28), [2, 29]);
row = null;
assert.deepEqual(apply([1, 5], 2, 50), [2, 50]);
console.log('Duration edit gate: passed');
