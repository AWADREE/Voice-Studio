# Seed randomizer verification

Implemented on the local feature/multiple-clip-combine worktree, 2026-11-10. No commit or push.

## Behavior

- Randomize sits next to the shared seed, disables and visually dims that field, and retains its value.
- Enabling Randomize prepares editable numeric clip seeds and New seed controls before generation, for single commentary and every Multiple row. New/imported rows get independent seeds.
- Each accepted repeat/full/individual generation picks a fresh seed unless a user edit or New seed has already prepared the next take. Automatically chosen batch seeds avoid collisions with other displayed clip seeds.
- Exact displayed seeds are captured for synthesis. Per-clip regeneration retains its immutable queued seed; draft edits or New seed can safely prepare a later take. Server results do not overwrite draft seeds.
- Randomize off uses the shared seed for single commentary and new batch rows without overrides. Existing per-clip seeds remain visible, editable fixed overrides, preserving the prior batch semantics.
- Invalid single seeds are blocked by readiness and validated before synthesis. Gradio delayed component mounting is handled without exposing a partially initialized controller.
- Fixed the existing generation-guard apostrophe parse error so confirmation and FIFO behavior execute.

## Automated verification

- Full Python unittest discovery: 187 tests passed, including new exact-single-seed forwarding checks for Generate, Clone, Design and invalid seed rejection.
- All 16 JavaScript test scripts passed. New test_seed_randomizer.cjs covers first/repeat generation, distinct seeds, explicit edits, New seed, late results, queued capture, off/on, added rows, collisions, invalid drafts and deferred Gradio module mounting.
- Existing queue, clip regeneration, playback, layout/alignment, number-wheel and readiness checks passed.
- git diff --check passed.
- Local environment still emits existing missing-SoX, missing-flash-attn and unclosed-event-loop warnings; tests pass.

## Browser verification

Used an isolated localhost:8014 fixture with the real UI and callback pipeline, but synthetic WAV generation. The active app on 8013 was not restarted or changed by this worker.

- Checkbox enabled; shared field disabled; single seed + New seed appeared before generation.
- First displayed single seed 2266843616 reached synthesis unchanged; repeat changed to 1140971995.
- Editing single seed to 123456 reached synthesis unchanged.
- Invalid 1.5 disabled Generate; New seed restored readiness.
- Two batch fields appeared before the first batch, with distinct displayed seeds 3367014572 and 4204176517. Both reached synthesis unchanged and generated two playable/downloadable clips.
- Individual regeneration changed only clip 1's seed to 1507793216; manually edited clip 2 seed 777 reached synthesis unchanged.
- Turning Randomize off restored the shared field (42), retained batch overrides, hid the random single field, and the next single synthesis used 42.
- Initial browser QA found and fixed Gradio delayed-mount initialization; subsequent first/repeated flows passed. Final cosmetic help-text/visibility wording is covered by automated tests.

No GPU inference was run for these checks. The fixture intercepts synthesis at app.generate; existing model-seeding code is unchanged. Local fixture logs and outputs are under ignored Temp/seed-randomizer-qa, with final Python output in Temp/seed-randomizer-python-tests-final.log.
