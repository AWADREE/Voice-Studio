# Individual clip regeneration

Branch: `feature/multiple-clip-combine`.

## Behavior

- Generate > Multiple shows Regenerate on paragraphs with a corresponding generated clip, after a full generation attempt has produced those clips. New/imported paragraphs without matching audio do not claim an existing clip.
- Paragraph IDs survive edits and import undo. Matching never relies on text or timestamp equality, so duplicate paragraphs/times cannot replace each other by accident.
- Regenerate uses the selected voice, current paragraph text and shared settings. It replaces only that clip in the existing output order, after synthesis and creation of a fresh complete ZIP succeed.
- Replacement is highlighted with an Updated label and warm outline; the Listen section scrolls to it without moving keyboard focus. Reduced-motion preferences are respected.
- Play all reads the current rendered players. Individual downloads, ZIP and the next Combine use the current replacement. Existing output files are not overwritten or deleted.
- Previous combined audio is untouched by edits, regeneration or failed Combine. Only successful recombination replaces its player/download.
- Full Generate asks before replacing existing Listen audio. Native modal focus, Escape and Cancel preserve current media and do not start generation. Confirmation copy adapts to Multiple versus single/audition modes.
- A busy guard prevents overlapping browser submissions and holds the paragraph editor stable through commit. Server-side batch/revision and paragraph checks reject obsolete results. Generation/archive failures retain the previous audio and ZIP; a failed full replacement retains the prior batch.

## Automated verification

- 158 Python tests passed, including 15 regeneration tests.
- All 12 JavaScript test scripts passed. Confirmation, cancel, duplicate clicks, busy editor state, focus return and both metadata/render arrival orders are covered.
- New failing regressions were observed for missing row identity, replacement functions/wiring, full-generation failure retention, unqueued state commit and late highlight metadata before their corresponding fixes.
- `git diff --check` and JavaScript syntax checks passed.
- Independent final read-only review found no high-confidence substantive issue.

## Browser and audio verification

An isolated port-8014 fixture used the normal production UI and callbacks, synthetic non-personal voice input, and previously generated QA audio instead of fresh model inference.

- Initial full Generate produced three clips. Regenerate paragraph 2 changed only its audio URL and duration; paragraphs 1 and 3 kept their exact URLs. Only paragraph 2 gained Updated styling.
- Play all advanced through the replacement player and then the final unchanged player.
- The new ZIP's replacement entry exactly matched the replacement WAV; its other two WAV entries were unchanged.
- New combined audio matched an independently constructed latest-source PCM mix exactly: 600,000 frames at 24 kHz, maximum sample error 0. The previous combined link stayed unchanged until recombination.
- Duration/timestamp edits and failed regeneration retained the previous combined file. Full replacement failure at clip 2 retained the previous Listen batch and combined audio.
- Cancel and Escape started no generation; keyboard confirmation did. Escape returned focus to Generate.
- Single, Clone and Design showed no Regenerate controls. Remove/add kept surviving IDs and gave the new row a fresh ID with regeneration hidden. Import created new IDs; Undo restored the prior IDs and correctly numbered accessible Regenerate labels.
- The live test caught Gradio 6.17.3 omitting State.change notifications for unqueued responses. The commit now runs queued, ensuring players and metadata update with the state.
- Screenshot: `Temp/regeneration-highlight.png` (local QA artifact).

Actual browser ZIP saving was canceled by the installed download handling. The generated archive and its bytes were verified directly; a completed browser download is not claimed. No new model inference or voice-file changes were needed. Existing optional SoX/flash-attn and Gradio event-loop warnings remain non-fatal.

The normal app on port 8013 was restarted with the feature. No push or merge. Pre-existing combined-retention and number-wheel edits were preserved.

## Scoped loading follow-up

