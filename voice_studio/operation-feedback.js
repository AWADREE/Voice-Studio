() => {
  if (window.voiceStudioOperationFeedback) return;
  window.voiceStudioOperationFeedback=true;
  const refresh=()=>{
    document.querySelectorAll('button').forEach(button=>{
      const busy=/^(Generating commentary|Cloning & generating|Saving voice|Saving new voice|Unloading model|Saving folder)\.\.\.$/.test(button.textContent.trim());
      if(busy&&!button.disabled)button.disabled=true;
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