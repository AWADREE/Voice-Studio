# Streaming clips verification

Date: 2026-11-10. Branch: `feature/stream-multiple-clips`, based on freshly fetched `origin/main` at `0cede22`.

## Automated checks

- 230 Python unittest cases passed (`python -B -m unittest discover -v`).
- All 19 `test_*.cjs` Node scripts passed.
- `git diff --check` passed.
- An independent final code audit found no blocking issue.

Coverage includes immutable snapshots; stable row IDs and legacy positional rows; cancellation and lock ownership across different consumer threads; partial failure preservation; unique ZIP entries and manifest correspondence; public API arity; serial FIFO queue eligibility and duplicate rejection; confirmation cancel/Escape; seed capture; timestamp rollover; active playback through native player remounts; unchanged top-loader styling; and a delayed duration response arriving after a user edit.

## Live browser checks (synthetic inference)

The actual Gradio app ran in Chrome on an isolated test port. Only inference was replaced with delayed synthetic 90-second test tones to expose streaming and race behavior. These checks are not model-quality tests.

1. Initial batch: queued/active loaders appeared in each existing paragraph/audio slot. Each finished clip became playable before later clips finished.
2. Initial and repeat full generation: the original native top loader appeared in `listen-top-controls`, 166 px high, with 0 px borders on both the audio container and native loader wrapper. Native progress remained visible after streamed snapshots (33/66 percent in a three-clip batch, 50 percent in a two-clip batch). No extra section was added.
3. Started clip 1 playback and confirmed its regeneration while clip 2 was still generating. Clip 1 remained playing as clip 2 arrived (playhead advanced from 0.84 to 23.31 seconds) and through final completion/queued replacement (46.64 seconds). Inference log order was original clips 1, 2, 3, then queued clip 1. No parallel inference occurred.
4. Manual addition: after editing the preceding timestamp to 00:58, Add clip produced 01:03, with Seed and New seed visible. Original first-row 00:01 remained unchanged.
5. Duration: final clip at 00:58 plus 90 seconds produced 02:28; editing its timestamp to 00:59 automatically produced 02:29. Editing total duration to 02:50 then changing timestamps/generating again retained 02:50. Verified a 16 px control gap. Repeated after the delayed-response edit gate was installed.
6. Combined output: a successful 02:50 combined WAV remained the identical download after a later partial full-regeneration failure. Newly completed clip 1 replaced its prior take; failed/unreached clips kept their previous file URLs. Final controls recovered and allowed regeneration. The surfaced failure was the original synthetic inference error, not a None-path exception.

## Real model smoke check

Separately ran the locally cached Qwen3-TTS 1.7B Base model on CUDA, with a synthetic zero-embedding test voice (not a personal voice), identity-only mode, and a 128-token limit. The first playable clip was published at 4.322 seconds, before the final batch at 5.406 seconds. Both finite 24 kHz WAVs had the correct row IDs and seeds (101/202). Regenerated only the first clip using seed 303; the second clip path, seed, bytes/hash and samples were unchanged. Model cleanup and lock release succeeded. This verifies real inference dispatch and incremental publication, not voice quality or VoiceDesign inference.

Raw local logs and test artifacts are under ignored `Temp/final-python-tests.log`, `Temp/streaming-qa/`, and `Temp/stream-real-qa/`. No personal voice was used. Existing SoX/flash-attention warnings remain unrelated environment limitations.

## Served instance

Restarted the user's port 8013 instance from the main checkout on this feature branch. Confirmed its process command points to this checkout, HTTP configuration includes the new duration edit gate and streaming queue code, and a fresh browser page exposes manual row Seed/New seed with 00:01 then 00:06 defaults. Port 8003 was left running unchanged. Existing worktrees and their files were preserved. The isolated synthetic test server was stopped. No commit or push was made.

## Loading border follow-up (2026-11-10)

- Reproduced the per-clip surface border in active/queued initial batch slots and regeneration cards: computed border was 1 px solid rgb(54, 80, 101).
- Reproduced the repeat-full-generation ring: Gradio's native `.wrap.generating` overlays under `batch-output` and its render container covered the shared Listen grid (about 2,079 px high). The theme painted a 1 px rgb(173, 204, 225) border plus inset blue glow, while Gradio animated opacity.
- Removed only the border and inset shadow from those native generating overlays and the two custom clip progress surfaces. Progress animations, transitions, normal card geometry, spinner styles, elapsed text and queue behavior are unchanged.
- A live computed-style regression assertion failed before the fix on the 1 px clip surface. After restart, Chrome confirmed 0 px borders and no shadows on initial active/queued clip loaders, repeated full-generation overlays, and individual regeneration. Active clip progress retained its 1.6-second moving animation; queued progress stayed paused; the top native progress remained visible. Individual regeneration affected one card and left its neighbor available, then restored both. New individual generation also completed successfully; its existing static pre-generation placeholder behavior is unchanged.
- Saved reusable read-only browser probe in `test_loading_borders.browser.js`. Its required-selector checks prevent missing/inactive loaders from passing verification.
- Fresh regression run: all 230 Python unittest cases and all 19 Node `test_*.cjs` suites passed. `node --check test_loading_borders.browser.js` and `git diff --check` passed. Existing SoX/flash-attention environment warnings remain.
- Restarted only the active 8013 instance from this checkout; HTTP 200 and served CSS verified. Port 8003 stayed on its original PID 19360. Reloaded the verification tab against 8013. Synthetic browser checks used isolated port 8018; no personal audio or model inference was required. No commit or push.
