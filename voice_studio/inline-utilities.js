() => {
 if(window.voxoverUtilities)return;
 const mounted=new Map(),pending=new Set();
 const setAttribute=(node,name,value)=>{if(node&&node.getAttribute(name)!==value)node.setAttribute(name,value);};
 const section=kind=>document.getElementById('inline-'+kind+'-section');
 const host=kind=>document.getElementById('inline-'+kind+'-host');
 const header=kind=>section(kind)?.querySelector('button.label-wrap');
 const openState=kind=>header(kind)?.classList.contains('open');
 const footerButton=kind=>document.querySelector('footer[aria-label="Gradio footer navigation"] > button.'+(kind==='api'?'show-api':'settings'));
 function dialogKind(dialog){
  // Both native labels are localized. Match the corresponding native footer
  // label or stable component markers, never English text or a guessed default.
  if(dialog.querySelector('.theme-buttons'))return 'settings';
  if(dialog.querySelector('#start-api-recorder'))return 'api';
  const label=dialog.getAttribute('aria-label');
  if(label)for(const kind of ['settings','api'])if(label===footerButton(kind)?.textContent.trim())return kind;
  return null; // Native async component has not identified itself yet.
 }
 function semantics(kind){
  const h=header(kind);if(!h)return;
  setAttribute(h,'aria-expanded',String(openState(kind)));
  setAttribute(h,'aria-controls','inline-'+kind+'-host');
  setAttribute(host(kind),'role','region');
  setAttribute(host(kind),'aria-label',kind==='api'?'Use via API':'Settings');
 }
 function open(kind){
  semantics(kind);const existing=mounted.get(kind);if(existing?.isConnected)return;
  if(pending.has(kind))return;
  const trigger=footerButton(kind);if(trigger){pending.add(kind);trigger.click();}
 }
 function close(kind){semantics(kind);}
 window.voxoverUtilities={open,close};
 function refresh(){
  for(const kind of ['api','settings']){
   semantics(kind);const trigger=footerButton(kind);if(trigger&&trigger.dataset.inlineUtilityTrigger!==kind)trigger.dataset.inlineUtilityTrigger=kind;
   const old=mounted.get(kind);if(old&&!old.isConnected){mounted.delete(kind);pending.delete(kind);if(openState(kind))header(kind).click();}
  }
  document.querySelectorAll('.api-docs[role="dialog"]').forEach(dialog=>{
   const kind=dialogKind(dialog);if(!kind)return;const target=host(kind);if(!target)return;
   dialog.dataset.inlineUtility=kind;dialog.setAttribute('role','region');dialog.removeAttribute('aria-modal');
   target.append(dialog);mounted.set(kind,dialog);pending.delete(kind);
   if(!openState(kind))header(kind)?.click();
   // Native utilities lock body scrolling on mount. Inline sections must not.
   if(document.body.style.overflow==='hidden')document.body.style.overflow='';
  });
  for(const kind of ['api','settings'])if(openState(kind)&&!mounted.has(kind))open(kind);
  // API documentation mounts its banner asynchronously after the outer root.
  for(const [kind,dialog] of mounted){
   const closeButton=dialog.querySelector('.banner-wrap > button');
   if(closeButton&&!closeButton.dataset.inlineCollapse){
    closeButton.dataset.inlineCollapse='true';
    closeButton.setAttribute('aria-label','Collapse '+(kind==='api'?'Use via API':'Settings'));
    closeButton.addEventListener('click',e=>{
     e.preventDefault();e.stopImmediatePropagation();
     if(openState(kind))header(kind).click();header(kind)?.focus();
    },true);
   }
  }

 }
 // Coalesce native component updates once per frame. Never create a synchronous
 // observer feedback chain with the app's existing component polish observer.
 let frame=0;
 const options={childList:true,subtree:true,attributes:true,attributeFilter:['class','aria-label']};
 const observer=new MutationObserver(()=>{
  if(frame)return;
  frame=requestAnimationFrame(()=>{
   frame=0;observer.disconnect();
   try{refresh();}finally{observer.observe(document.body,options);}
  });
 });
 refresh();observer.observe(document.body,options);
}
