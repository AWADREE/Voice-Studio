() => {
  if (window.voxoverSeedRandomizer) return;
  // SEED_HELPERS
  function mount() {
    if (window.voxoverSeedRandomizer) return true;
    const panel = document.getElementById('generate-panel');
    if (!panel) return false;
    const checkbox = panel.querySelector('.seed-randomize input[type="checkbox"]');
    const shared = panel.querySelector('.shared-seed input');
    const single = document.getElementById('single-clip-seed');
    const controls = single?.querySelector('.single-seed-controls');
    const input = single?.querySelector('[data-field="seed"]');
    if (!checkbox || !shared || !controls || !input) return false;
    const api = {
      get enabled() { return checkbox.checked; },
      prepare(args) {
        // Capture the displayed drafts exactly once per accepted full request.
        // Individual regeneration captures its own seed when it joins the queue.
        if (args[0] === 'generate' && args[1] === 'batch') {
          args[2] = window.voxoverClipEditor.prepareSeeds(api.enabled);
        } else if (api.enabled) {
          args[12] = consumeClipSeed(input, true);
        }
        return args;
      }
    };
    window.voxoverSeedRandomizer = api;
    function refresh() {
      shared.disabled = api.enabled;
      shared.setAttribute('aria-disabled', String(api.enabled));
      shared.closest('.shared-seed').classList.toggle('seed-randomized', api.enabled);
      controls.hidden = !api.enabled;
      if (api.enabled && input.dataset.seedReady !== 'true') initializeClipSeed(input);
      window.dispatchEvent(new Event('voxover-randomize'));
    }
    input.addEventListener('input', () => { input.dataset.seedReady = 'true'; });
    single.querySelector('.clip-new-seed').addEventListener('click', () => {
      initializeClipSeed(input);
      input.dispatchEvent(new Event('input', {bubbles: true}));
    });
    checkbox.addEventListener('change', refresh);
    refresh();
    return true;
  }
  // Gradio's component modules can finish mounting after app.load callbacks.
  if (!mount()) {
    const observer = new MutationObserver(() => { if (mount()) observer.disconnect(); });
    observer.observe(document.getElementById('generate-panel') || document.body, {childList: true, subtree: true});
  }
}
