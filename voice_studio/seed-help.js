() => {
  function mount() {
    const root = document.querySelector('#generate-panel .seed-randomize');
    const checkbox = root?.querySelector('input[type="checkbox"]');
    if (!checkbox) return false;
    if (root.dataset.seedHelpReady) return true;
    root.dataset.seedHelpReady = 'true';
    const tooltip = document.createElement('div');
    tooltip.className = 'seed-help-tooltip';
    tooltip.id = 'voxover-randomize-help';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.hidden = true;
    tooltip.innerHTML = '<p><strong>Seed</strong> applies to clips without their own seed. Use -1 for random.</p>' +
      '<p><strong>Randomize</strong> chooses fresh seeds for each take. Per-clip edits apply to the next take.</p>';
    root.appendChild(tooltip);
    const descriptions = new Set((checkbox.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    descriptions.add(tooltip.id);
    checkbox.setAttribute('aria-describedby', [...descriptions].join(' '));
    let hovered = false, focused = false, dismissed = false;
    const render = () => { tooltip.hidden = dismissed || !(hovered || focused); };
    root.addEventListener('pointerenter', () => {
      hovered = true;
      dismissed = false;
      render();
    });
    root.addEventListener('pointerleave', () => {
      hovered = false;
      if (!focused) dismissed = false;
      render();
    });
    root.addEventListener('focusin', () => {
      focused = true;
      dismissed = false;
      render();
    });
    root.addEventListener('focusout', event => {
      if (root.contains(event.relatedTarget)) return;
      focused = false;
      if (!hovered) dismissed = false;
      render();
    });
    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || tooltip.hidden) return;
      dismissed = true;
      render();
      event.stopPropagation();
    }, true);
    render();
    return true;
  }
  if (!mount()) {
    const observer = new MutationObserver(() => { if (mount()) observer.disconnect(); });
    observer.observe(document.getElementById('generate-panel') || document.body, {childList:true, subtree:true});
  }
}