- Regeneration shows the same navy Listen surface, native progress text and blue/gold track inside only the selected clip. The indeterminate bar does not invent a percentage; elapsed time is measured from the request.
- Existing card geometry is retained so neighboring clips do not move. Other clips remain visible and can play. Play all is temporarily disabled while the old target player is hidden, then restored.
- Success, failure, mode switching and canceled main-generation confirmation were tested live with a delayed fixture. Failures restore the old audio; success restores the player with its Updated highlight.
- The busy flag applies only to the old audio player, leaving the sibling live status announceable. Reduced motion uses a static centered fill and zero-duration visibility transitions.
- The original full Generate loader is unchanged. The pending card fits a 390px viewport without horizontal overflow.
- 158 Python tests and 13 JavaScript scripts passed at this checkpoint. Screenshot: `Temp/clip-loader-pending.jpg`.

## Per-clip seeds follow-up

- Seed and New seed appear only for paragraphs with generated audio. Initial values inherit the shared seed used for that first generation; subsequent results do not overwrite edited fields.
- Each row's seed overrides the shared seed for both individual Regenerate and full Generate. New/uninitialized rows use the current shared seed.
- New seed uses secure 32-bit randomness, including a distinct-value fallback for a repeated random draw. Manual seeds support -1 (random) through the largest exactly representable browser integer, 9,007,199,254,740,991.
- Seeds follow stable paragraph IDs through edits and import undo. Invalid, changed or removed in-flight overrides cannot overwrite existing audio. Changing a seed alone does not regenerate audio or invalidate an existing combined file.
- Live fixture generation-callback logs verified initial shared seeds, one-row overrides, New seed, full-batch overrides, unchanged fields, and Single mode's continued use of the global seed. Invalid -2 triggered no synthesis and preserved audio URLs.
- Add/delete/import/undo retained the correct identities. A focused wheel gesture left the seed unchanged; ArrowUp changed it normally.
- Final regression checkpoint: all 167 Python tests and all 14 JavaScript scripts passed, plus syntax/whitespace checks. Independent seed review found no actionable seed defect. Evidence: `Temp/seed-qa-calls.jsonl` and `Temp/clip-seeds-python-tests.log`.
- Production 8013 was restarted with seeds before beginning the separately requested alignment work. No push or merge.
- A second integration check exercised real `app.generate`, voice validation, PyTorch seed setters, WAV writes, batching and replacement commit, mocking only model loading/inference. `torch.initial_seed()` observed at `generate_voice_clone` was `[123, 123]` initially, `[101, 202]` for full regeneration despite shared 999, `[303]` for individual regeneration despite shared 888, and `[101, 303, 777]` when a new row inherited shared 777. This verifies model-boundary seed propagation, not fresh neural inference.

## Aligned paragraph and Listen rows

- Multiple now uses shared CSS Grid rows and subgrids. Each paragraph stays in Generate and its native player stays in Listen, matched by stable ID. There are no measured spacer heights or native-player DOM moves.
- The two controls groups share a naturally sized top row on wide screens. Paragraph/player pairs have equal top and bottom edges, even when either side grows. Narrow screens stack each pair while retaining the separate section structure.
- New paragraphs receive a Not generated yet placeholder. Removed or import-replaced paragraphs do not silently lose their audio: unmatched players remain under Previous clips. Import Undo restores the pairing. Play all follows the visible row order and stops when leaving Multiple.
- Existing entry/removal fades, loading transitions, replacement highlights, keyboard controls and reduced-motion behavior remain supported. Shared tracks stay intact through the removal fade.
- Final automated checkpoint: all 173 Python tests and all 15 JavaScript scripts passed, plus `git diff --check`. Coverage includes stable IDs, reorder, placeholders, orphan/undo, mobile footer tracks, native-player identity, observer convergence, mode-stop playback and hidden Gradio wrapper hit-testing contracts.
- Final port-8015 live fixture checks passed: three wide pairs had 0px top and height differences, including expanded generation settings, successful 25-second Combine, and a manual textarea resize from 96px to 316px. At 390px, controls, paired rows and Add/Previous/orphan rows were separate with 20px gaps and no horizontal document overflow.
- Real Generate, Combine and Play all clicks were tested. The native full-generation loader remained visible while batch players were hidden. Scoped failure/success loaders affected only the selected clip. Failure retained all three exact download URLs; successful retry restored the Updated highlight. Play all used sourced WaveSurfer shadow media and switching to Single paused all players.
- Browser testing caught and fixed Gradio's rewritten `:is()` specificity on mobile controls, an overlapping mobile orphan footer, and an invisible status wrapper intercepting Listen controls. An independent source review also caught the ancestor mode-change playback issue; regressions cover each fix.
- Evidence: `Temp/aligned-browser-qa-final.md`, `Temp/alignment-parent-tests.log`, `Temp/aligned-wide-latest.jpg`, `Temp/aligned-mobile-latest.jpg`, and `Temp/aligned-resized-textarea.jpg`.
- Production 8013 restarted successfully with the aligned configuration (HTTP 200). Existing disk audio and voices were retained. No push or merge.
- The existing production browser tab was reloaded once after restart. Clone, Design, Single and Multiple loaded normally; it was left on Generate > Multiple with an exactly aligned initial paragraph/placeholder and no generated test audio. Screenshot: `Temp/aligned-production-ready.jpg`. The isolated QA tab and server were closed.


