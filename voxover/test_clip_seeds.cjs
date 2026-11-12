const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let random=7;
const context={Uint32Array,crypto:{getRandomValues(array){array[0]=random;return array;}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('clip-seeds.js','utf8'),context);
assert.equal(vm.runInContext('newClipSeed(7)',context),8,'New seed must differ even on a repeated random draw');
random=4294967295;assert.equal(vm.runInContext('newClipSeed(4294967295)',context),0,'max draw wraps safely');
assert.equal(vm.runInContext('newClipSeed(-1)',context),4294967295);
assert.equal(vm.runInContext('newClipSeed(42)',context),4294967295);
console.log('PASS fresh clip seeds use bounded secure randomness and always differ from the current seed');
