/** Read-only browser regression. Run in the real app or synthetic Gradio fixture
 * at empty, generating, partial, complete, previous-only and cleared states. */
function verifyPlaybackControls({ expectedClips, expectedVisible }) {
  const workspace = document.querySelector('#production-workspace');
  if (!workspace) throw new Error('Missing production workspace.');
  const clips = document.querySelectorAll('#batch-output .batch-audio').length;
  if (clips !== expectedClips) throw new Error(`Expected ${expectedClips} generated clips; found ${clips}.`);
  const controls = ['batch-play-all', 'batch-stop-all'].map(id => {
    const button = document.getElementById(id);
    if (!button) throw new Error(`Missing ${id}.`);
    const rect = button.getBoundingClientRect();
    const visible = rect.width > 0 && rect.height > 0 && getComputedStyle(button).visibility !== 'hidden';
    if (visible !== expectedVisible) throw new Error(`${id} should be ${expectedVisible ? 'visible' : 'hidden'} with ${clips} generated clips.`);
    return { id, visible };
  });
  return { clips, multiple: workspace.classList.contains('multiple-mode'), controls };
}
