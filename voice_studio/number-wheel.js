() => {
  if (window.voxoverNumberWheel) return;
  window.voxoverNumberWheel = true;
  const guarded = new WeakMap();
  const numberInput = event => (event.composedPath?.() || [event.target]).find(
    node => node?.tagName === 'INPUT' && node.type === 'number'
  );
  const restore = input => {
    if (!guarded.has(input)) return;
    guarded.delete(input);
    input.readOnly = input.dataset?.generationReadonly === 'true';
  };
  document.addEventListener('wheel', event => {
    const input = numberInput(event);
    if (!input || input.disabled || event.ctrlKey || (input.readOnly && !guarded.has(input))) return;
    // Keep the native number type, constraints, focus and keyboard stepping.
    // Read-only during the wheel's default action prevents native spinbutton
    // stepping without cancelling the event (which would also block scrolling).
    // Capture/composedPath covers new Gradio controls and clip-editor shadow DOM.
    event.stopImmediatePropagation();
    if (guarded.has(input)) return;
    const token = {};
    guarded.set(input, token);
    input.readOnly = true;
    requestAnimationFrame(() => {
      if (guarded.get(input) === token) restore(input);
    });
  }, {capture: true, passive: true});
  // Do not wait for a paint if the user resumes editing immediately, or if
  // focus leaves the field and Gradio needs to validate/commit its value.
  for (const type of ['keydown', 'beforeinput', 'pointerdown', 'focusout']) {
    document.addEventListener(type, event => {
      const input = numberInput(event);
      if (input) restore(input);
    }, true);
  }
}
