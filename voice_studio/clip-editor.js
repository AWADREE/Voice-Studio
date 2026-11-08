const list = element.querySelector('.clip-list');
const add = element.querySelector('.clip-add');
function snapshot() {
  props.value = [...list.querySelectorAll('.clip-row')].map(row => ({minutes: Number(row.querySelector('[data-field="minutes"]').value), seconds:Number(row.querySelector('[data-field="seconds"]').value), text:row.querySelector('textarea').value}));
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
    box.remove(); snapshot(); (next?.querySelector('textarea') || add).focus();
  });
  list.appendChild(box); return box;
}
for(const data of props.value || []) row(data);
add.addEventListener('click', () => { if(list.children.length>=100)return; const added=row({minutes:0,seconds:0,text:''}); snapshot(); added.querySelector('textarea').focus(); });
