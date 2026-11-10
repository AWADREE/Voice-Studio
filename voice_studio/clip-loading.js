() => {
  if(window.voxoverClipLoading)return;
  window.voxoverClipLoading=true;
  let marked=null;
  let operation=null,startedAt=0,timer=null;
  function updateElapsed(){
    const label=marked?.querySelector('.clip-pending-elapsed');
    const text='processing | '+((Date.now()-startedAt)/1000).toFixed(1)+'s';
    if(label && label.textContent!==text)label.textContent=text;
  }
  function refresh(){
    const pending=window.voxoverGenerationGuard?.pending;
    const id=pending && pending!=='full'?pending:null;
    if(id!==operation){
      if(timer!==null){clearInterval(timer);timer=null;}
      operation=id;startedAt=Date.now();
      if(id)timer=setInterval(updateElapsed,100);
    }
    const current=id?document.getElementById('generated-clip-'+id):null;
    if(marked && marked!==current){
      marked.removeAttribute('data-regenerating');
      marked.querySelector('.batch-audio')?.removeAttribute('aria-busy');
    }
    marked=current;
    if(marked){
      marked.setAttribute('data-regenerating','true');
      // Only the old player is busy. Keep the sibling live status outside that
      // region so assistive technology can announce generation immediately.
      marked.querySelector('.batch-audio')?.setAttribute('aria-busy','true');
    }
    if(id)updateElapsed();
    // Existing audio remains valid until replacement succeeds. Play all may
    // include the old target and can restart the sequence throughout generation.
  }
  window.addEventListener('voxover-operation',refresh);
  new MutationObserver(refresh).observe(document.getElementById('listen-panel'),{subtree:true,childList:true});
  refresh();
}
