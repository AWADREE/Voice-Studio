requestAnimationFrame(() => {
const list = element.querySelector('.clip-list');
const add = element.querySelector('.clip-add');
const draftId=crypto.randomUUID();
function snapshot() {
  props.value = [...list.querySelectorAll('.clip-row:not([data-removing])')].map(row => {
    const value={id:row.dataset.clipId, minutes:Number(row.querySelector('[data-field="minutes"]').value), seconds:Number(row.querySelector('[data-field="seconds"]').value), text:row.querySelector('textarea').value};
    if(row.dataset.seedInitialized){
      const seed=row.querySelector('[data-field="seed"]').value;
      value.seed=seed===''?'':Number(seed);
    }
    return value;
  });
  add.disabled = props.value.length >= 100;
  refreshRegeneration();
  window.dispatchEvent(new Event('voxover-rows'));
}
function row(data) {
  const box = document.createElement('div'); box.className = 'clip-row';
  const uid = crypto.randomUUID();
  box.dataset.clipId = data.id || uid;
  box.innerHTML = `<div class="clip-time"><label for="minutes-${uid}">Minutes<input id="minutes-${uid}" data-field="minutes" type="number" min="0" max="9999" step="1"></label><label for="seconds-${uid}">Seconds<input id="seconds-${uid}" data-field="seconds" type="number" min="0" max="59.999999999" step="any"></label></div><label for="paragraph-${uid}">Commentary<textarea id="paragraph-${uid}" rows="3" maxlength="2000"></textarea></label><div class="clip-seed-controls"><label for="seed-${uid}">Seed<input id="seed-${uid}" data-field="seed" type="number" min="-1" max="9007199254740991" step="1" aria-describedby="seed-note-${uid}"></label><div class="clip-seed-actions"><button class="clip-reset-seed" type="button" title="Reset to the current main seed">Reset</button><button class="clip-new-seed" type="button">New seed</button></div><p class="clip-seed-note" role="status" aria-live="polite" id="seed-note-${uid}">Defaults to the main seed. Reset copies its current value. Use -1 for random.</p></div><div class="clip-row-actions"><button class="clip-regenerate" type="button">Generate</button><button class="clip-remove" type="button">Remove clip</button></div><p class="clip-operation-status" role="status" aria-live="polite" hidden></p>`;
  box.querySelector('[data-field="minutes"]').value = data.minutes;
  box.querySelector('[data-field="seconds"]').value = data.seconds;
  box.querySelector('textarea').value = data.text;
  if(Object.prototype.hasOwnProperty.call(data,'seed')){
    box.querySelector('[data-field="seed"]').value=data.seed;
    box.dataset.seedInitialized='true';
    box.querySelector('[data-field="seed"]').dataset.seedReady='true';
  }
  box.querySelector('.clip-reset-seed').addEventListener('click',()=>{
    const seed=currentSharedSeed(), status=box.querySelector('.clip-operation-status');
    if(seed===undefined){
      status.textContent='Enter a valid main seed before resetting this clip.';status.hidden=false;return;
    }
    const input=box.querySelector('[data-field="seed"]');
    input.value=seed;status.hidden=true;status.textContent='';
    input.dispatchEvent(new Event('input',{bubbles:true}));
  });
  box.querySelector('.clip-new-seed').addEventListener('click',()=>{
    const input=box.querySelector('[data-field="seed"]');
    input.value=newClipSeed(input.value, otherSeeds(box));box.dataset.seedInitialized='true';
    input.dispatchEvent(new Event('input',{bubbles:true}));
  });
  box.querySelector('[data-field="seed"]').addEventListener('input',event=>{event.target.dataset.seedReady='true';box.dataset.seedInitialized='true';});
  box.addEventListener('input',snapshot);
  box.querySelector('.clip-regenerate').addEventListener('click', () => {
    const guard=window.voxoverGenerationGuard;
    if(!guard)return;
    if((guard.pending==='full'&&!guard.canEnqueue?.(box.dataset.clipId))||guard.pending===box.dataset.clipId||guard.position(box.dataset.clipId))return;
    const input=box.querySelector('[data-field="seed"]');
    const id=box.dataset.clipId, metadata=window.voxoverBatchMetadata;
    const batch_id=metadata?.batch_id || null, replacing=!!metadata?.ids?.includes(id);
    const valid=()=>box.isConnected&&!box.dataset.removing &&
      (batch_id ? window.voxoverBatchMetadata?.batch_id===batch_id :
        !window.voxoverBatchMetadata?.batch_id || window.voxoverBatchMetadata?.origin_draft_id===draftId) &&
      (!replacing || window.voxoverBatchMetadata?.ids?.includes(id));
    const submit=()=>{
      if(!valid() || (guard.pending==='full'&&!guard.canEnqueue?.(id)) || guard.pending===id || guard.position(id))return;
      const hasSeed=!!box.dataset.seedInitialized;
      if(hasSeed && (!input.reportValidity() || input.value==='')){
        const status=box.querySelector('.clip-operation-status');status.hidden=false;status.textContent='Enter a valid seed before generating this clip.';snapshot();return;
      }
      // If the main input has not mounted yet, an uninitialized row
      // still inherits the real shared value on the server when its job starts.
      const seed=hasSeed?consumeClipSeed(input, !!window.voxoverSeedRandomizer?.enabled, otherSeeds(box)):undefined;
      const status=box.querySelector('.clip-operation-status');status.hidden=true;status.textContent='';
      snapshot();
      guard.enqueue(id,()=>{
        snapshot();trigger('regenerate',{id,...(seed===undefined?{}:{seed}),batch_id,draft_id:draftId});
      },{seed,batch_id},valid);
    };
    if(!replacing){submit();return;}
    const index=[...list.querySelectorAll('.clip-row:not([data-removing])')].indexOf(box)+1;
    guard.confirmAction({title:`Replace paragraph ${index} audio?`,
      description:'Regenerating will replace this clip and update Download all after it succeeds. Other clips and your last combined audio stay unchanged. If another clip is running, this request joins the queue. Text and shared settings are read when it starts.',
      confirmLabel:'Replace & regenerate',origin:box.querySelector('.clip-regenerate'),action:submit});
  });
  box.querySelector('.clip-remove').addEventListener('click', () => {
    const guard=window.voxoverGenerationGuard;
    if((guard?.pending==='full'&&(!guard.streaming?.()||window.voxoverBatchMetadata?.pending_ids?.includes(box.dataset.clipId)))||guard?.pending===box.dataset.clipId)return;
    guard?.cancel(box.dataset.clipId);
    const next = box.nextElementSibling || box.previousElementSibling;
    box.dataset.removing='true'; snapshot(); (next?.querySelector('textarea') || add).focus();
    const finish=()=>{box.remove();window.dispatchEvent(new Event('voxover-rows'));};
    if(matchMedia('(prefers-reduced-motion: reduce)').matches){finish();return;}
    const anim=box.animate([{opacity:1},{opacity:0}],{duration:200,easing:'ease-out'});
    anim.onfinish=finish;
  });
  list.appendChild(box); refreshRegeneration(); return box;
}
function refreshRegeneration(){
  const ids=window.voxoverBatchMetadata?.ids || [];
  const seeds=window.voxoverBatchMetadata?.seeds || {};
  const guard=window.voxoverGenerationGuard, pending=guard?.pending;
  let initialized=false;
  const rows=[...list.querySelectorAll('.clip-row:not([data-removing])')];
  for(const [index,box] of rows.entries()){
    const button=box.querySelector('.clip-regenerate');
    const generated=ids.includes(box.dataset.clipId);button.hidden=false;
    const active=pending===box.dataset.clipId, position=guard?.position(box.dataset.clipId)||0;
    const job=guard?.job(box.dataset.clipId);
    button.textContent=active?(generated?'Regenerating...':'Generating...'):position?`Queued ${position}`:(generated?'Regenerate':'Generate');
    const unfinished=pending==='full'&&(!guard.streaming?.()||window.voxoverBatchMetadata?.pending_ids?.includes(box.dataset.clipId));
    button.disabled=active||position>0||unfinished;
    const seedInput=box.querySelector('[data-field="seed"]');
    seedInput.dataset.generationReadonly=String(active);
    seedInput.readOnly=active;
    box.querySelector('textarea').readOnly=active;
    box.querySelector('.clip-remove').disabled=active||unfinished;
    box.querySelector('.clip-seed-note').textContent=job?
      `${active?'Regenerating':`Queued ${position}`} with ${job.seed===undefined?'the shared seed':`seed ${job.seed}`}. Reset and New seed prepare the next take.${position?' Text and shared settings are read when this clip starts.':''}`:
      (window.voxoverSeedRandomizer?.enabled?'Randomize chooses a fresh seed per take. Edits, Reset and New seed apply to the next take.':'Defaults to the main seed. Reset copies its current value. Use -1 for random.');
    button.setAttribute('aria-label',`${generated?'Regenerate':'Generate'} paragraph ${index+1}${position?`, queued ${position}`:''}`);
    button.setAttribute('aria-busy',String(pending===box.dataset.clipId));
    if(!box.dataset.seedInitialized && Object.prototype.hasOwnProperty.call(seeds,box.dataset.clipId)){
      box.querySelector('[data-field="seed"]').value=seeds[box.dataset.clipId];
      box.dataset.seedInitialized='true';initialized=true;
    }
    if(window.voxoverSeedRandomizer?.enabled && !box.dataset.seedInitialized){
      initializeClipSeed(seedInput,otherSeeds(box));box.dataset.seedInitialized='true';initialized=true;
    }
    if(!box.dataset.seedInitialized){
      const shared=currentSharedSeed();
      if(shared!==undefined){
        seedInput.value=shared;seedInput.dataset.seedReady='false';
        box.dataset.seedInitialized='true';initialized=true;
      }
    }
    box.querySelector('.clip-seed-controls').hidden=false;
    if(!box.dataset.seedInitialized)seedInput.placeholder='Shared seed';
    box.querySelector('.clip-reset-seed').setAttribute('aria-label',`Reset seed for paragraph ${index+1} to main seed`);
    box.querySelector('.clip-new-seed').setAttribute('aria-label',`New seed for paragraph ${index+1}`);
    box.querySelector('[data-field="seed"]').setAttribute('aria-label',`Seed for paragraph ${index+1}`);
  }
  // Initialize each row once. Later server results must not overwrite an edit.
  if(initialized)snapshot();
}
function currentSharedSeed(){
  const value=document.querySelector('#generate-panel .shared-seed input')?.value;
  if(value===undefined || value==='')return undefined;
  const seed=Number(value);
  return Number.isSafeInteger(seed)&&seed>=-1?seed:undefined;
}
function otherSeeds(except){
  return [...list.querySelectorAll('.clip-row:not([data-removing])')]
    .filter(box=>box!==except && box.dataset.seedInitialized)
    .map(box=>Number(box.querySelector('[data-field="seed"]').value));
}
function prepareSeeds(randomize){
  const used=[];
  for(const box of list.querySelectorAll('.clip-row:not([data-removing])')){
    if(!randomize && !box.dataset.seedInitialized)continue;
    const input=box.querySelector('[data-field="seed"]');
    used.push(consumeClipSeed(input,randomize,[...used,...otherSeeds(box)]));
    box.dataset.seedInitialized='true';
  }
  snapshot();
  return JSON.parse(JSON.stringify(props.value));
}
function alignTimestamps(origin,message){
  const guard=window.voxoverGenerationGuard;
  if(!guard || guard.busy()){message('Wait for all active and queued generations to finish before setting timestamps.');return;}
  snapshot();
  const version=window.voxoverBatchMetadata?.version, before=JSON.stringify(props.value);
  let planned;
  try{planned=sequentialClipRows(props.value,window.voxoverBatchMetadata?.timing);}
  catch(error){message(error.message);return;}
  guard.confirmAction({title:'Set timestamps back-to-back?',
    description:'This overwrites the timestamps from the second paragraph onward using actual generated audio durations. The first timestamp stays unchanged. No audio is regenerated or combined, and your last combined audio stays available.',
    confirmLabel:'Overwrite timestamps',origin,action:()=>{
      snapshot();
      if(guard.busy() || window.voxoverBatchMetadata?.version!==version || JSON.stringify(props.value)!==before){
        message('The clips or generation queue changed. Timestamps were not overwritten. Try again when ready.');return;
      }
      const rows=[...list.querySelectorAll('.clip-row:not([data-removing])')];
      rows.forEach((box,index)=>{
        if(!index)return;
        box.querySelector('[data-field="minutes"]').value=planned[index].minutes;
        box.querySelector('[data-field="seconds"]').value=planned[index].seconds;
      });
      snapshot();message('Timestamps now follow the generated clips back-to-back. The first start is unchanged. Choose the total duration, then press Combine when ready.');
    }});
}
window.voxoverClipEditor={prepareSeeds,alignTimestamps};
window.addEventListener('voxover-randomize',()=>{
  if(window.voxoverSeedRandomizer?.enabled){
    for(const box of list.querySelectorAll('.clip-row:not([data-removing])')){
      const input=box.querySelector('[data-field="seed"]');
      // Enabling must not replace an edited next take or an immutable queued job.
      if(input.dataset.seedReady!=='true' && !window.voxoverGenerationGuard?.job(box.dataset.clipId)){
        initializeClipSeed(input,otherSeeds(box));box.dataset.seedInitialized='true';
      }
    }
  }
  snapshot();
});
window.addEventListener('voxover-clip-result',event=>{
  const box=[...list.querySelectorAll('.clip-row:not([data-removing])')].find(row=>row.dataset.clipId===event.detail.id);
  const status=box?.querySelector('.clip-operation-status');
  if(status){status.textContent=event.detail.status;status.hidden=!event.detail.status;}
});
window.addEventListener('voxover-batch',refreshRegeneration);
window.addEventListener('voxover-operation',refreshRegeneration);
for(const data of props.value || []) row(data);
snapshot();
add.addEventListener('click', () => {
  if(list.children.length>=100)return;
  snapshot();
  const previous=props.value.at(-1);
  const start=previous?Number(previous.minutes)*60+Number(previous.seconds)+5:1;
  const data={minutes:Math.floor(start/60),seconds:Number((start%60).toFixed(9)),text:''};
  const added=row(data);snapshot();added.querySelector('textarea').focus({preventScroll:true});
});

function bindImport(){
const importer=document.getElementById('clip-import');
if(!importer?.querySelector('.clip-source'))return false;
const source=importer.querySelector('.clip-source');
const split=importer.querySelector('.clip-split');
const confirm=importer.querySelector('.clip-confirm');
const status=importer.querySelector('.clip-import-status');
const undo=importer.querySelector('.clip-undo');
let previous=null;
function updateImportActions(){
  const busy=!!window.voxoverGenerationGuard?.busy();
  importer.querySelector('.clip-replace').disabled=busy;
  undo.disabled=busy;
}
window.addEventListener('voxover-operation',updateImportActions);
updateImportActions();
function message(text){status.textContent=text;status.hidden=false;}
function showConfirm(show){confirm.hidden=!show;if(show&&!matchMedia('(prefers-reduced-motion: reduce)').matches)confirm.animate([{opacity:0},{opacity:1}],{duration:180});}
function applyImport(){
  if(window.voxoverGenerationGuard?.busy()){message('Wait for generation to finish before replacing clips. You can keep editing the source script.');return;}
  try{
    const entries=paragraphRows(source.value);snapshot();previous=JSON.parse(JSON.stringify(props.value));
    list.replaceChildren();entries.forEach(row);snapshot();showConfirm(false);undo.hidden=false;
    message(`Created ${entries.length} editable clips. Source text retained. Times are rounded to the nearest second without cumulative rounding drift.`);
  }catch(error){message(error.message);}
}
split.addEventListener('click',()=>{
  try{
    paragraphRows(source.value);snapshot();
    if(props.value.some((r,index)=>r.text.trim()||r.minutes!==0||r.seconds!==(index===0?1:0))){showConfirm(true);message('Existing clips are unchanged until you confirm replacement.');}
    else applyImport();
  }catch(error){message(error.message);}
});
importer.querySelector('.clip-replace').addEventListener('click',applyImport);
importer.querySelector('.clip-cancel').addEventListener('click',()=>{showConfirm(false);message('Import cancelled. Existing clips unchanged.');});
undo.addEventListener('click',()=>{
  if(!previous||window.voxoverGenerationGuard?.busy())return;
  const current=JSON.parse(JSON.stringify(props.value));list.replaceChildren();previous.forEach(row);previous=current;snapshot();
  message('Restored the previous clips. Click again to return to the imported version.');
});

return true;
}
if(!bindImport()){
  const importMount=new MutationObserver(()=>{if(bindImport())importMount.disconnect();});
  importMount.observe(document.getElementById('production-workspace'),{childList:true,subtree:true});
}

});
