# Multiple timeline combine verification

Branch: `feature/multiple-clip-combine`, based on `feature/voice-design` (`229aeae`).

## Behavior
- Generate / Multiple only: duration in whole minutes and seconds plus Combine appear after a batch contains generated audio.
- Combines the generated batch snapshot, not subsequently edited draft timestamps.
- Clips keep their exact timestamp offsets. Gaps and trailing space are digital silence; overlapping clips sum together.
- Lossless PCM-24 WAV at the source sample rate and channel count. If summed peaks exceed full scale, a single disclosed gain adjustment prevents clipping. No automatic resampling or time stretching.
- A too-short requested duration reports every overrun and the minimum required duration. No clip is truncated and no output is published.
- Combined player/download appear only with successful media. Duration edits, a new batch, and new combine attempts clear stale output.
- Source clips and existing individual downloads remain untouched. Partial batches explicitly report generated/requested counts.
- Bounded-memory two-pass export with duration, RIFF size, disk space, source-format and audio-finiteness checks. Failed exports remove their incomplete staging file.

## Verification (2026-11-09)
- 126 Python tests passed and all 10 JavaScript test scripts passed.
- Backend synthetic tests cover silence/sample placement, overlap, peak protection, exact length, invalid data, format mismatch, overrun and cleanup.
- Existing real model-generated QA clips at 0:03 and 0:08 combined into exactly 12 seconds, PCM-24 at native rate, with sample-accurate placement and silence verified.
- Isolated browser fixture at port 8014 injected those real generated clips into the normal batch state. Controls were absent before clips; success revealed the 0:12 player and download. Playback advanced to 0:05 and the download control was exercised.
- Browser duration edit hid stale media. At 5 seconds, warning identified ends 5.080 and 10.800 seconds and minimum 0:11; no player/download remained. Switching to Single hid the controls.
- The fixture did not run a fresh model inference and did not change the user's voice files/output folders. No push or merge.
