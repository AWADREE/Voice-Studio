() => {
  if (window.voiceStudioOperationFeedback) return;
  window.voiceStudioOperationFeedback=true;
  const refresh=()=>{
    document.querySelectorAll('button').forEach(button=>{
      const busy=/^(Generating commentary|Cloning & generating|Saving voice|Saving new voice|Unloading model|Saving folder)\.\.\.$/.test(button.textContent.trim());
      // Svelte may update disabled before replacing the busy label. Our busy
      // guard must undo that transient override when the final label arrives.
      const wasBusy=button.getAttribute('aria-busy')==='true';
      if(busy&&!button.disabled)button.disabled=true;
      if(!busy&&wasBusy&&/^(Unload experimental model|Save as new voice \.pt|Save voice file|Use this folder|Clone reference & generate commentary)$/.test(button.textContent.trim()))button.disabled=false;
      if(button.getAttribute('aria-busy')!==String(busy))button.setAttribute('aria-busy',String(busy));
      button.classList.toggle('studio-operation-busy',busy);
    });
    document.querySelectorAll('.studio-output-status').forEach(status=>{
      if(status.getAttribute('role')!=='status')status.setAttribute('role','status');
      if(status.getAttribute('aria-live')!=='polite')status.setAttribute('aria-live','polite');
    });
  };
  new MutationObserver(refresh).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['disabled']});
  refresh();
}