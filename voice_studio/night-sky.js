() => {
  // Native Gradio selects 25%-50% of the recording. With a long waveform
  // that region is virtualized offscreen. Reveal its beginning on first click.
  document.addEventListener('click', event=>{
    const button=event.target.closest('button[aria-label="Trim audio to selection"]');
    const player=button?.closest('.studio-reference-audio');
    if(!player)return;
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      const host=Array.from(player.querySelectorAll('#waveform *')).find(e=>e.shadowRoot);
      const scroll=host?.shadowRoot.querySelector('[part=scroll]');
      if(scroll && scroll.scrollWidth>scroll.clientWidth)scroll.scrollLeft=Math.max(0,scroll.scrollWidth/4-16);
    }));
  }, true);
  const filledIcons={
    download:'M11 3h2v9h4l-5 5-5-5h4zM4 17h2v3h12v-3h2v5H4z',
    share:'M18 2a4 4 0 1 1-3.46 6L8 11.3a4 4 0 0 1 0 1.4l6.54 3.3a4 4 0 1 1-.9 1.8L7.1 14.5a4 4 0 1 1 0-5l6.54-3.3A4 4 0 0 1 18 2z',
    clear:'m6 4 6 6 6-6 2 2-6 6 6 6-2 2-6-6-6 6-2-2 6-6-6-6z',
    play:'M7 3v18l15-9z', pause:'M5 3h5v18H5zM14 3h5v18h-5z',
    back:'M11 4 1 12l10 8zM22 4l-10 8 10 8z', forward:'M2 4v16l10-8zM13 4v16l10-8z',
    volume:'M3 8h4l6-5v18l-6-5H3zM16 5v3a5 5 0 0 1 0 8v3a8 8 0 0 0 0-14z',
    mute:'M3 8h4l6-5v18l-6-5H3zM16 8l3 3 3-3 1 1-3 3 3 3-1 1-3-3-3 3-1-1 3-3-3-3z',
    undo:'M4 3v6h6L7.5 6.5A7 7 0 1 1 5 14H2a10 10 0 1 0 3.4-9.6z',
    trim:'M5 2a4 4 0 1 0 3.1 6.5L10 11l-1.9 2.5A4 4 0 1 0 9 16l3-3 8 9 2-2-8-9 8-9h-4l-6 7-3-3A4 4 0 0 0 5 2zm0 2a2 2 0 1 1 0 4 2 2 0 0 1 0-4zm0 12a2 2 0 1 1 0 4 2 2 0 0 1 0-4z',
    upload:'M11 17h2V8h4l-5-5-5 5h4zM4 17h2v3h12v-3h2v5H4z',
    mic:'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0zM5 10h2v2a5 5 0 0 0 10 0v-2h2v2a7 7 0 0 1-6 6.93V21h4v2H7v-2h4v-2.07A7 7 0 0 1 5 12z'
  };
  function polishIcons(){
    document.querySelectorAll('.gradio-container button[aria-label]').forEach(b=>{
      const label=b.getAttribute('aria-label')||'';
      const key=label==='Download'?'download':label==='Share'?'share':label==='Clear'?'clear':label==='Play'?'play':label==='Pause'?'pause':label.startsWith('Skip backwards')?'back':label.startsWith('Skip forward')?'forward':label==='Reset audio'?'undo':label==='Trim audio to selection'?'trim':label==='Upload file'?'upload':label==='Record audio'?'mic':label==='Adjust volume'?(b.querySelector('svg:not(.studio-glyph) title')?.textContent?.toLowerCase().includes('muted')?'mute':'volume'):null;
      if(!key)return;
      b.classList.add('studio-filled-icon');
      let svg=b.querySelector('.studio-glyph');
      if(!svg){svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('studio-glyph');b.append(svg);}
      if(svg.dataset.icon!==key){svg.dataset.icon=key;svg.innerHTML='<path d="'+filledIcons[key]+'"/>';}
    });
  }
  // Parent mode layout is not a child entering/leaving or changing its content.
    const referenceLayoutBusy = el => Boolean(el.closest('#reference-panel') && document.querySelector('#voice-mode-workspace')?.matches('.generate-mode,.mode-transitioning'));
    const presenceState=new WeakMap();
  function animatePresence(){
    document.querySelectorAll('.studio-output-status,#correction-editor,.studio-wav-output,.studio-presence').forEach(el=>{
      if(el.parentElement.closest('.studio-output-status') || referenceLayoutBusy(el))return;
      const prior=presenceState.get(el);
      if(prior?.animating)return;
      const visible=getComputedStyle(el).display!=='none'&&el.getBoundingClientRect().height>0;
      const height=el.getBoundingClientRect().height;
      const state={visible,height,exiting:false};presenceState.set(el,state);
      if(!prior||prior.visible===visible||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
      let frames;
      if(visible){frames=[{height:'0px',opacity:0,minHeight:'0px',overflow:'clip'},{height:height+'px',opacity:1,minHeight:'0px',overflow:'clip'}];}
      else{
        if(!el.isConnected||el.parentElement.getBoundingClientRect().height===0)return;
        state.exiting=true;el.style.setProperty('display','block','important');el.inert=true;
        frames=[{height:prior.height+'px',opacity:1,minHeight:'0px',overflow:'clip'},{height:'0px',opacity:0,minHeight:'0px',overflow:'clip'}];
      }
      state.animating=true;
      const animation=el.animate(frames,{duration:180,easing:'cubic-bezier(.2,.8,.2,1)'});
      const samples=[];const sample=()=>{samples.push([Math.round(el.getBoundingClientRect().height),Number(getComputedStyle(el).opacity)]);if(animation.playState==='running')requestAnimationFrame(sample);else el.dataset.presenceMotion=JSON.stringify(samples);};requestAnimationFrame(sample);
      animation.onfinish=()=>{if(state.exiting){el.style.removeProperty('display');el.inert=false;state.exiting=false;}state.height=visible?el.getBoundingClientRect().height:0;state.animating=false;requestAnimationFrame(animatePresence);};
    });
  }
  document.addEventListener('change',()=>requestAnimationFrame(animatePresence),true);
  function animateDrawer(dialog,closing,done){
    const panel=dialog.querySelector('.api-docs-wrap');
    if(!panel||matchMedia('(prefers-reduced-motion: reduce)').matches){done?.();return;}
    const animation=panel.animate(closing?[{transform:'translateX(0)',opacity:1},{transform:'translateX(100%)',opacity:0}]:[{transform:'translateX(100%)',opacity:0},{transform:'translateX(0)',opacity:1}],{duration:180,easing:'cubic-bezier(.2,.8,.2,1)',fill:closing?'forwards':'none'});
    const samples=[];const sample=()=>{samples.push(Math.round(panel.getBoundingClientRect().x));if(animation.playState==='running')requestAnimationFrame(sample);else document.documentElement.dataset.drawerMotion=JSON.stringify({closing,samples});};requestAnimationFrame(sample);
    animation.onfinish=()=>done?.();
  }
  function polishDrawers(){
    document.querySelectorAll('.api-docs[role=dialog]').forEach(d=>{
      const closeNow=d.querySelector('.banner-wrap button');if(closeNow)closeNow.setAttribute('aria-label','Close panel');
      if(d.dataset.studioDrawer)return;d.dataset.studioDrawer='true';
      animateDrawer(d,false);
      d.addEventListener('click',e=>{
        if(d.dataset.allowClose)return;
        if(!e.target.closest('.banner-wrap button,.backdrop'))return;
        e.preventDefault();e.stopImmediatePropagation();
        if(d.dataset.closing)return;d.dataset.closing='true';
        animateDrawer(d,true,()=>{d.dataset.allowClose='true';d.querySelector('.banner-wrap button')?.click();});
      },true);
      d.addEventListener('keydown',e=>{if(e.key==='Escape'&&!d.dataset.allowClose){e.preventDefault();e.stopImmediatePropagation();d.querySelector('.banner-wrap button')?.click();}},true);
    });
  }
  let storageReturnFocus=null;
  function polishStorageDialog(){
    const d=document.querySelector('#storage-picker-dialog');if(!d)return;
    d.setAttribute('role','dialog');d.setAttribute('aria-modal','true');d.setAttribute('aria-label','Choose a storage folder');
    const visible=d.getBoundingClientRect().height>0;
    if(visible&&d.dataset.open!=='true'){storageReturnFocus=document.activeElement;d.querySelector('textarea,input')?.focus();}
    if(!visible&&d.dataset.open==='true')storageReturnFocus?.focus();
    d.dataset.open=String(visible);
  }
  document.addEventListener('keydown',e=>{
    const d=document.querySelector('#storage-picker-dialog');if(!d||d.getBoundingClientRect().height===0)return;
    if(e.key==='Escape'){e.preventDefault();d.querySelector('#cancel-storage-picker')?.click();}
    if(e.key==='Tab'){
      const items=Array.from(d.querySelectorAll('button,input,textarea,[tabindex="0"]')).filter(x=>!x.disabled&&x.getBoundingClientRect().height>0);
      const first=items[0],last=items[items.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
    }
  },true);
  document.addEventListener('pointerdown',e=>{const d=document.querySelector('#storage-picker-dialog');if(d?.getBoundingClientRect().height>0&&!d.contains(e.target)){e.preventDefault();e.stopImmediatePropagation();d.querySelector('#cancel-storage-picker')?.click();}},true);
  const pickerGeometry=new WeakMap();
  function animatePickerGeometry(){
    document.querySelectorAll('.studio-reference-audio,.studio-voice-input,.studio-audio-output').forEach(el=>{
      if(referenceLayoutBusy(el))return;
      const prior=pickerGeometry.get(el);
      const source=el.querySelector('.source-selection button.selected')?.getAttribute('aria-label')||'';
      const body=el.querySelector('.audio-container');
      const current=el.getBoundingClientRect().height;
      const bodyCurrent=body?.getBoundingClientRect().height;
      if(prior?.animation)prior.animation.cancel();
      if(prior?.bodyAnimation)prior.bodyAnimation.cancel();
      const target=el.getBoundingClientRect().height;
      const bodyTarget=body?.getBoundingClientRect().height;
      const from=prior?.animation?current:prior?.height;
      const bodyFrom=prior?.bodyAnimation?bodyCurrent:prior?.bodyHeight;
      const entry={height:target,bodyHeight:bodyTarget,source,animation:null,bodyAnimation:null};pickerGeometry.set(el,entry);
      if(from==null||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
      const timing={duration:220,easing:'cubic-bezier(.2,.8,.2,1)'};
      if(body && bodyFrom!=null && Math.abs(bodyTarget-bodyFrom)>=2){
        entry.bodyAnimation=body.animate([{height:bodyFrom+'px',minHeight:'0px',overflow:'clip'},{height:bodyTarget+'px',minHeight:'0px',overflow:'clip'}],timing);
        entry.bodyAnimation.onfinish=()=>{entry.bodyAnimation=null;};
      }
      if(Math.abs(target-from)<2)return;
      entry.animation=el.animate([{height:from+'px',minHeight:'0px',overflow:'clip'},{height:target+'px',minHeight:'0px',overflow:'clip'}],timing);
      const samples=[];
      const sample=()=>{samples.push(Math.round(el.getBoundingClientRect().height*100)/100);if(entry.animation?.playState==='running')requestAnimationFrame(sample);else el.dataset.pickerMotion=JSON.stringify(samples);};
      requestAnimationFrame(sample);
      entry.animation.onfinish=()=>{entry.animation=null;};
    });
  }
  const polishFiles=()=>{
    requestAnimationFrame(animatePickerGeometry);
    requestAnimationFrame(animatePresence);
    polishIcons();
    polishDrawers();
    polishStorageDialog();
    document.querySelectorAll('.studio-reference-audio .source-selection').forEach(group=>{
      group.setAttribute('role','group');group.setAttribute('aria-label','Reference audio source');
      group.querySelectorAll('button').forEach(b=>{
        const label=b.getAttribute('aria-label');
        if(label!=='Upload file'&&label!=='Record audio')return;
        let text=b.querySelector('.studio-source-label');
        if(!text){text=document.createElement('span');text.className='studio-source-label';b.appendChild(text);}
        text.textContent=label==='Upload file'?'Upload':'Microphone';
        b.setAttribute('aria-pressed',String(b.classList.contains('selected')));
      });
    });
    document.querySelectorAll('button[aria-dropeffect] .icon-wrap').forEach(w=>{
      if(w.querySelector('.studio-dropzone-glyph'))return;
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('studio-dropzone-glyph');svg.innerHTML='<path d="'+filledIcons.upload+'"/>';w.append(svg);
    });
    document.querySelectorAll('.studio-voice-input td a').forEach(a=>{a.removeAttribute('href');a.removeAttribute('download');a.setAttribute('tabindex','-1');a.setAttribute('role','text');a.classList.add('studio-static-size');if(a.textContent.includes('\u21e3'))a.textContent=a.textContent.replace('\u21e3','').trim();});
    document.querySelectorAll('.studio-output-status').forEach(e=>{if(!e.parentElement.closest('.studio-output-status')){e.setAttribute('role','status');e.setAttribute('aria-live','polite');e.setAttribute('aria-atomic','true');}e.classList.toggle('has-status',Boolean((e.querySelector('[data-testid=markdown]') || e).querySelector('.md')?.textContent.trim()));});
    document.querySelectorAll('.studio-wav-output td a').forEach(a=>{
      if(a.dataset.studioDownload)return;a.dataset.studioDownload='true';
      const size=document.createElement('span');size.className='studio-file-size';size.textContent=a.textContent.replace('\u21e3','').trim();
      a.textContent='Download WAV';a.append(size);a.setAttribute('aria-label','Download generated commentary WAV');a.classList.add('studio-download-link');
    });
  };
  if(!document.documentElement.dataset.filePolishBound){
    document.documentElement.dataset.filePolishBound='true';
    const obs=new MutationObserver(()=>{obs.disconnect();polishFiles();obs.observe(document.querySelector('.gradio-container'),{childList:true,subtree:true,attributes:true,attributeFilter:['aria-label','class']});});
    polishFiles();obs.observe(document.querySelector('.gradio-container'),{childList:true,subtree:true,attributes:true,attributeFilter:['aria-label','class']});
  }

  const focusRoot = document.querySelector('.gradio-container');
  if(focusRoot && !focusRoot.dataset.focusModeBound){
    focusRoot.dataset.focusModeBound='true';
    document.addEventListener('keydown', e=>{if(e.key==='Tab')focusRoot.classList.add('keyboard-navigation');},true);
    document.addEventListener('pointerdown', ()=>focusRoot.classList.remove('keyboard-navigation'),true);
  }

    // Keep both forms mounted; mode switching changes presentation only.
    const modeNav = document.querySelector('#voice-mode-tabs');
    const workspace = document.querySelector('#voice-mode-workspace');
    const reference = document.querySelector('#reference-panel');
    if (modeNav && workspace && reference && !modeNav.dataset.bound) {
        modeNav.dataset.bound = 'true';
        let modeTimer;
        modeNav.addEventListener('click', event => {
            const button = event.target.closest('button[data-voice-mode]');
            if (!button) return;
            const generate = button.dataset.voiceMode === 'generate';
            if(generate === workspace.classList.contains('generate-mode'))return;
            clearTimeout(modeTimer);
            // Freeze the inner form at its expanded width in BOTH directions.
            // Otherwise the expanding zero-width grid rewraps the source tabs,
            // and the picker animator preserves that temporary extra row.
            const narrow = matchMedia('(max-width:800px)').matches;
            const panelWidth = narrow ? workspace.clientWidth : (workspace.clientWidth - 24) / 2;
            workspace.style.setProperty('--reference-content-width', Math.max(0, panelWidth - 48) + 'px');
            workspace.classList.add('mode-transitioning');
            reference.querySelectorAll('.studio-reference-audio').forEach(el=>{
                const old=pickerGeometry.get(el);
                old?.animation?.cancel();old?.bodyAnimation?.cancel();
                pickerGeometry.delete(el);
            });
            modeTimer=setTimeout(()=>{
                workspace.classList.remove('mode-transitioning');
                reference.querySelectorAll('.studio-reference-audio').forEach(el=>pickerGeometry.delete(el));
                requestAnimationFrame(animatePickerGeometry);
            },matchMedia('(prefers-reduced-motion: reduce)').matches?0:260);
            workspace.classList.toggle('generate-mode', generate);
            reference.inert = generate;
            reference.setAttribute('aria-hidden', String(generate));
            modeNav.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
        });
    }

    // Original procedural backdrop for this distributable UI. No borrowed artwork.
    document.documentElement.classList.add('dark');
    document.querySelectorAll('.star-sky,.sky-twinkles').forEach(e=>e.remove());
    if(window.__qwenSkyCleanup)window.__qwenSkyCleanup();
    const c=document.createElement('canvas');c.className='star-sky';document.body.appendChild(c);
    const ctx=c.getContext('2d'), reduced=matchMedia('(prefers-reduced-motion: reduce)');
    const stars=Array.from({length:180},()=>({x:Math.random(),y:Math.random(),r:.4+Math.random()*1.1,p:Math.random()*6.28}));
    let frame=0,last=0;
    function paint(t){
      const w=innerWidth,h=innerHeight,d=Math.min(devicePixelRatio||1,2);
      if(c.width!==Math.round(w*d)||c.height!==Math.round(h*d)){c.width=Math.round(w*d);c.height=Math.round(h*d);}
      ctx.setTransform(d,0,0,d,0,0);
      const g=ctx.createLinearGradient(0,0,w,h);g.addColorStop(0,'#060d19');g.addColorStop(.6,'#101d32');g.addColorStop(1,'#080e19');ctx.fillStyle=g;ctx.fillRect(0,0,w,h);
      for(const s of stars){ctx.fillStyle=`rgba(190,214,237,${reduced.matches?.35:.25+.15*Math.sin(t/5000+s.p)})`;ctx.beginPath();ctx.arc(s.x*w,s.y*h,s.r,0,Math.PI*2);ctx.fill();}
    }
    function tick(t){if(document.hidden)return;if(t-last>40){paint(t);last=t;}if(!reduced.matches)frame=requestAnimationFrame(tick);}
    function refresh(){cancelAnimationFrame(frame);paint(0);if(!document.hidden&&!reduced.matches)frame=requestAnimationFrame(tick);}
    window.addEventListener('resize',refresh);document.addEventListener('visibilitychange',refresh);reduced.addEventListener('change',refresh);refresh();
    window.__qwenSkyCleanup=()=>{cancelAnimationFrame(frame);window.removeEventListener('resize',refresh);document.removeEventListener('visibilitychange',refresh);reduced.removeEventListener('change',refresh);c.remove();};
}
