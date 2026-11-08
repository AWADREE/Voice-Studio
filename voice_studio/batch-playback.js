() => {
  if(window.voiceStudioBatchPlayback)return;
  let playing=false,index=-1,active=null,sequence=[],run=0;
  const players=()=>[...document.querySelectorAll('#batch-output .batch-audio')];
  // WaveSurfer puts its native audio element in an open shadow root. Use that
  // media API rather than translated Play/Pause labels or private Gradio state.
  function mediaIn(root){
    const direct=root.querySelector('audio');if(direct)return direct;
    for(const node of root.querySelectorAll('*'))if(node.shadowRoot){const media=mediaIn(node.shadowRoot);if(media)return media;}
    return null;
  }
  function sameSequence(){const current=players();return current.length===sequence.length&&current.every((node,i)=>node===sequence[i]);}
  function clearActive(){if(active)active.media.removeEventListener('ended',active.end);active=null;}
  function stop(){
    playing=false;index=-1;run++;
    const old=active?.media;clearActive();old?.pause();
    players().forEach(p=>mediaIn(p)?.pause());sequence=[];
  }
  function start(i){
    if(!playing||!sameSequence()){stop();return;}
    const player=sequence[i],media=player&&mediaIn(player);
    if(!media){stop();return;}
    clearActive();index=i;const ticket=run;
    const end=()=>{if(playing&&ticket===run&&active?.media===media&&sameSequence())start(i+1);else if(playing&&!sameSequence())stop();};
    active={player,media,end};media.addEventListener('ended',end);
    try{
      media.currentTime=0;
      const promise=media.play();
      promise?.catch(()=>{if(ticket===run&&active?.media===media)stop();});
    }catch(error){stop();}
  }
  function play(){stop();sequence=players();playing=true;start(0);}
  // Existing Gradio stop callbacks may arrive after a player was replaced.
  // Native ended listeners above carry media identity; ignore stale RPC events.
  function finished(){}
  const root=document.getElementById('batch-output');
  new MutationObserver(()=>{if(playing&&(!root||!root.isConnected||getComputedStyle(root).display==='none'||!sameSequence()))stop();}).observe(document.getElementById('listen-panel'),{childList:true,subtree:true,attributes:true,attributeFilter:['style','class']});
  window.voiceStudioBatchPlayback={play,stop,finished};
}
