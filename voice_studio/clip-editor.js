const list = element.querySelector('.clip-list');
const add = element.querySelector('.clip-add');
function snapshot() {
  props.value = [...list.querySelectorAll('.clip-row:not([data-removing])')].map(row => ({minutes: Number(row.querySelector('[data-field="minutes"]').value), seconds:Number(row.querySelector('[data-field="seconds"]').value), text:row.querySelector('textarea').value}));
  add.disabled = props.value.length >= 100;
}
function row(data) {
  const box = document.createElement('div'); box.className = 'clip-row';
  const uid = crypto.randomUUID();
  box.innerHTML = `<div class="clip-time"><label for="minutes-${uid}">Minutes<input id="minutes-${uid}" data-field="minutes" type="number" min="0" max="9999" step="1"></label><label for="seconds-${uid}">Seconds<input id="seconds-${uid}" data-field="seconds" type="number" min="0" max="59" step="1"></label></div><label for="paragraph-${uid}">Commentary<textarea id="paragraph-${uid}" rows="3" maxlength="2000"></textarea></label><button class="clip-remove" type="button">Remove clip</button>`;
  box.querySelector('[data-field="minutes"]').value = data.minutes;
  box.querySelector('[data-field="seconds"]').value = data.seconds;
  box.querySelector('textarea').value = data.text;
  box.addEventListener('input',snapshot);
  box.querySelector('.clip-remove').addEventListener('click', () => {
    const next = box.nextElementSibling || box.previousElementSibling;
    box.dataset.removing='true'; snapshot(); (next?.querySelector('textarea') || add).focus();
    if(matchMedia('(prefers-reduced-motion: reduce)').matches){box.remove();return;}
    const height=box.getBoundingClientRect().height;
    const anim=box.animate([{height:height+'px',opacity:1,padding:'16px',marginBottom:'0px'},{height:'0px',opacity:0,padding:'0px 16px',marginBottom:'-20px'}],{duration:200,easing:'cubic-bezier(.2,.7,.2,1)',fill:'forwards'});
    box.style.overflow='hidden';box.style.minHeight='0';
    anim.onfinish=()=>box.remove();
  });
  list.appendChild(box); return box;
}
for(const data of props.value || []) row(data);
add.addEventListener('click', () => { if(list.children.length>=100)return; const before=list.getBoundingClientRect().height; const added=row({minutes:0,seconds:0,text:''}); snapshot(); if(!matchMedia('(prefers-reduced-motion: reduce)').matches){const after=list.getBoundingClientRect().height;list.animate([{height:before+'px',overflow:'clip'},{height:after+'px',overflow:'clip'}],{duration:200,easing:'cubic-bezier(.2,.7,.2,1)'});} added.querySelector('textarea').focus({preventScroll:true}); });
