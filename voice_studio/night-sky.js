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
      if(el.matches('.studio-output-status') || el.parentElement.closest('.studio-output-status') || referenceLayoutBusy(el))return;
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
      const voiceSelection=el.matches('.studio-voice-input')?Boolean(el.querySelector('.file-preview-holder')):null;
      if(voiceSelection!==null&&prior?.voiceSelection===voiceSelection)return;
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
      const entry={height:target,bodyHeight:bodyTarget,source,voiceSelection,animation:null,bodyAnimation:null};pickerGeometry.set(el,entry);
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
  // Keep the outgoing status painted until its layout space has collapsed.
  // Gradio clears its Markdown before toggling visibility, so height-only animation
  // cannot preserve the old content without this inert visual snapshot.
  const statusPresence=new WeakMap();
  function polishStatusPresence(){
    [...document.querySelectorAll('.studio-output-status')].reverse().forEach(el=>{
      if(el.closest('[data-status-ghost]'))return;
      if(el.parentElement.closest('.studio-output-status')){el.classList.toggle('has-status',Boolean(el.textContent.trim()));return;}
      el.setAttribute('role','status');el.setAttribute('aria-live','polite');el.setAttribute('aria-atomic','true');
      const content=el.querySelector('.md:not([data-status-ghost])');
      const clearedVoice=el.id==='selected-voice-status'&&!document.querySelector('.studio-voice-input .file-preview-holder');
      const text=clearedVoice?'':content?.textContent.trim()||'';
      const prior=statusPresence.get(el);
      if(prior?.text===text)return;
      const from=(!text?prior?.height:el.getBoundingClientRect().height)||prior?.height||0;
      prior?.animation?.cancel();prior?.ghost?.remove();
      el.style.removeProperty('display');el.style.removeProperty('overflow');el.style.removeProperty('padding');
      el.classList.toggle('has-status',Boolean(text));
      content?.style.removeProperty('display');
      const state={text,height:el.getBoundingClientRect().height,content:content?.cloneNode(true)};
      statusPresence.set(el,state);
      if(!prior||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
      const gap=parseFloat(getComputedStyle(el.parentElement).rowGap)||0;
      if(!text&&prior.content){
        state.ghost=prior.content;state.ghost.dataset.statusGhost='true';state.ghost.setAttribute('aria-hidden','true');state.ghost.inert=true;
        if(content)content.style.setProperty('display','none','important');
        el.append(state.ghost);el.style.setProperty('display','block','important');
        el.classList.add('has-status');el.style.setProperty('padding','0','important');state.ghost.style.padding='10px 12px';
      }
      el.style.overflow='clip';
      const target=text?state.height:0;
      state.animation=el.animate([
        {height:from+'px',minHeight:'0px',opacity:prior.text?1:0,marginBottom:prior.text?'0px':-gap+'px',boxSizing:'border-box'},
        {height:target+'px',minHeight:'0px',opacity:text?1:0,marginBottom:text?'0px':-gap+'px',paddingTop:text?'10px':'0px',paddingBottom:text?'10px':'0px',boxSizing:'border-box'}
      ],{duration:220,easing:'cubic-bezier(.2,.8,.2,1)'});
      const samples=[];const sample=()=>{samples.push(Math.round(el.getBoundingClientRect().height*100)/100);if(state.animation?.playState==='running')requestAnimationFrame(sample);else el.dataset.statusMotion=JSON.stringify(samples);};requestAnimationFrame(sample);
      state.animation.onfinish=()=>{
        if(statusPresence.get(el)!==state)return;
        state.ghost?.remove();content?.style.removeProperty('display');el.style.removeProperty('display');el.style.removeProperty('overflow');el.style.removeProperty('padding');
        el.classList.toggle('has-status',Boolean(text));state.animation=null;
      };
    });
  }
  const polishFiles=()=>{
    animatePickerGeometry();
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
    polishStatusPresence();
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
                animatePickerGeometry();
            },matchMedia('(prefers-reduced-motion: reduce)').matches?0:260);
            workspace.classList.toggle('generate-mode', generate);
            reference.inert = generate;
            reference.setAttribute('aria-hidden', String(generate));
            modeNav.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
        });
    }

    if (window.__qwenSkyCleanup)
        window.__qwenSkyCleanup();
    document.querySelectorAll('.star-sky,.sky-twinkles').forEach(e => e.remove());
    document.documentElement.classList.add('dark');
    /** Stable seeded variation: hydration matches, each star/cycle gets a distinct bounded peak. */
    function starCyclePeak(star, cycle) { let n = Math.imul(star + 1, 374761393) ^ Math.imul(cycle + 1, 668265263); n = Math.imul(n ^ (n >>> 13), 1274126177); return .46 + (((n ^ (n >>> 16)) >>> 0) / 4294967295) * .44; }
    function starTwinkleAlpha(star, time, period, phase, reduced) { if (reduced)
        return .35; const position = time / period + phase; const cycle = Math.floor(position), fraction = position - cycle; return .12 + (starCyclePeak(star, cycle) - .12) * (.5 - .5 * Math.cos(2 * Math.PI * fraction)); }
    const SKY_STAR_COUNT = 750;
    function starInitialPhase(star) { return Math.min(.999999, (starCyclePeak(star + 729, 17) - .46) / .44); }
    /** Find compact bright sources; broad luminous gas is deliberately excluded. */
    function findRasterStars(data, width, height) {
        const visited = new Uint8Array(width * height), stars = [];
        const bright = (i) => data[i * 4 + 3] > 0 && (.2126 * data[i * 4] + .7152 * data[i * 4 + 1] + .0722 * data[i * 4 + 2]) > 118;
        for (let i = 0; i < width * height; i++) {
            if (visited[i] || !bright(i))
                continue;
            const queue = [i];
            visited[i] = 1;
            let sumX = 0, sumY = 0, minX = width, maxX = 0, minY = height, maxY = 0;
            for (let at = 0; at < queue.length; at++) {
                const j = queue[at], x = j % width, y = Math.floor(j / width);
                sumX += x;
                sumY += y;
                minX = Math.min(minX, x);
                maxX = Math.max(maxX, x);
                minY = Math.min(minY, y);
                maxY = Math.max(maxY, y);
                for (const [nx, ny] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
                    if (nx < 0 || ny < 0 || nx >= width || ny >= height)
                        continue;
                    const k = ny * width + nx;
                    if (!visited[k] && bright(k)) {
                        visited[k] = 1;
                        queue.push(k);
                    }
                }
            }
            if (queue.length > 90 || maxX - minX > 18 || maxY - minY > 18)
                continue;
            const x = sumX / queue.length, y = sumY / queue.length, seed = ((Math.round(x) * 73856093) ^ (Math.round(y) * 19349663)) >>> 0;
            stars.push({ x, y, radius: Math.max(2, Math.min(11, Math.max(maxX - minX, maxY - minY) * .7 + 2)), phase: (seed % 6283) / 1000, period: 12000 + seed % 14000 });
        }
        return stars;
    }
    /** Always retains at least22% of the original core; independent8ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“16s cycles, no positional motion. */
    function rasterStarDimming(star, time, reduced) { return reduced ? 0 : .39 * (1 + Math.sin(time * Math.PI * 2 / star.period + star.phase)); }
    function drawRasterShimmer(context, stars, time, reduced, scaleX, scaleY) {
        if (reduced)
            return;
        for (const [index, star] of stars.entries()) {
            const amount = rasterStarDimming(star, time, false), x = star.x * scaleX, y = star.y * scaleY, r = star.radius * Math.max(scaleX, scaleY);
            const mask = context.createRadialGradient(x, y, 0, x, y, r);
            mask.addColorStop(0, 'rgba(0,0,0,' + amount + ')');
            mask.addColorStop(.35, 'rgba(0,0,0,' + amount * .8 + ')');
            mask.addColorStop(1, 'rgba(0,0,0,0)');
            void mask;
            const bloom = context.createRadialGradient(x, y, 0, x, y, r * 1.3);
            const light = starTwinkleAlpha(index, time, star.period, star.phase / (Math.PI * 2), false) * .4;
            bloom.addColorStop(0, 'rgba(225,240,255,' + light + ')');
            bloom.addColorStop(.25, 'rgba(180,215,255,' + light * .35 + ')');
            bloom.addColorStop(1, 'rgba(180,215,255,0)');
            context.fillStyle = bloom;
            context.fillRect(x - r * 1.3, y - r * 1.3, r * 2.6, r * 2.6);
        }
    }
    function skyRandom(i, salt) { let n = Math.imul(i + 1, 374761393) ^ salt; n = Math.imul(n ^ (n >>> 13), 1274126177); return ((n ^ (n >>> 16)) >>> 0) / 4294967295; }
    const canvas = document.createElement('canvas');
    canvas.className = 'star-sky';
    document.body.appendChild(canvas);
    const context = canvas?.getContext('2d', { alpha: false });
    const overlay = document.createElement('canvas');
    overlay.className = 'star-sky star-sky--shimmer';
    document.body.appendChild(overlay);
    const shimmer = overlay?.getContext('2d');
    if (!canvas || !context || !overlay || !shimmer)
        return;
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    let width = 0, height = 0, frame = 0, resizeFrame = 0, last = 0;
    let stars = [];
    const sky = document.createElement('canvas');
    const skyContext = sky.getContext('2d', { alpha: false });
    if (!skyContext)
        return;
    // ART_DRIFT_GEOMETRY_BEGIN
    function artCoverBounds(vw,vh,iw,ih){
      const scale=Math.max(vw/iw,vh/ih)*1.08;
      const w=iw*scale,h=ih*scale;
      return {w,h,x:Math.max(0,Math.min(48,(w-vw)/2-2)),y:Math.max(0,Math.min(48,(h-vh)/2-2))};
    }
    function artEase(t){return t*t*t*(t*(t*6-15)+10);}
    // ART_DRIFT_GEOMETRY_END
    let driftFrom={x:0,y:0},driftTo={x:0,y:0},driftPos={x:0,y:0};
    let driftElapsed=0,driftDuration=0,driftLast=0,driftDiagnostic=0;
    function nextDrift(){
      driftFrom={...driftPos};
      driftTo={x:(Math.random()*2-1)*.9,y:(Math.random()*2-1)*.9};
      // Quintic derivative peaks at1.875; this duration caps planar speed .70px/s
      // even at maximum48px bounds and after resizing.
      const distance=Math.hypot(driftTo.x-driftFrom.x,driftTo.y-driftFrom.y)*48;
      driftDuration=Math.max(60000+Math.random()*45000,distance*1.875/.70*1000);
      driftElapsed=0;
    }
    nextDrift();
    function driftArtwork(time){
      const bounds=artCoverBounds(width,height,image.naturalWidth,image.naturalHeight);
      if(!motion.matches&&!document.hidden&&time>0){
        if(driftLast)driftElapsed+=Math.min(100,Math.max(0,time-driftLast));
        driftLast=time;
        if(driftElapsed>=driftDuration){driftPos={...driftTo};nextDrift();}
        const e=artEase(Math.min(1,driftElapsed/driftDuration));
        driftPos={x:driftFrom.x+(driftTo.x-driftFrom.x)*e,y:driftFrom.y+(driftTo.y-driftFrom.y)*e};
      }
      const x=(width-bounds.w)/2+driftPos.x*bounds.x;
      const y=(height-bounds.h)/2+driftPos.y*bounds.y;
      context.drawImage(image,x,y,bounds.w,bounds.h);
      if(time-driftDiagnostic>1000||time===0){
        canvas.dataset.artDrift=JSON.stringify({x,y,w:bounds.w,h:bounds.h,vw:width,vh:height,bx:bounds.x,by:bounds.y,elapsed:driftElapsed,duration:driftDuration});driftDiagnostic=time;
      }
    }
    const image = new Image();
    let imageReady = false;
    let rasterStars = [];
    let disposed = false;
    let seed = 91473;
    const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
    const hash = (x, y) => {
        let n = Math.imul(x, 374761393) + Math.imul(y, 668265263);
        n = Math.imul(n ^ (n >>> 13), 1274126177);
        return ((n ^ (n >>> 16)) >>> 0) / 4294967295;
    };
    const noise = (x, y) => {
        const ix = Math.floor(x), iy = Math.floor(y);
        const a = x - ix, b = y - iy, u = a * a * (3 - 2 * a), v = b * b * (3 - 2 * b);
        return (hash(ix, iy) * (1 - u) + hash(ix + 1, iy) * u) * (1 - v)
            + (hash(ix, iy + 1) * (1 - u) + hash(ix + 1, iy + 1) * u) * v;
    };
    const fractal = (x, y) => noise(x, y) * .53 + noise(x * 2.07, y * 2.07) * .27
        + noise(x * 4.13, y * 4.13) * .13 + noise(x * 8.3, y * 8.3) * .07;
    function rebuild() {
        width = Math.max(1, window.innerWidth);
        height = Math.max(1, window.innerHeight);
        const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        context.setTransform(dpr, 0, 0, dpr, 0, 0);
        overlay.width = canvas.width;
        overlay.height = canvas.height;
        shimmer.setTransform(dpr, 0, 0, dpr, 0, 0);
        // Cache the expensive gas field at a bounded resolution; animate only stars.
        sky.width = Math.min(760, Math.round(width));
        sky.height = Math.min(600, Math.max(1, Math.round(sky.width * height / width)));
        if (imageReady) {
            // Cache cover composition at capped display resolution to retain tiny asset stars.
            sky.width = canvas.width;
            sky.height = canvas.height;
            const scale = Math.max(sky.width / image.naturalWidth, sky.height / image.naturalHeight);
            const imageWidth = image.naturalWidth * scale, imageHeight = image.naturalHeight * scale;
            skyContext.drawImage(image, (sky.width - imageWidth) / 2, (sky.height - imageHeight) / 2, imageWidth, imageHeight);
        }
        else {
            const pixels = skyContext.createImageData(sky.width, sky.height);
            const aspect = width / height;
            for (let y = 0; y < sky.height; y++)
                for (let x = 0; x < sky.width; x++) {
                    const nx = x / sky.width, ny = y / sky.height;
                    const px = nx * Math.min(aspect, 2.5) * 4.3, py = ny * 4.3;
                    const warp = fractal(px * .85 + 8, py * .85 + 4);
                    const diagonal = ny + nx * .62;
                    const ribbon = Math.exp(-Math.pow((diagonal - 1.04 + (warp - .5) * .27) / .075, 2))
                        + .65 * Math.exp(-Math.pow((diagonal - 1.63 + (warp - .5) * .22) / .065, 2));
                    const filaments = Math.pow(Math.max(0, 1 - Math.abs(fractal(px * 3 + warp * 4, py * 3) - .51) * 7), 3);
                    const cloud = ribbon * (.12 + filaments * .88) * (.3 + fractal(px + 31, py + 17));
                    const purple = noise(px * .6 + 22, py * .6 + 5);
                    const dust = Math.pow(fractal(px * 2 + 40, py * 2), 2);
                    const amount = cloud * (1 - dust * .8);
                    const index = (y * sky.width + x) * 4;
                    pixels.data[index] = 2 + amount * (24 + purple * 46);
                    pixels.data[index + 1] = 6 + amount * (42 - purple * 17);
                    pixels.data[index + 2] = 12 + amount * (91 + purple * 20);
                    pixels.data[index + 3] = 255;
                }
            skyContext.putImageData(pixels, 0, 0);
        }
        rasterStars = imageReady ? findRasterStars(skyContext.getImageData(0, 0, sky.width, sky.height).data, sky.width, sky.height) : [];
        seed = 91473;
        const count = Math.min(300, Math.max(150, Math.round(width * height / 6500)));
        stars = Array.from({ length: count }, () => {
            const bright = random();
            return { x: random() * width, y: random() * height, radius: bright > .99 ? .95 : .22 + random() * .48,
                phase: random() * Math.PI * 2, speed: .24 + random() * .66, alpha: .22 + random() * .5,
                cross: false, cyan: random() > .56 };
        });
        draw(0);
    }
    function draw(time) {
        context.globalAlpha = 1;
        if(imageReady)driftArtwork(time);else context.drawImage(sky, 0, 0, width, height);
        shimmer.clearRect(0, 0, width, height);
        drawRasterShimmer(shimmer, rasterStars, time, motion.matches, width / sky.width, height / sky.height);
        for (const [starIndex, star] of stars.entries()) {
            // Each point keeps a visible floor; no scene-wide opacity pulsing.
            const shimmer = starTwinkleAlpha(starIndex, time, 12000 + (star.speed - .24) / .66 * 14000, star.phase / (Math.PI * 2), motion.matches);
            context.globalAlpha = star.alpha * shimmer;
            context.fillStyle = star.cyan ? '#b9ddff' : '#fff4ee';
            context.beginPath();
            context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
            context.fill();
            if (star.cross) {
                const r = 4 + star.alpha * 4;
                const halo = context.createRadialGradient(star.x, star.y, 0, star.x, star.y, r * 2);
                halo.addColorStop(0, star.cyan ? '#82bcff88' : '#e4a8de77');
                halo.addColorStop(1, '#00000000');
                context.fillStyle = halo;
                context.fillRect(star.x - r * 2, star.y - r * 2, r * 4, r * 4);
                context.fillStyle = '#e7f2ff';
                context.beginPath();
                context.moveTo(star.x - r, star.y);
                context.lineTo(star.x - .5, star.y - .5);
                context.lineTo(star.x, star.y - r * .9);
                context.lineTo(star.x + .5, star.y - .5);
                context.lineTo(star.x + r, star.y);
                context.lineTo(star.x + .5, star.y + .5);
                context.lineTo(star.x, star.y + r * .9);
                context.lineTo(star.x - .5, star.y + .5);
                context.closePath();
                context.fill();
            }
        }
        context.globalAlpha = 1;
    }
    function tick(time) {
        if (document.hidden || motion.matches) {
            frame = 0;
            return;
        }
        if (time - last >= 1000 / 24) {
            draw(time);
            last = time;
        }
        frame = requestAnimationFrame(tick);
    }
    function syncMotion() {
        driftLast=0;
        cancelAnimationFrame(frame);
        frame = 0;
        if (!document.hidden) {
            draw(0);
            if (!motion.matches)
                frame = requestAnimationFrame(tick);
        }
    }
    function resize() {
        cancelAnimationFrame(resizeFrame);
        resizeFrame = requestAnimationFrame(() => { rebuild(); });
    }
    image.onload = () => {
        if (disposed)
            return;
        imageReady = true;
        rebuild();
        syncMotion();
    };
    // Failure intentionally leaves the original procedural loading fallback visible.
    image.src = '__VOICE_STUDIO_ASSETS__/night-sky-stars-removed.png';
    rebuild();
    syncMotion();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', syncMotion);
    motion.addEventListener('change', syncMotion);
    window.__qwenSkyCleanup = () => {
        disposed = true;
        image.onload = null;
        cancelAnimationFrame(frame);
        cancelAnimationFrame(resizeFrame);
        window.removeEventListener('resize', resize);
        document.removeEventListener('visibilitychange', syncMotion);
        motion.removeEventListener('change', syncMotion);
    };
    const twinkles = document.createElement('div');
    twinkles.className = 'sky-twinkles';
    twinkles.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < SKY_STAR_COUNT; i++) {
        const el = document.createElement('span');
        el.className = 'sky-twinkle';
        const period = 12 + skyRandom(i, 51731) * 14;
        el.style.cssText = 'left:' + skyRandom(i, 91473) * 100 + '%;top:' + skyRandom(i, 78233) * 100 + '%;--twinkle-peak:' + starCyclePeak(i, 0) + ';--twinkle-period:' + period + 's;--twinkle-delay:' + (-starInitialPhase(i) * period) + 's;--twinkle-size:' + (i % 11 === 0 ? 4 : i % 3 === 0 ? 2.5 : 1.6) + 'px';
        let cycle = 0;
        el.addEventListener('animationiteration', () => el.style.setProperty('--twinkle-peak', String(starCyclePeak(i, ++cycle))));
        twinkles.appendChild(el);
    }
    document.body.appendChild(twinkles);
}
