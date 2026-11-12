() => {
 if(window.voxoverReadiness)return;window.voxoverReadiness=true;
 const root=document.getElementById('production-workspace');
 function validText(value){const size=Array.from(value.trim()).length;return size>0&&size<=2000;}
 function refresh(){
  const button=document.getElementById('generate-commentary');if(!button)return;
  const voice=document.querySelector('.studio-voice-input .filename[aria-label]');
  const tabs=document.getElementById('commentary-mode-tabs');
  const batch=tabs?.querySelector('[role="tab"][aria-selected="true"]')?.textContent.trim()==='Multiple';
  const busy=/Generating/.test(button.textContent)||!!window.voxoverGenerationGuard?.busy();
  let contentValid=true;
  const workspace=document.getElementById('voice-mode-workspace');
  const mode=workspace?.classList.contains('generate-mode')?'generate':workspace?.classList.contains('design-mode')?'design':'clone';
  root.classList?.toggle('multiple-mode',mode==='generate'&&!!batch);
  let valid=!busy;
  if(batch&&mode==='generate'){
   const rows=[...root.querySelectorAll('.clip-list .clip-row:not([data-removing])')];
   contentValid=rows.length>0&&rows.length<=100&&rows.every(row=>{
    const minutes=row.querySelector('[data-field="minutes"]').value,seconds=row.querySelector('[data-field="seconds"]').value;
    const seed=row.querySelector('[data-field="seed"]');
    const seedValid=!row.dataset.seedInitialized || (seed?.value!=='' && Number.isSafeInteger(Number(seed?.value)) && Number(seed.value)>=-1);
    return /^\d+$/.test(minutes)&&Number(minutes)<=9999&&seconds!==''&&Number.isFinite(Number(seconds))&&Number(seconds)>=0&&Number(seconds)<60&&validText(row.querySelector('textarea').value)&&seedValid;
   });
  }else{
   const field=tabs?.querySelector('textarea:not(.clip-source):not(.clip-row textarea)');
   contentValid=!!field&&validText(field.value);
   if(window.voxoverSeedRandomizer?.enabled){
    const seed=document.querySelector('#single-clip-seed [data-field="seed"]');
    contentValid=contentValid && seed?.value!=='' && Number.isSafeInteger(Number(seed?.value)) && Number(seed.value)>=-1;
   }
  }
  const panel=tabs?.parentElement;
  for(const input of panel?.querySelectorAll('.generation-settings input[type="number"]')||[]){
   if(input.disabled)continue;
   const number=Number(input.value);if(input.value===''||!Number.isFinite(number)||(input.min!==''&&number<Number(input.min))||(input.max!==''&&number>Number(input.max)))contentValid=false;
  }
  const language=panel?.querySelector('[role="listbox"]');
  const languages=['Auto','English','Chinese','Japanese','Korean','German','French','Russian','Portuguese','Spanish','Italian'];
  if(!language||!languages.includes(language.value))contentValid=false;
  if(mode==='generate')valid=valid&&!!voice&&/\.pt$/i.test(voice.getAttribute('aria-label'));
  if(mode==='clone'){
   const reference=document.getElementById('clone-inputs');
   const include=reference?.querySelector('input[type="checkbox"]')?.checked;
   const transcript=reference?.querySelector('textarea');
   const hasAudio=!!window.voxoverReferenceReady||!!reference?.querySelector('.studio-reference-audio .file-preview-holder');
   valid=valid&&hasAudio&&(!include||!!transcript?.value.trim());
  }
  if(mode==='design')valid=valid&&!!document.querySelector('#design-inputs textarea')?.value.trim();
  valid=valid&&contentValid;
  if(button.disabled===valid)button.disabled=!valid;
 }
 root.addEventListener('input',refresh);root.addEventListener('change',refresh);
 new MutationObserver(refresh).observe(root,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['disabled','aria-selected','aria-label']});
 refresh();
}
