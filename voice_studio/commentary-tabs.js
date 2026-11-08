() => {
  const root=document.getElementById('commentary-mode-tabs');
  if(!root || root.dataset.presenceBound)return;
  root.dataset.presenceBound='true';
  const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  let pending=null, animation=null, cleanup=null;
  function clear(){ if(animation)animation.cancel();animation=null;if(cleanup)cleanup();cleanup=null; }
  root.addEventListener('click',event=>{
    const button=event.target.closest('[role="tab"]');
    if(!button || button.getAttribute('aria-selected')==='true')return;
    const height=root.getBoundingClientRect().height;
    clear();
    pending={height};
  },true);
  const observer=new MutationObserver(()=>{
    if(!pending)return;
    const start=pending.height;pending=null;
    requestAnimationFrame(()=>{
      const end=root.getBoundingClientRect().height;
      if(reduced() || Math.abs(start-end)<1)return;
      const timing={duration:220,easing:'cubic-bezier(.2,.7,.2,1)'};
      animation=root.animate([{height:start+'px',overflow:'clip'},{height:end+'px',overflow:'clip'}],timing);
      const panels=[...root.children].filter(el=>el.getAttribute('role')==='tabpanel'||el.classList.contains('tabitem'));
      const active=panels.find(el=>getComputedStyle(el).display!=='none');
      if(active)active.animate([{opacity:0,transform:'translateY(4px)'},{opacity:1,transform:'translateY(0)'}],timing);
      animation.onfinish=()=>{animation=null;};
    });
  });
  observer.observe(root,{subtree:true,attributes:true,attributeFilter:['aria-selected','style','class']});
}
