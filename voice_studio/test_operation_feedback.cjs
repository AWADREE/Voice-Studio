const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('operation-feedback.js','utf8');
let callback;
const attrs={};const button={disabled:false,textContent:'Unloading model...',getAttribute:k=>attrs[k],setAttribute:(k,v)=>attrs[k]=v,classList:{toggle(){}}};
const context={window:{},document:{body:{},querySelectorAll:s=>s==='button'?[button]:[]},MutationObserver:class{constructor(fn){callback=fn}observe(){}}};
vm.runInNewContext('('+source+')()',context);
assert(button.disabled);assert.equal(attrs['aria-busy'],'true');
button.disabled=false;callback();assert(button.disabled); // framework applies interactive first
button.textContent='Unload experimental model';callback();assert(!button.disabled);assert.equal(attrs['aria-busy'],'false');
button.textContent='Cloning & generating...';callback();assert(button.disabled);
button.textContent='Switch to Single commentary to clone';callback();assert(button.disabled); // mode restriction preserved
console.log('PASS operation guard busy race and mode restriction');
