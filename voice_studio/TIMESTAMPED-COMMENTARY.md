# Timestamped commentary batches

In **Load voice & generate**, choose **Timestamped clips**. Each row contains minutes, seconds, and a paragraph. Add/remove rows freely; single commentary remains a separate retained input. Load a reusable voice file, choose the common delivery instruction/language/sampling controls, and click **Generate commentary**.

- Timestamps label clips for placement in your video editor. They do not add silence, synchronize duration, sort rows, or time-stretch speech.
- Clips generate sequentially in row order, with the same selected voice and settings. GPU release happens once after the entire batch, including a failure, when enabled.
- Up to 100 rows; each paragraph is 1–2,000 characters. Minutes are whole numbers 0–9,999, seconds 0–59. Duplicate timestamps are allowed.
- Each run gets a unique output subfolder. Filenames include the timestamp and row ordinal, e.g. `02m15s-003.wav`. Original generation files remain untouched.
- Listen & export displays each clip and an explicit download. **Play all** plays top to bottom; pause or Stop playback stops the sequence. **Download all (ZIP)** contains completed WAVs and a portable manifest, not voice files or absolute paths.
- If a clip fails, later clips are not attempted. Completed clips remain downloadable. Fix the problem and remove already-completed rows before generating the remaining rows. There is no automatic retry.
- The clone-and-sample action is available in Single commentary mode. Clone once there, then use the selected saved voice for a batch. Batch clips do not replace the single-preview voice-saving workflow.

## Architecture

`batch_generation.py`: pure validation/sequence/export helper, injected callback and reentrant model lock. `clip-editor.js/.css`: Gradio stateful HTML editor; edits synchronize locally, avoiding per-keystroke server renders and stale whole-row snapshots. `batch-playback.js`: sequential playback with cancellation and listener cleanup. Existing single-clip `generate` API remains available; the new `generate_commentary` API receives mode and rows.

## Verification (feature branch)

- 62 Python tests passed, including 12 batch helper and 6 integration cases. Mocked inference verifies settings, one final release, partial failures, artifact authorization, validation, duplicate timestamps, privacy, lock contention, and API compatibility.
- Existing mode-transition JavaScript tests passed and 2,121 background-drift geometry cases passed.
- Real Chrome, isolated localhost fixture with synthetic silent WAVs: editing, adding/removing rows, retained text across mode switches, batch submission, duplicate timestamp filenames, two output players, sequential Play all completion verified.
- Actual model inference not repeated: another local Qwen instance was using GPU memory, leaving less than the existing 6 GiB guard. No live server was stopped or modified. Acoustic quality is not assessed by synthetic UI tests.
- Batch clips use the same themed Gradio Audio waveform player as single commentary. Play all advances through the player's official end-of-media event. Shared delivery instructions, language and generation settings appear above both modes. Generation shows a persistent busy notice and disables the Generate button until success or failure finishes, including when previous outputs exist.
