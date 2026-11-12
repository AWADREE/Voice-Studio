# Playback controls visibility verification

Date: 2026-11-11.

- Play all and Stop playback are hidden when no generated batch players exist.
- Visibility follows the rendered players rather than draft row count or generation completion, so the first streamed clip reveals the controls immediately.
- Existing mode gating still hides the controls outside Multiple. Retained Previous clips still count as generated clips.
- The change is limited to the existing playback-control CSS selector; playback code, generated output, and draft state are unchanged.

## Verification

- The new read-only test_playback_controls.browser.js probe failed against the original live app: Play all was visible with zero generated clips.
- The same probe passed with the fix in an isolated Gradio fixture using synthetic tones instead of model inference.
- Browser coverage: empty initial row, three ungenerated draft rows, initial generation loader, one streamed clip while two remained pending, three completed clips, removing a generated row while retaining its audio, switching to Single, and returning to Multiple after a single generation cleared the batch output.
- Play all started with the first streamed clip and kept playing as the next two arrived. The first playhead reached 9.90 seconds without resetting; all three draft texts were intact. Stop playback remained functional.
- Complete suite at this change: 241 Python tests and 21 JavaScript scripts passed. Existing optional SoX/flash-attn and event-loop warnings were non-fatal. git diff --check passed.
- Screenshot: Temp/playback-controls-empty.png. Python log: Temp/playback-controls-python.log.
- Normal servers 8003 and 8013 were restarted together with the parallel seed-control change and both returned HTTP 200. Post-restart live UI checks are coordinated with that task. No commit or push.
