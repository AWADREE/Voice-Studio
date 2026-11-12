() => {
  if(window.voxoverClipLoading)return;
  window.voxoverClipLoading=true;
  let marked=new Set(),operation=null,startedAt=0,timer=null;
  function updateElapsed(){
    const text='processing | '+((Date.now()-startedAt)/1000).toFixed(1)+'s';
    for(const node of marked){
      const label=node.querySelector('.clip-pending-elapsed');
      const value=node.getAttribute?.('data-loading-state')==='queued'?'Waiting for earlier clips':text;
      if(label && label.textContent!==value)label.textContent=value;
    }
  }
  function refresh(){
    const guard=window.voxoverGenerationGuard,metadata=window.voxoverBatchMetadata;
    const streaming=guard?.streaming?.();
    const id=streaming?metadata.active_id:guard?.pending && guard.pending!=='full'?guard.pending:null;
    if(id!==operation){
      if(timer!==null){clearInterval(timer);timer=null;}
      operation=id;startedAt=Date.now();
      if(id)timer=setInterval(updateElapsed,100);
    }
    const current=new Set();
    const ids=streaming?metadata.pending_ids||[]:id?[id]:[];
    for(const pendingId of ids){
      const card=document.getElementById('generated-clip-'+pendingId);
      if(card){
        current.add(card);card.setAttribute('data-regenerating','true');
        card.setAttribute('data-loading-state',pendingId===id?'active':'queued');
        card.querySelector('.batch-audio')?.setAttribute('aria-busy','true');
        const label=card.querySelector('.progress-level-inner');
        if(label){const text=streaming?(pendingId===id?'Generating clip...':'Clip queued'):'Regenerating clip...';if(label.textContent!==text)label.textContent=text;}
      }
    }
    for(const node of document.querySelectorAll?.('#clip-placeholders .clip-empty-player[data-loading-state="active"], #clip-placeholders .clip-empty-player[data-loading-state="queued"]')||[])current.add(node);
    for(const node of marked)if(!current.has(node)){
      node.removeAttribute('data-regenerating');node.removeAttribute('data-loading-state');
      node.querySelector('.batch-audio')?.removeAttribute('aria-busy');
    }
    marked=current;updateElapsed();
  }
  window.addEventListener('voxover-operation',refresh);
  window.addEventListener('voxover-batch',refresh);
  window.addEventListener('voxover-aligned',refresh);
  new MutationObserver(refresh).observe(document.getElementById('listen-panel'),{subtree:true,childList:true});
  refresh();
}
