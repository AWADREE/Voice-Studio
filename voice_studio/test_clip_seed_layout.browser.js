/** Read-only browser regression; run in Multiple at desktop and 390 CSS px. */
function verifyClipSeedLayout() {
  const rows=[...document.querySelectorAll('#clip-editor .clip-row')];
  if(!rows.length)throw new Error('Expected a clip row.');
  if(document.documentElement.scrollWidth>innerWidth)throw new Error('Horizontal overflow.');
  return rows.map(row=>{
    const input=row.querySelector('[data-field="seed"]').getBoundingClientRect();
    const reset=row.querySelector('.clip-reset-seed').getBoundingClientRect();
    const next=row.querySelector('.clip-new-seed').getBoundingClientRect();
    if(Math.abs(reset.height-next.height)>1 || Math.abs(reset.y-next.y)>1)throw new Error('Seed actions must have matching heights and alignment.');
    if(reset.right>next.x || Math.abs(next.x-reset.right-8)>1)throw new Error('Reset must be immediately left of New seed with an 8px gap.');
    if(innerWidth<=480 ? reset.y<input.bottom : reset.x<input.right)throw new Error('Seed actions overlap the input.');
    if(!input.width || !reset.width || !next.width)throw new Error('Seed controls must be visible.');
    return {viewport:innerWidth,seed:row.querySelector('[data-field="seed"]').value,inputWidth:input.width,gap:next.x-reset.right};
  });
}
