() => {
  const workspace=document.getElementById('production-workspace');
  if(!workspace || workspace.dataset.alignmentBound)return;
  workspace.dataset.alignmentBound='true';
  const mobile=matchMedia('(max-width: 900px)');
  let scheduled=false;
  let previousExpanded=false;
  function reconcile(){
    scheduled=false;
    const rows=[...document.querySelectorAll('#clip-editor .clip-row')];
    const cards=[...document.querySelectorAll('#batch-output .batch-clip')];
    const ids=rows.map(row=>row.dataset.clipId);
    const orphans=cards.filter(card=>!ids.includes(card.id.replace('generated-clip-','')));
    const narrow=mobile.matches;
    const first=narrow?3:2, step=narrow?2:1;
    const footer=first+rows.length*step;
    // Narrow sections share one column: Add clip and Previous clips need
    // separate natural tracks, unlike their side-by-side desktop footer.
    const previous=footer+(narrow && orphans.length ? 1 : 0);
    workspace.style.setProperty('--clip-track-count',String(previous+(previousExpanded?orphans.length:0)));
    const host=document.querySelector('#clip-placeholders .clip-placeholders');
    if(!host)return;
    const wanted=new Set();
    rows.forEach((row,index)=>{
      const track=first+index*step;
      row.style.gridRow=String(track);
      const card=cards.find(card=>card.id==='generated-clip-'+row.dataset.clipId);
      if(card){card.style.gridRow=String(track+(narrow?1:0));card.removeAttribute('data-previous');card.hidden=false;}
      else {
        const id=row.dataset.clipId;wanted.add(id);
        let placeholder=[...host.children].find(node=>node.dataset.clipId===id);
        if(!placeholder){placeholder=document.createElement('div');placeholder.className='clip-empty-player';placeholder.dataset.clipId=id;host.appendChild(placeholder);}
        const metadata=window.voxoverBatchMetadata;
        const pending=window.voxoverGenerationGuard?.streaming?.() && metadata?.pending_ids?.includes(id);
        const state=pending?(metadata.active_id===id?'active':'queued'):'empty';
        if(placeholder.dataset.loadingState!==state || placeholder.dataset.loadingIndex!==String(index)){
          placeholder.dataset.loadingIndex=String(index);
          placeholder.dataset.loadingState=state;
          if(pending){
            placeholder.innerHTML='<div class="wrap clip-pending-surface"><div class="progress-level"><span class="progress-level-inner" role="status" aria-live="polite"></span></div><div class="progress-bar-wrap" role="progressbar"><div class="progress-bar"></div></div><div class="meta-text clip-pending-elapsed" aria-hidden="true"></div></div>';
            placeholder.querySelector('.progress-level-inner').textContent=state==='active'?`Generating clip ${index+1}...`:`Clip ${index+1} queued`;
            placeholder.querySelector('.progress-bar-wrap').setAttribute('aria-label',`Generating clip ${index+1}`);
          }else placeholder.textContent=`Paragraph ${index+1} - Not generated yet`;
        }
        placeholder.style.gridRow=String(track+(narrow?1:0));
      }
    });
    for(const node of [...host.children])if(node.id!=='previous-clips-heading' && !wanted.has(node.dataset.clipId))node.remove();
    let heading=document.getElementById('previous-clips-heading');
    if(orphans.length && !heading){
      heading=document.createElement('h3');heading.id='previous-clips-heading';
      const toggle=document.createElement('button');toggle.type='button';toggle.className='previous-clips-toggle';
      toggle.addEventListener('click',()=>{previousExpanded=!previousExpanded;schedule();});
      heading.appendChild(toggle);host.appendChild(heading);
    }
    if(heading){
      heading.style.gridRow=String(previous);heading.hidden=!orphans.length;
      const toggle=heading.children[0];
      const text=`Previous clips (${orphans.length})`;
      if(toggle.textContent!==text)toggle.textContent=text;
      toggle.setAttribute('aria-expanded',String(previousExpanded));
      toggle.setAttribute('aria-controls',orphans.map(card=>card.id).join(' '));
    }
    // Keep native audio elements mounted in their original containers. Hiding
    // the cards preserves their state; playback observes hidden and pauses them.
    orphans.forEach((card,index)=>{card.style.gridRow=String(previous+index+1);card.dataset.previous='true';card.hidden=!previousExpanded;});
    document.querySelector('#clip-editor .clip-add')?.style.setProperty('grid-row',String(footer));
    window.dispatchEvent?.(new Event('voxover-aligned'));
  }
  const schedule=()=>{if(!scheduled){scheduled=true;requestAnimationFrame(reconcile);}};
  window.addEventListener('voxover-rows',schedule);
  window.addEventListener('voxover-batch',schedule);
  window.addEventListener('voxover-operation',schedule);
  mobile.addEventListener('change',schedule);
  new MutationObserver(schedule).observe(document.getElementById('batch-output'),{childList:true,subtree:true});
  schedule();
}
