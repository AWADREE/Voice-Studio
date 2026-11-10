() => {
  if(window.voxoverGenerationGuard)return;
  let pending=null, activeJob=null, approved=false, lastHighlight='', confirmation=null, returnFocus=null;
  const queue=[];
  let fullBaseline=null;
  const streaming=()=>pending==='full' && window.voxoverBatchMetadata?.streaming===true && window.voxoverBatchMetadata!==fullBaseline;
  const canEnqueue=id=>pending!=='full' || (streaming() && !window.voxoverBatchMetadata.pending_ids?.includes(id));
  const dialog=document.createElement('dialog');
  dialog.id='generation-replace-dialog';
  dialog.setAttribute('aria-labelledby','generation-replace-title');
  dialog.setAttribute('aria-describedby','generation-replace-description');
  dialog.innerHTML='<h2 id="generation-replace-title">Replace generated audio?</h2><p id="generation-replace-description">Generating again will replace the current clips in Listen & export. To keep the other clips, cancel and use the paragraph Regenerate button instead. Your last combined audio stays until you combine again.</p><div class="generation-dialog-actions"><button type="button" data-cancel autofocus>Cancel</button><button type="button" data-confirm>Replace & generate</button></div>';
  document.body.appendChild(dialog);
  const main=()=>document.getElementById('generate-commentary');
  const busy=()=>pending!==null || /Generating/.test(main()?.textContent || '');
  function update(){
    // A running request owns its snapshot, not the entire editor or importer.
    const editor=document.getElementById('clip-editor');
    if(editor)editor.inert=false;
    const importer=document.getElementById('clip-import');if(importer)importer.inert=false;
    if(pending!==null && main())main().disabled=true;
    window.dispatchEvent(new Event('voxover-operation'));
  }
  function start(id){if(id==='full')fullBaseline=window.voxoverBatchMetadata;pending=id;update();if(id==='full')window.voxoverBatchPlayback?.stop();}
  function drain(){
    if(pending!==null)return;
    while(queue.length){
      const next=queue.shift();
      if(!next.valid())continue;
      activeJob=next;start(next.id);next.run();return;
    }
    update();
    document.getElementById('production-workspace')?.dispatchEvent(new Event('change',{bubbles:true}));
  }
  function finish(){
    if(pending && pending!=='full'){
      const event=new Event('voxover-clip-result');
      event.detail={id:pending,status:document.getElementById('batch-status')?.textContent?.trim() || ''};
      window.dispatchEvent(event);
    }
    pending=null;activeJob=null;drain();
  }
  function enqueue(id,run,data={},valid=()=>true){
    if(!canEnqueue(id) || (pending!=='full' && /Generating/.test(main()?.textContent || '')) || pending===id || queue.some(job=>job.id===id))return false;
    queue.push({...data,id,run,valid});
    if(pending===null)drain();else update();
    return true;
  }
  function cancel(id){
    const index=queue.findIndex(job=>job.id===id);
    if(index>=0){queue.splice(index,1);update();}
  }
  function confirmAction({title,description,confirmLabel,origin,action}){
    if(dialog.open)return false;
    confirmation=action;returnFocus=origin;
    dialog.querySelector('#generation-replace-title').textContent=title;
    dialog.querySelector('#generation-replace-description').textContent=description;
    dialog.querySelector('[data-confirm]').textContent=confirmLabel;
    dialog.showModal();return true;
  }
  const api={busy,start,finish,enqueue,cancel,confirmAction,streaming,canEnqueue,
    position:id=>queue.findIndex(job=>job.id===id)+1,
    job:id=>activeJob?.id===id?activeJob:queue.find(job=>job.id===id),
    get pending(){return pending;}};
  window.voxoverGenerationGuard=api;
  function hasAudio(){
    return !!document.querySelector('#batch-output .batch-audio') ||
      !!document.querySelector('#listen-panel .studio-wav-output a[href]');
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest?.('#generate-commentary');
    if(!button)return;
    if(busy()) {event.preventDefault();event.stopImmediatePropagation();return;}
    if(!approved && hasAudio()){
      event.preventDefault();event.stopImmediatePropagation();
      const multiple=document.getElementById('production-workspace')?.classList.contains('multiple-mode');
      confirmAction({title:'Replace generated audio?',description:'Generating again will replace the current generated audio in Listen & export.'+(multiple?' To keep the other clips, cancel and use the paragraph Regenerate button instead. Your last combined audio stays until you combine again.':' Cancel to keep your current take.'),confirmLabel:'Replace & generate',origin:main(),action:()=>{
        if(busy()||main()?.disabled)return;
        approved=true;main()?.click();approved=false;
      }});return;
    }
    approved=false;
    start('full');
  },true);
  dialog.querySelector('[data-cancel]').addEventListener('click',()=>dialog.close());
  dialog.querySelector('[data-confirm]').addEventListener('click',()=>{
    const action=confirmation;confirmation=null;dialog.close();action?.();
  });
  dialog.addEventListener('close',()=>{confirmation=null;returnFocus?.focus({preventScroll:true});returnFocus=null;});
  function revealReplacement(){
    const highlighted=document.querySelector('.batch-clip-updated');
    const version=window.voxoverBatchMetadata?.version;
    const id=window.voxoverBatchMetadata?.highlight_id;
    if(highlighted && id && highlighted.id==='generated-clip-'+id && version!==lastHighlight){
      lastHighlight=version;
      highlighted.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    }
  }
  window.addEventListener('voxover-batch',revealReplacement);
  const observer=new MutationObserver(revealReplacement);
  observer.observe(document.getElementById('listen-panel'),{subtree:true,childList:true});
}
