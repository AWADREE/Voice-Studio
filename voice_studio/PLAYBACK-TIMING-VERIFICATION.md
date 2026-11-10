# Clip generation, playback and timing verification

Date: 2026-11-10. Branch: feature/multiple-clip-combine. Local changes only; no push or merge.

## Implemented behavior

- Every existing per-clip take requires Replace & regenerate confirmation, including queued jobs. Cancel/Escape leaves audio, seed and queue unchanged. First-time Generate does not ask to replace nonexistent audio.
- Generate is visible on every row before a full generation and for newly added rows. Existing generated IDs show Regenerate. Standalone generation builds a partial batch without synthesizing other rows.
- Individual generation does not stop playback. Play all stays available and every click resets the sequence to the first visible clip. Native playback state is retained through Gradio same-element source reloads and replacements; explicit user Pause and Stop are respected.
- Set timestamps back-to-back appears directly above Combine. It confirms overwrite, preserves the first timestamp, and computes later starts from actual WAV frame counts. Timing edits alone never combine or clear the previous combined result.
- Timestamp planning uses stable row IDs and exact text/current generated mapping; missing/stale/invalid audio and running or queued generation are rejected. Confirmation rechecks editor and generation versions to avoid overwriting intervening edits.
- Generation failures retain old audio and expose the backend reason beside the affected row. Metadata publishes before FIFO queue release. First standalone queued jobs share only their own draft origin; old/different batch jobs cannot overwrite a newer result.

## Reported fast-return failure

The original live 8013 page displayed: "Regeneration failed: The generated batch changed while this clip was queued. Existing audio was kept." This is a pre-synthesis guard failure, not completed neural inference. Editing text or adding a row alone does not change the server batch identity. The original historical source of stale metadata/session identity cannot be conclusively reconstructed. Explicit metadata-before-unlock ordering closes the observed client timing risk; reset sessions now give an actionable restore message while preserving disk audio. The batch-identity safety check remains enforced.

Exact sequence exercised: full generation, one regeneration, move part of an existing paragraph to a new row, regenerate shortened original, then Generate the added row. Logs verify the shortened text reaches synthesis and produces a fresh immutable WAV; unrelated audio stays unchanged. Tested in the browser fixture and separately through actual Qwen model inference.

## Automated evidence

- 209 Python tests passed (Temp/playback-timing-python-tests.log).
- 18 JavaScript test scripts passed, including confirmation/cancel, FIFO/removed rows, first standalone jobs, shared-seed inheritance with settings unmounted, timing/version races, one-sample precision, repeated Play all, native pause, and source reload/remount continuity.
- Same-node blob reload regressions model reset timeupdate and pause while connected, before the new source becomes current. These distinguish player lifecycle from an explicit Pause.
- Syntax checks and git diff --check are part of the final checkpoint.

## Browser and output evidence

The isolated 8017 browser fixture uses production UI/callbacks and synthetic WAV generation with 14-second delayed runs and final 1-second rapid-reload runs. It is not neural synthesis. It verifies native media state, modal behavior, queuing, failures, current text dispatch and the actual exported WAV.

- Confirmation cancel caused no synthesis and retained audio. A queued cancellation did not enqueue work.
- Play all continued at generation start and could be clicked again during the job to restart from the first clip. Completion continuity is checked separately below.
- Single commentary to Multiple, then first Generate plus a second queued Generate worked with generation settings closed/unmounted. Both native players became visible without full Generate.
- Invalid voice fixture failure retained all four old download URLs and the old combined URL, and displayed the actionable error beside the row.
- Retime cancel retained [1,15,25,0]. Confirm yielded seconds [1,4.750041666666666,17.000083333333333,29.250125], keeping the first start, text and seeds. Full Generate remained enabled with fractional times.
- Retime left the old combined URL unchanged. Only pressing Combine created a new result.
- The 40-second combined WAV was checked sample by sample at 24 kHz: source frames [90001,294001,294001,60001], boundaries [24000,114001,408002,702003,762004], total 960000 frames. Exactly one second leading silence, consecutive source samples, then trailing silence; np.array_equal passed, maximum absolute error 0.0. No overlap or sample gap at the clip boundaries.

## Real inference evidence

Temp/real-clip-qa-20261110-113851/summary.json records actual cached Qwen3-TTS Base inference, not a mock. A synthetic nonpersonal test voice embedding was used with identity_only and a short 128-token cap. Full batch, regeneration, shortened-original regeneration after splitting text, added-row generation, and first standalone generation all produced nonempty audio with distinct hashes and immutable file paths. Durations were 1.44, 1.92, 0.72, 1.04 and 0.88 seconds respectively. Existing source files and unrelated clip paths were retained. This validates synthesis dispatch and persistence, not voice quality.

## Final live playback checkpoint

Passed in the final browser fixture:

- Regenerating a later clip while Play all was active: after Updated clip 2, the first native player was still playing at 6.727 seconds; other players stayed paused.
- Regenerating the active first clip: after Updated clip 1, the new take was playing at 16.070 seconds, preserving the playhead rather than restarting at zero.
- Stop Play all, independently play the first native player, regenerate it: after completion, that player remained playing while the other two remained paused. The final reading reached 44.998 seconds normally.
- Explicit native Pause at 1.227941 seconds, followed by successful replacement: it remained paused at exactly 1.227941 seconds. Pressing Play all then started the first clip at zero.
- The final live test exposed and fixed WaveSurfer's double reset: it seeks/pauses before source load, then can reset again after loadedmetadata while finalizing its waveform. Recovery persists until actual playback advances, but native user input, Stop and collapse invalidate recovery. Regression tests include the exact observed event order, Stop between reset/load, independent playback after stopping Play all, and stale play-promise rejection.

Production port 8013 was restarted with the final code. Served config was checked and a fresh production browser tab was left open in Generate / Multiple with the per-row Generate button visible before any generation. The original tab could not be controlled after the desktop reconnect, so the new tab is the verified entry point. The isolated QA tab was closed and its server stopped. Existing disk audio/voice files and unrelated work were retained.
