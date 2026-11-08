() => {
  if(window.voiceStudioBatchPlayback)return;
  let playing=false,index=-1;
  const players=()=>[...document.querySelectorAll('#batch-output .batch-audio')];
  function stop(){playing=false;index=-1;players().forEach(p=>p.querySelector('button[aria-label="Pause"]')?.click());}
  function start(i){
    const player=players()[i];
    if(!player){stop();return;}
    index=i;
    const play=player.querySelector('button[aria-label="Play"]');
    if(play)play.click();else if(!player.querySelector('button[aria-label="Pause"]'))stop();
  }
  function play(){stop();playing=true;start(0);}
  function finished(i){if(playing&&i===index)start(i+1);}
  const root=document.getElementById('batch-output');
  new MutationObserver(()=>{if(playing&&(!root||!root.isConnected||getComputedStyle(root).display==='none'||!players()[index]))stop();}).observe(document.getElementById('listen-panel'),{childList:true,subtree:true,attributes:true,attributeFilter:['style','class']});
  window.voiceStudioBatchPlayback={play,stop,finished};
}
