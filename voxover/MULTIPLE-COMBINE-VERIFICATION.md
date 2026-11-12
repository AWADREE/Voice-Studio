# Multiple timeline combine verification

Branch: `feature/multiple-clip-combine`, based on `feature/voice-design` (`229aeae`).

## Behavior
- Generate / Multiple only: duration in whole minutes and seconds plus Combine appear after a batch contains generated audio.
- Combines generated audio using the current editor timestamps. Changed commentary, row counts, or mismatched clips require regeneration.
- Clips keep their exact timestamp offsets. Gaps and trailing space are digital silence; overlapping clips sum together.
- Lossless PCM-24 WAV at the source sample rate and channel count. If summed peaks exceed full scale, a single disclosed gain adjustment prevents clipping. No automatic resampling or time stretching.
- A too-short requested duration reports every overrun and the minimum required duration. No clip is truncated and no output is published.
- Combined player/download appear only with successful media. Editing timestamps or total duration and starting or failing another Combine preserve the last successful output. Only a successful Combine replaces it. The section sits below Unload model and above the generated-clips status.
- Source clips and existing individual downloads remain untouched. Partial batches explicitly report generated/requested counts.
- Bounded-memory two-pass export with duration, RIFF size, disk space, source-format and audio-finiteness checks. Failed exports remove their incomplete staging file.

## Verification (2026-11-09)
- 126 Python tests passed and all 10 JavaScript test scripts passed.
- Backend synthetic tests cover silence/sample placement, overlap, peak protection, exact length, invalid data, format mismatch, overrun and cleanup.
- Existing real model-generated QA clips at 0:03 and 0:08 combined into exactly 12 seconds, PCM-24 at native rate, with sample-accurate placement and silence verified.
- Isolated browser fixture at port 8014 injected those real generated clips into the normal batch state. Controls were absent before clips; success revealed the 0:12 player and download. Playback advanced to 0:05 and the download control was exercised.
- Browser duration edit hid stale media. At 5 seconds, warning identified ends 5.080 and 10.800 seconds and minimum 0:11; no player/download remained. Switching to Single hid the controls.
- The fixture did not run a fresh model inference and did not change the user's voice files/output folders. No push or merge.


## Retention and placement regression (2026-11-10)
- 142 Python tests and all 10 JavaScript scripts passed. New retention and placement tests were observed failing before the fix.
- Browser checks used the production UI and real previously generated clips in the isolated port-8014 fixture. No fresh model inference was needed.
- A successful 12-second mix kept its exact media link after editing both total-duration fields and per-clip minutes/seconds. A too-short 2-second attempt and changed-commentary rejection kept the same player and download. Playback advanced to the end of the retained 12-second file.
- Restoring commentary and combining to 14 seconds replaced the result. The emitted WAV was sample-checked at the edited 0:01 and 0:06 offsets, with exact total length and silent gaps. The old file remained unchanged.
- Browser file saving was not completed; the download test encountered a separate approval. The retained player/link and actual WAV contents were verified without saving a browser copy.
- Actual browser layout confirmed Combine below Unload model and above the generated-clips status. Single mode hides it after its transition; returning to Multiple restores the retained player.
- Independent read-only diff review found no substantive issues.
- The normal app on port 8013 was restarted and its existing browser tab reloaded. No push, merge, or voice-file changes.
- Environment warnings remain: optional SoX and flash-attn are absent, and Gradio tests emit unclosed-event-loop ResourceWarnings. They did not cause test failures.
