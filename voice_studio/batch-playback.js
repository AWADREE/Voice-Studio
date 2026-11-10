() => {
  if(window.voxoverBatchPlayback)return;
  let playing=false,index=-1,active=null,sequence=[],run=0,retry=null;
  const tracked=new Map();
  const regenerating=()=>window.voxoverGenerationGuard?.pending && window.voxoverGenerationGuard.pending!=='full';
  const allPlayers=()=>[...document.querySelectorAll('#batch-output .batch-audio')];
  const visible=player=>!player.closest?.('.batch-clip')?.hidden;
  const players=()=>allPlayers().filter(visible).sort((a,b)=>Number(a.closest?.('.batch-clip')?.style.gridRow||0)-Number(b.closest?.('.batch-clip')?.style.gridRow||0));
  // WaveSurfer puts its native audio element in an open shadow root. Use that
  // media API rather than translated Play/Pause labels or private Gradio state.
  function mediaIn(root){
    const candidates=[];
    function collect(scope){
      candidates.push(...scope.querySelectorAll('audio'));
      for(const node of scope.querySelectorAll('*'))if(node.shadowRoot)collect(node.shadowRoot);
    }
    collect(root);
    // Gradio also renders an unsourced light-DOM audio placeholder. It accepts
    // play() but cannot produce sound; select the sourced WaveSurfer media.
    const sourced=candidates.filter(media=>media.currentSrc||media.getAttribute('src')||media.querySelector('source[src]'));
    return sourced.sort((a,b)=>b.readyState-a.readyState)[0]||null;
  }
  const source=media=>media.currentSrc||media.getAttribute('src')||'';
  const settled=record=>!record.loading&&record.media.readyState>0&&source(record.media)===record.source;
  // WaveSurfer first seeks to zero and pauses with readyState=4, then calls
  // load() on the same element. Retain that immediately preceding state until
  // the load event proves it was a source reset rather than an ordinary seek.
  function rememberReset(record){
    if(record.restoring && record.media.currentTime>record.restoring.time+0.05)record.restoring=null;
    if(record.time>0 && record.media.currentTime===0 && !record.reset)
      record.reset={time:record.time,playing:record.playing,userPaused:record.userPaused,at:Date.now()};
    // WaveSurfer finishes decoding after loadedmetadata and can reset once more
    // without another load event. Retain recovery until playback really moves.
    if(record.restoring && record.media.currentTime===0 && record.restoring.time>0){
      loading(record);record.time=record.restoring.time;
      if(retry===null)retry=setTimeout(reconcile,50);
    }
  }
  function loading(record){
    if(record.reset && Date.now()-record.reset.at<2000){
      record.time=record.reset.time;record.playing=record.reset.playing;record.userPaused=record.reset.userPaused;
    }
    record.reset=null;record.loading=true;
  }
  const identity=player=>player?.closest?.('.batch-clip')?.id || player;
  function sameSequence(){const current=players();return current.length===sequence.length&&current.every((node,i)=>identity(node)===identity(sequence[i]));}
  function trackPlayers(){
    const current=players(),ids=new Set(current.map(identity));
    for(const [id,previous] of tracked)if(!ids.has(id)&&!regenerating()){previous.playing=false;previous.cleanup?.();tracked.delete(id);}
    for(const player of current){
      const media=mediaIn(player);if(!media)continue;
      const id=identity(player),previous=tracked.get(id);
      if(previous?.media===media && previous.source===source(media) && !previous.loading)continue;
      if(previous && media.readyState<1)continue;
      if(previous?.media===media && source(media)!==previous.source)loading(previous);
      previous?.cleanup?.();
      const record={player,media,source:source(media),loading:false,time:media.currentTime||0,playing:!media.paused};tracked.set(id,record);
      const listeners=[];
      const listen=(event,fn)=>{listeners.push([event,fn]);media.addEventListener(event,fn);};
      record.cleanup=()=>listeners.forEach(([event,fn])=>media.removeEventListener(event,fn));
      listen('play',()=>{record.playing=true;record.reset=null;});
      listen('timeupdate',()=>{rememberReset(record);if(player.isConnected!==false&&settled(record))record.time=media.currentTime;});
      listen('pause',()=>{if(player.isConnected!==false&&media.isConnected!==false&&settled(record))record.playing=false;});
      listen('ended',()=>{record.playing=false;});
      listen('emptied',()=>loading(record));
      listen('loadstart',()=>loading(record));
      listen('loadedmetadata',()=>reconcile());
      if(previous?.restoring)record.restoring=previous.restoring;
      if(previous?.playing && (!playing || identity(active?.player || player)!==id)){
        previous.playing=false;
        const offset=settled(previous)?previous.media.currentTime:previous.time;
        previous.media.pause();
        if(!Number.isFinite(media.duration)||offset<media.duration){
          try{record.restoring={time:offset};media.currentTime=offset;media.play()?.catch(()=>{});}catch(error){}
        }
      }
    }
  }
  function clearActive(){if(active){active.media.removeEventListener('ended',active.end);active.media.removeEventListener('timeupdate',active.tick);active.media.removeEventListener('pause',active.pause);active.media.removeEventListener('play',active.resume);active.media.removeEventListener('emptied',active.load);active.media.removeEventListener('loadstart',active.load);active.media.removeEventListener('loadedmetadata',active.metadata);}active=null;}
  function stop(){
    playing=false;index=-1;run++;if(retry!==null){clearTimeout(retry);retry=null;}
    const old=active?.media;clearActive();old?.pause();
    allPlayers().forEach(p=>mediaIn(p)?.pause());for(const record of tracked.values()){record.playing=false;record.reset=null;record.restoring=null;}sequence=[];
  }
  function start(i,offset=0,paused=false,restoring=false){
    if(!playing||!sameSequence()){stop();return;}
    sequence=players();
    const player=sequence[i],media=player&&mediaIn(player);
    if(!media){stop();return;}
    clearActive();index=i;const ticket=run;
    const end=()=>{if(playing&&ticket===run&&active?.media===media&&!active.userPaused&&sameSequence())start(index+1);else if(playing&&!sameSequence())stop();};
    const tick=()=>{if(active?.media===media)rememberReset(active);if(active?.media===media&&player.isConnected!==false&&media.isConnected!==false&&settled(active))active.time=media.currentTime;};
    const pause=()=>{if(active?.media===media&&!media.ended&&player.isConnected!==false&&media.isConnected!==false&&settled(active))active.userPaused=true;};
    const resume=()=>{if(active?.media===media){active.userPaused=false;active.reset=null;}};
    const load=()=>{if(active?.media===media)loading(active);};
    const metadata=()=>reconcile();
    active={player,media,source:source(media),loading:false,restoring:restoring?{time:offset}:null,end,tick,pause,resume,load,metadata,time:offset,userPaused:paused};media.addEventListener('ended',end);media.addEventListener('timeupdate',tick);media.addEventListener('pause',pause);media.addEventListener('play',resume);media.addEventListener('emptied',load);media.addEventListener('loadstart',load);media.addEventListener('loadedmetadata',metadata);
    try{
      if(paused){media.currentTime=Number.isFinite(media.duration)?Math.min(offset,media.duration):offset;return;}
      if(Number.isFinite(media.duration)&&offset>=media.duration){start(i+1);return;}
      media.currentTime=offset;
      const binding=active,promise=media.play();
      promise?.catch(()=>{if(ticket===run&&active===binding&&!binding.loading&&source(media)===binding.source)stop();});
    }catch(error){stop();}
  }
  function play(){stop();trackPlayers();sequence=players();playing=true;start(0);}
  // Existing Gradio stop callbacks may arrive after a player was replaced.
  // Native ended listeners above carry media identity; ignore stale RPC events.
  function finished(){}
  const root=document.getElementById('batch-output');
  function reconcile(){
    retry=null;
    if(!root||!root.isConnected||getComputedStyle(root).display==='none'){stop();return;}
    trackPlayers();
    // A collapsed card may have been played independently of Play all.
    // Pause only hidden players, leaving unrelated visible audio untouched.
    allPlayers().filter(player=>!visible(player)).forEach(player=>{
      const record=tracked.get(identity(player));if(record){record.playing=false;record.reset=null;record.restoring=null;}
      mediaIn(player)?.pause();
    });
    if(playing&&sequence.some(player=>!visible(player))){
      sequence=sequence.filter(visible);
      index=sequence.indexOf(active?.player);
      if(index<0){playing=false;run++;clearActive();sequence=[];}
    }
    if(playing&&!sameSequence()){
      const current=players(),activeId=identity(active?.player);
      // Adding a newly generated row extends the visible sequence. A temporary
      // empty/subset render during a replacement is not a request to stop.
      if(sequence.every(old=>current.some(node=>identity(node)===identity(old))) && current.some(node=>identity(node)===activeId)){
        sequence=current;index=current.findIndex(node=>identity(node)===activeId);
      }else if(regenerating()){if(retry===null)retry=setTimeout(reconcile,50);return;}
      else {stop();return;}
    }
    if(playing&&active){
      const current=players();
      const replacement=current[index];
      if(replacement!==active.player || (mediaIn(replacement) && (mediaIn(replacement)!==active.media || source(mediaIn(replacement))!==active.source || active.loading))){
        // Gradio can reload even unchanged sources. Keep the logical sequence,
        // use the new take for future rows, and retain an active clip's playhead.
        if(mediaIn(replacement)===active.media && source(active.media)!==active.source)loading(active);
        const offset=settled(active)?active.media.currentTime:active.time;
        if(mediaIn(replacement)?.readyState>0){
          const old=active.media,paused=active.userPaused;sequence=current;clearActive();old.pause();start(index,offset,paused,true);
        }else if(retry===null)retry=setTimeout(reconcile,50);
      }else sequence=current;
    }
  }
  const observer=new MutationObserver(reconcile);
  observer.observe(document.getElementById('listen-panel'),{childList:true,subtree:true,attributes:true,attributeFilter:['style','class','hidden']});
  // Mode visibility comes from an ancestor class, outside the Listen subtree.
  const workspace=document.getElementById('production-workspace');
  if(workspace)observer.observe(workspace,{attributes:true,attributeFilter:['class']});
  // A genuine native control interaction supersedes an earlier seek/reset.
  const userInput=event=>{
    const player=event.target.closest?.('.batch-audio');if(!player)return;
    const record=tracked.get(identity(player));if(record){record.reset=null;record.restoring=null;}
    if(active?.player===player){active.reset=null;active.restoring=null;}
  };
  document.addEventListener?.('pointerdown',userInput,true);
  document.addEventListener?.('keydown',userInput,true);
  window.addEventListener?.('voxover-operation',reconcile);
  window.voxoverBatchPlayback={play,stop,finished};
}
