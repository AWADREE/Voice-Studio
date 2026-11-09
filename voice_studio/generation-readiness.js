() => {
 if(window.voiceStudioReadiness)return;window.voiceStudioReadiness=true;
 const root=document.getElementById('production-workspace');
 function validText(value){const size=Array.from(value.trim()).length;return size>0&&size<=2000;}
 function refresh(){
  const button=document.getElementById('generate-commentary');if(!button)return;
  const voice=document.querySelector('.studio-voice-input .filename[aria-label]');
  const tabs=document.getElementById('commentary-mode-tabs');
  const batch=tabs?.querySelector('[role="tab"][aria-selected="true"]')?.textContent.includes('Timestamped');
  const busy=/Generating/.test(button.textContent);
  let contentValid=true;
  const workspace=document.getElementById('voice-mode-workspace');
  const mode=workspace?.classList.contains('generate-mode')?'generate':workspace?.classList.contains('design-mode')?'design':'clone';
  let valid=!busy;
  if(batch&&mode==='generate'){
   const rows=[...tabs.querySelectorAll('.clip-list .clip-row:not([data-removing])')];
   contentValid=rows.length>0&&rows.length<=100&&rows.every(row=>{
    const minutes=row.querySelector('[data-field="minutes"]').value,seconds=row.querySelector('[data-field="seconds"]').value;
    return /^\d+$/.test(minutes)&&Number(minutes)<=9999&&/^\d+$/.test(seconds)&&Number(seconds)<=59&&validText(row.querySelector('textarea').value);
   });
  }else{
   const field=tabs?.querySelector('textarea:not(.clip-source):not(.clip-row textarea)');
   contentValid=!!field&&validText(field.value);
  }
  const panel=tabs?.parentElement;
  for(const input of panel?.querySelectorAll('.generation-settings input[type="number"]')||[]){
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
   const hasAudio=!!window.voiceStudioReferenceReady||!!reference?.querySelector('.studio-reference-audio .file-preview-holder');
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
