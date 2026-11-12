/** Read-only browser regression. Run in Generate > Single, then pass the returned
 * result as baseline after switching to Multiple at the same viewport.
 * Repeat at 1600, 1300, 1299, 1000, 900 and 390 CSS pixels.
 */
function verifyCommentaryWidths({ baseline = null } = {}) {
  const workspace = document.querySelector('#production-workspace');
  const generate = document.querySelector('#generate-panel');
  const listen = document.querySelector('#listen-panel');
  if (!document.querySelector('#voice-mode-workspace.generate-mode')) throw new Error('Select Generate first.');
  const multiple = workspace.classList.contains('multiple-mode');
  const rect = element => { const r = element.getBoundingClientRect(); return { x:r.x, y:r.y, width:r.width, height:r.height, bottom:r.bottom }; };
  const panels = { generate:rect(generate), listen:rect(listen) };
  const narrow = matchMedia('(max-width:1299px)').matches;
  const columns = getComputedStyle(workspace).gridTemplateColumns.split(' ').filter(Boolean);
  if (columns.length !== (narrow ? 1 : 2)) throw new Error('Both tabs must use the same 1299px stacking breakpoint.');
  if (!narrow && Math.abs(panels.generate.width - panels.listen.width * 2) > 1) throw new Error('Both tabs must retain the original 2:1 Generate/Listen widths.');
  if (narrow && Math.abs(panels.generate.width - panels.listen.width) > 1) throw new Error('Stacked section widths must match.');
  if (document.documentElement.scrollWidth > innerWidth) throw new Error('Unexpected horizontal document overflow.');
  if (baseline) for (const name of ['generate','listen']) {
    if (Math.abs(panels[name].width - baseline.panels[name].width) > 1 ||
        Math.abs(panels[name].x - baseline.panels[name].x) > 1) throw new Error(name + ' changed width or horizontal position when switching tabs.');
  }
  const surface = rect(multiple ? document.querySelector('#listen-top-controls') : listen);
  if (baseline && (Math.abs(surface.width-baseline.surface.width)>1 || Math.abs(surface.x-baseline.surface.x)>1)) throw new Error('The visible Listen card changes width or position between tabs.');
  const pairs = [];
  if (multiple) for (const row of document.querySelectorAll('#clip-editor .clip-row')) {
    const id = row.dataset.clipId;
    const player = document.getElementById('generated-clip-' + id) ||
      Array.from(document.querySelectorAll('#clip-placeholders .clip-empty-player')).find(element => element.dataset.clipId === id);
    if (!player) throw new Error('Missing player/placeholder for ' + id);
    const editorRect = rect(row), playerRect = rect(player);
    if (narrow ? playerRect.y < editorRect.bottom - 1 :
        Math.abs(editorRect.y-playerRect.y)>1 || Math.abs(editorRect.height-playerRect.height)>1) throw new Error('Paragraph/player alignment is broken.');
    const nextRow = row.nextElementSibling;
    if (narrow && nextRow?.classList.contains('clip-row') && playerRect.bottom > rect(nextRow).y + 1) throw new Error('A player overlaps the next paragraph.');
    pairs.push({ id, editor:editorRect, player:playerRect });
  }
  return { multiple, viewport:innerWidth, narrow, columns, panels, surface, pairs };
}
