() => {
  if (window.voiceStudioBatchPlayback) return;
  let run=0, cancel=null;
  const players=()=>[...document.querySelectorAll('#batch-output .batch-audio audio')];
  function stop(){run++; if(cancel)cancel(); players().forEach(a=>a.pause());}
  async function play(){
    stop(); const ticket=run;
    for(const audio of players()){
      if(ticket!==run || !audio.isConnected)break;
      audio.currentTime=0;
      let finish;
      const ended=new Promise(resolve=>{
        finish=()=>{audio.removeEventListener('ended',finish);audio.removeEventListener('error',fail);audio.removeEventListener('pause',paused);if(cancel===finish)cancel=null;resolve();};
        const fail=()=>{run++;finish();};
        const paused=()=>{if(!audio.ended){run++;finish();}};
        audio.addEventListener('ended',finish);audio.addEventListener('error',fail);audio.addEventListener('pause',paused);cancel=finish;
      });
      try{await audio.play();await ended;}catch(_){finish();stop();break;}
    }
  }
  new MutationObserver(()=>{if(cancel && !players().some(a=>!a.paused))stop();}).observe(document.getElementById('listen-panel'),{childList:true,subtree:true});
  window.voiceStudioBatchPlayback={play,stop};
}
