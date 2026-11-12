/**
 * Read-only browser regression probe. Pass this function to the connected
 * browser's evaluate API during initial, repeated and per-clip generation.
 * requiredSelectors prevents a missing loader from making a test pass.
 */
function verifyLoadingBorders({ requiredSelectors = [] } = {}) {
  const selectors = [
    '#listen-top-controls > .studio-audio-output > .wrap:not(.hide)',
    '#listen-panel .wrap.generating',
    '#clip-placeholders .clip-pending-surface',
    '#batch-output .clip-pending-surface',
  ];
  const visible = (element) => {
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };
  for (const selector of requiredSelectors) {
    if (!Array.from(document.querySelectorAll(selector)).some(visible)) {
      throw new Error(`Expected a visible loading surface: ${selector}`);
    }
  }
  const surfaces = Array.from(new Set(selectors.flatMap((selector) =>
    Array.from(document.querySelectorAll(selector)).filter(visible)
  )));
  if (!surfaces.length) throw new Error('Run this probe while generation is active.');
  return surfaces.map((element) => {
    const style = getComputedStyle(element);
    const widths = ['Top', 'Right', 'Bottom', 'Left'].map((side) => style[`border${side}Width`]);
    if (widths.some((width) => width !== '0px') || style.boxShadow !== 'none') {
      throw new Error(`Loading border/glow on ${element.className}: ${style.border}; ${style.boxShadow}`);
    }
    const progress = element.querySelector('.progress-bar');
    const state = element.closest('[data-loading-state]')?.getAttribute('data-loading-state');
    if (progress && element.classList.contains('clip-pending-surface') &&
        state !== 'queued' && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const animation = getComputedStyle(progress);
      if (animation.animationName !== 'clip-loading-progress' || animation.animationPlayState !== 'running') {
        throw new Error('Border removal must preserve active clip progress animation.');
      }
    }
    return { classes: element.className, border: style.border, shadow: style.boxShadow,
      progress: progress ? getComputedStyle(progress).animation : null };
  });
}
