const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let refresh,mode='clone',batch=false,voice=null;
const button={disabled:true,textContent:'Generate commentary'};
const text={value:''},transcript={value:''},description={value:''},include={checked:true};
const number={value:'42',min:'',max:''},language={value:'English'};
const reference={querySelector:s=>s==='textarea'?transcript:s==='input[type="checkbox"]'?include:null};
const tabs={querySelector:s=>s.includes('role=')?{textContent:batch?'Multiple clips':'Single commentary'}:text,
 querySelectorAll:()=>[],parentElement:{querySelectorAll:()=>[number],querySelector:()=>language}};
const workspace={classList:{contains:name=>name===mode+'-mode'}};
const root={addEventListener:(type,f)=>{refresh=f}};
const document={getElementById:id=>({'production-workspace':root,'generate-commentary':button,
 'voice-mode-workspace':workspace,'clone-inputs':reference,'commentary-mode-tabs':tabs}[id]),
 querySelector:s=>s==='#design-inputs textarea'?description:voice};
const window={};
vm.runInNewContext('('+fs.readFileSync('generation-readiness.js','utf8')+')()',
 {window,document,MutationObserver:class{observe(){}}});
assert(button.disabled);
text.value='Hello';refresh();assert(button.disabled);
window.voiceStudioReferenceReady=true;transcript.value='Reference';refresh();assert(!button.disabled);
transcript.value='';refresh();assert(button.disabled);
include.checked=false;refresh();assert(!button.disabled);
number.value='';refresh();assert(button.disabled);
number.value='42';text.value='x'.repeat(2001);refresh();assert(button.disabled);
text.value='Valid';mode='design';refresh();assert(button.disabled);
description.value='Warm baritone';refresh();assert(!button.disabled);
mode='generate';refresh();assert(button.disabled);
voice={getAttribute:()=> 'voice.pt'};refresh();assert(!button.disabled);
batch=true;refresh();assert(button.disabled);
batch=false;button.textContent='Generating commentary...';refresh();assert(button.disabled);
button.textContent='Generate commentary';refresh();assert(!button.disabled);
language.value='';refresh();assert(button.disabled);
console.log('PASS shared composer readiness across clone, design, saved voice, settings and busy states');
