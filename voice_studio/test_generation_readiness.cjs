const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let refresh,mode='clone',batch=false,voice=null;
const button={disabled:true,textContent:'Generate commentary'};
const text={value:''},transcript={value:''},description={value:''},include={checked:true};
const number={value:'42',min:'',max:''},language={value:'English'};
const reference={querySelector:s=>s==='textarea'?transcript:s==='input[type="checkbox"]'?include:null};
const tabs={querySelector:s=>s.includes('role=')?{textContent:batch?'Multiple':'Single commentary'}:text,
 querySelectorAll:()=>[],parentElement:{querySelectorAll:()=>[number],querySelector:()=>language}};
const workspace={classList:{contains:name=>name===mode+'-mode'}};
const rootClasses=new Set();
const root={querySelectorAll:()=>[],classList:{toggle:(name,on)=>on?rootClasses.add(name):rootClasses.delete(name)},addEventListener:(type,f)=>{refresh=f}};
const document={getElementById:id=>({'production-workspace':root,'generate-commentary':button,
 'voice-mode-workspace':workspace,'clone-inputs':reference,'commentary-mode-tabs':tabs}[id]),
 querySelector:s=>s==='#design-inputs textarea'?description:voice};
const singleSeed={value:'123'};
const originalQuery=document.querySelector;
document.querySelector=s=>s==='#single-clip-seed [data-field="seed"]'?singleSeed:originalQuery(s);
const window={};
vm.runInNewContext('('+fs.readFileSync('generation-readiness.js','utf8')+')()',
 {window,document,MutationObserver:class{observe(){}}});
assert(button.disabled);
text.value='Hello';refresh();assert(button.disabled);
window.voxoverReferenceReady=true;transcript.value='Reference';refresh();assert(!button.disabled);
transcript.value='';refresh();assert(button.disabled);
include.checked=false;refresh();assert(!button.disabled);
number.value='';refresh();assert(button.disabled);
number.value='42';text.value='x'.repeat(2001);refresh();assert(button.disabled);
text.value='Valid';mode='design';refresh();assert(button.disabled);
description.value='Warm baritone';refresh();assert(!button.disabled);
mode='generate';refresh();assert(button.disabled);
voice={getAttribute:()=> 'voice.pt'};refresh();assert(!button.disabled);
batch=true;refresh();assert(button.disabled);assert(rootClasses.has('multiple-mode'));
mode='clone';refresh();assert(!rootClasses.has('multiple-mode'));mode='generate';refresh();
batch=false;button.textContent='Generating commentary...';refresh();assert(button.disabled);
button.textContent='Generate commentary';refresh();assert(!button.disabled);
language.value='';refresh();assert(button.disabled);
console.log('PASS shared composer readiness across clone, design, saved voice, settings and busy states');

language.value='English';number.disabled=true;number.value='';
window.voxoverSeedRandomizer={enabled:true};refresh();assert(!button.disabled,'disabled global seed is ignored');
for(const value of ['', '1.5', '-2', '9007199254740992']){singleSeed.value=value;refresh();assert(button.disabled,value);}
singleSeed.value='123';refresh();assert(!button.disabled);
window.voxoverSeedRandomizer.enabled=false;number.disabled=false;number.value='42';singleSeed.value='';refresh();assert(!button.disabled,'hidden single draft is ignored when Randomize is off');
console.log('PASS randomized single seed validation and disabled shared seed readiness');

batch=true;
const fields={minutes:{value:'0'},seconds:{value:'2.125041666666667'},seed:{value:'42'}};
root.querySelectorAll=()=>[{dataset:{seedInitialized:'true'},querySelector:selector=>selector==='textarea'?{value:'Valid aligned paragraph'}:fields[selector.match(/data-field="([^"]+)"/)[1]]}];
refresh();assert(!button.disabled,'sample-precise fractional timestamps must remain ready for full generation');
for(const seconds of ['', '60','-0.1','NaN','Infinity']){fields.seconds.value=seconds;refresh();assert(button.disabled,seconds);}
