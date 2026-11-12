/** Read-only browser regression. Run after a completed Clone audition, both
 * with and without Include reference transcript and without correction checked.
 * Pass this function to the connected browser's read-only evaluate API.
 */
function verifyCloneSaveAvailability({ duringGeneration = false } = {}) {
  const generating = /Generating/.test(document.querySelector('#generate-commentary')?.textContent || '');
  if (duringGeneration && !generating) throw new Error('Start replacement generation before this check.');
  if (document.querySelector('#voice-mode-tabs button[aria-pressed="true"]')?.textContent.trim() !== 'Clone') {
    throw new Error('Run this check in Clone mode.');
  }
  const actions = document.querySelector('#audition-save-actions');
  if (!actions) throw new Error('Generate a Clone audition before this check.');
  const correction = actions.querySelector('#edit-transcript input');
  if (correction?.checked) throw new Error('Turn off transcript correction for this regression check.');
  const button = actions.querySelector('#save-corrected-audition');
  if (!button) throw new Error('The Clone voice save control is missing.');
  const rect = button.getBoundingClientRect();
  if (!rect.width || !rect.height || getComputedStyle(button).visibility === 'hidden' || getComputedStyle(button).pointerEvents === 'none') {
    throw new Error('Clone voice saving must be visible without editing the transcript, including identity-only cloning.');
  }
  if (button.disabled) throw new Error('Clone voice saving must be enabled when it is not already saving.');
  return { label: button.textContent.trim(), visible: true, enabled: true,
    transcriptCorrection: false, generating };
}