## Responsive generation and serial regeneration queue

- Full Generate and per-clip Regenerate no longer make the editor/importer inert. Source text, draft paragraphs, shared settings, New seed, Add clip and navigation remain usable.
- During a per-clip request only that paragraph's text and seed are read-only (still focusable/selectable), its Remove control is disabled, and duplicate submissions for active/queued rows are blocked. Full Generate and destructive import replacement/undo wait until the queue finishes. Full Generate temporarily disables removal/regeneration without freezing draft inputs.
- Other generated rows can enqueue Regenerate. Each row shows Regenerating or its FIFO queue position. Each job waits for the preceding prepare, state/ZIP commit and cleanup, avoiding shared-state candidate races.
- A queued job captures its seed and batch identity. Text and shared settings are read when the job starts, as stated beside the queued seed. New seed and queued draft seed edits choose a future take; they cannot invalidate the captured job or be overwritten by its completion. The active row remains protected against manual seed/text edits. The wheel guard preserves that read-only ownership.
- Removing a queued row cancels its queued request, leaving existing audio under Previous clips. A failed request retains its prior audio and still advances the queue. Batch, row identity, text and revision guards remain in place. Queued jobs continue under their originating Generate/Multiple operation if the user visits another mode.
- Red regressions were observed for the global editor lock, captured seed dispatch/commit, changed batch rejection and number-wheel read-only cleanup before the fixes. Final automated checkpoint: all 177 Python tests, all 15 JavaScript scripts and `git diff --check` passed. Existing optional SoX/flash-attn and Gradio event-loop warnings remain non-fatal.
- Live port-8016 fixture used production UI/callbacks with synthetic voice input and copied, uniquely named existing QA audio. Full generation allowed source/delivery changes, a paragraph edit and Add clip without losing those drafts. No new neural inference was needed for this UI/state change.
- A three-job run used captured seeds 111, 222 and 333, in order, at least 12 seconds apart. The active seed accepted focus and Ctrl+A but typing did not change it. New seed remained clickable and its future value survived commit. A queued paragraph edit reached the later generation callback. All resulting clip URLs were distinct and the ZIP manifest retained the three captured seeds.
- Failure/recovery check retained the failed first clip's exact URL, updated the second clip, skipped the removed queued third clip and retained that third audio as an orphan. Import replacement stayed disabled while source editing and Cancel worked. Navigation to Design, editing its future draft and returning to Multiple did not interrupt the queue. Play all and Stop worked afterward.
- Evidence: `Temp/queue-pending.png`, `Temp/queue-qa-calls.jsonl`, `Temp/queue-python-tests.log`. The isolated QA tab and fixture server were closed.
- After the user explicitly requested restarts after fixes and said not to retain the live clips, production port 8013 was restarted and its existing browser tab refreshed. The new queue script and queued-workflow binding were verified in the served config, and the UI loaded normally. Existing disk audio/voices and prior uncommitted changes are untouched. No push or merge.


## 2026-11-10 confirmation, playback and timing follow-up

The current behavior and expanded verification are documented in [PLAYBACK-TIMING-VERIFICATION.md](PLAYBACK-TIMING-VERIFICATION.md). That follow-up supersedes earlier descriptions of disabled Play all and regeneration-only row buttons.
