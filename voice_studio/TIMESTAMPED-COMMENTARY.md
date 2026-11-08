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
- Batch clips use the same themed Gradio Audio waveform player as single commentary. Play all advances through the player's official end-of-media event. Shared delivery instructions, language and generation settings appear above both modes. Generation disables the Generate button until success or failure finishes, including when previous outputs exist. The later progress-bar update below supersedes the earlier generic busy notice.

## Submission feedback audit
Generate, Clone reference & generate, Save as new voice, hidden legacy Save voice, Unload model and Use this folder have busy labels, disabled submission controls and error-safe restoration. Screen-reader busy attributes and live status announcements share the same filled spinner styling (reduced-motion respected). Folder errors stay inside the picker dialog. Navigation, reset defaults, playback and download controls remain immediate actions rather than showing artificial loading.

Verification: 72 Python tests; delayed local synthetic browser checks for generation, clone failure, save failure, successful unload and invalid folder confirmation. Real model inference was not repeated for this UI lifecycle change.

## Paragraph import
The timestamped tab accepts an uncapped source script. Split on blank lines (including whitespace-only separators); trim paragraphs, retain internal single line breaks, start at 00:05, then add 0.08 seconds per preceding Unicode character, including internal spaces and punctuation. Integer centiseconds prevent accumulated rounding drift; only displayed timestamps round to whole seconds. These are editable estimates, not duration guarantees.

Existing nonempty or retimed rows require explicit replacement confirmation. Cancel preserves them; source text is never cleared. Undo toggles between the previous and imported rows. Current generation limits remain 100 clips and 2,000 characters per clip: oversized imports explain how to split the script and leave all existing content intact.

Single commentary visibility is now owned by the tab itself rather than a delayed server callback. Both directions retain the shared 220ms presence transition and reduced-motion behavior. Browser verified empty source, whitespace separators, trimming, editable rows, confirmation/cancel/undo, retained source across tabs, and imported 3-clip synthesis using synthetic audio. Deterministic parser tests cover Unicode, timing drift and limits; 73 Python regression tests pass.

## Readiness, cursors and progress bar
Generate commentary is disabled until a .pt voice and valid commentary are present. Timestamped mode requires every row to have valid minutes, seconds and text; shared numeric settings are validated too. Cloning or generating keeps it disabled, and completion/error rechecks the current inputs rather than blindly enabling it. A local readiness guard also handles Gradio dynamic-player renders.

Disabled and busy controls use the normal default cursor, not wait/prohibited cursors. Available buttons retain a pointer and accessible busy labels remain. Listen & export again uses the original actual generation progress bar with current clip/count/percentage rather than the replacement generic loading notice.

Verified with 78 Python tests and delayed synthetic browser inference: required/empty/missing-voice inputs, invalid/repaired timestamp, single and batch success/error recovery, disabling during generation, current-input revalidation after completion, and multi-clip progress updating through clip 3/3. Browser control scan found no wait/not-allowed/progress cursors. Synthetic preselected voice avoids changing Chrome local-file access permissions. No real GPU inference or acoustic-quality claim is made for this UI update.

## Voice removal and unload recovery
Status messages now retain an inert visual snapshot while their height, opacity and surrounding gap collapse over 220ms; clearing a voice no longer drops its status before the exit animation. Nested Markdown remains visible, interrupted transitions clean up their snapshot, and reduced-motion skips animation. Browser checks repeated selected-fixture clears and measured status heights down to zero with no leftover ghost.

Unload now returns immediately with a busy message if a model operation owns the lock, rather than waiting through a batch. It bypasses the generation queue, has a no-model fast path, and releases its lock after errors. Fixed a separate frontend race where Gradio restored interactivity before the busy label, allowing the busy guard to leave the button disabled. Browser verified actual no-model response and enabled button afterward; unit tests cover loaded/busy/error paths without model weights. 83 Python tests and five JavaScript suites pass. No active user generation was interrupted for deployment.

### Full picker/status coordination audit
A later full-interaction frame trace revealed that independent smooth animations could still move Delivery instruction down then back up: the empty picker expanded immediately, while status clearing waited for its server callback; unrelated status mutations also restarted picker animation. Selected-voice status now starts exiting from local picker state in the same update, and unchanged selected/empty state cannot restart picker geometry motion. Reference-audio animation behavior remains otherwise unchanged.

Two repeated selected→empty runs on the isolated browser fixture measured Delivery instruction y=542.50→544.28→544.56→544.64→544.66 and 542.50→544.42→544.59→544.64→544.66, with no upward reversal, no leftover visual snapshot and Generate disabled after clear. Reduced-motion still bypasses both animations. Live 8014 was deliberately not restarted because the user's session must be preserved until they permit refresh.

### Drawer overlay exits
Use via API and Settings now animate their backdrop opacity together with the drawer panel for180ms, including outside-click, Escape and explicit close. Closing during entry starts from the current visual state; reduced-motion closes immediately. Focus returns to the opener. Also narrowed the close selector to the banner's direct child button, avoiding accidentally targeting API Recorder inside the API heading.
Browser verified Settings outside/Escape and API outside/close paths, with backdrop opacity traces1→0.63→0.35→0 and opener focus restored. Unit test verifies coordinated duration, deferred close and reduced-motion.8014 remains unchanged; real preview8016 was opened without interrupting it. The final API close-selector correction requires restarting8016 after the user permits refresh.

### Corrected full-page dim layer target
Correction to the preceding drawer verification: Gradio's `.backdrop` is a transparent click target. Actual dimming is painted by the full-page `.api-docs` background. The animation now changes that background alpha, independently of the sliding panel. Verified on real app8017: Settings dim alpha0.5→0.176→0.035→0.004→removed; API0.5→0.098→0.035→0.004→removed. Both restore focus to opener. Earlier8016 only faded the transparent target; it is not the corrected version.8017 is the latest real preview, opened without stopping8014 or8016 or refreshing user inputs.

### Left-side utility drawers
Both utility drawers now anchor at the left edge and translate from/to -100%, retaining actual full-page dim fade, click/Escape dismissal, focus return and reduced-motion handling. Browser frames verified x=-1150→-402→-77→0 entering, x=0→-923→-1106 exiting. Both drawers fit a390px viewport without overflowing; viewport restored afterward. Latest real preview8018 opened without restarting older sessions.

## Inline native utility sections (2026-11-08)
Use via API and Settings now mount the original native Gradio components inside the existing animated accordion design at the page end. Native controls and API documentation are retained, not recreated. Collapsing retains their state; native recorder-triggered close remains supported. Duplicate footer triggers are hidden, but recording stop controls remain available.

Verification: 83 Python tests and seven JavaScript suites passed. Browser verified both sections rendered original content, API JavaScript tab updated examples, settings checkbox state survived collapse/reopen, native close binding and footer hiding. Fixed cross-observer feedback and asynchronous API banner binding discovered during testing. No GPU generation, screen recording, PWA installation or theme-navigation test was performed. Frame-by-frame animation measurement was not completed (browser read-only evaluation lacks requestAnimationFrame); existing accordion CSS and reduced-motion rules are reused. Final pending-open guard is unit tested, not yet freshly browser tested. Preview 8019 is isolated; earlier user previews remain untouched.

## Clone readiness and utility theme (2026-11-08)
Clone reference & generate now starts disabled and requires a loaded reference, valid shared single commentary (1–2000 characters), valid numeric settings, and transcript only when Include reference transcript is checked. It stays disabled in timestamped mode and during either generation operation. Original backend validation/busy/error handling remains intact. Reference readiness comes from the actual Gradio Audio change event, not a guessed filename or visual player presence.

Filled dark utility content styling extends to native buttons, selected controls, code blocks, dropdown surfaces, and checkboxes. Original API endpoints/code tabs/copy/recorder and Settings theme/language/PWA/recording components remain native. Verified in browser: missing reference stays disabled; synthetic reference loaded through real Gradio update enables with transcript unchecked; missing required transcript disables; supplied transcript enables; batch disables, return to single enables; empty numeric setting disables, restoring enables; clearing reference disables; no console errors. Synthetic fixture was local silence, no private voice used and no GPU generation invoked. API cURL switching and Settings checkbox retention across keyboard/click collapse verified. Busy/error recovery covered by unit suites, not a new GPU run. Theme navigation/screen recording/PWA and every copy control not individually exercised.
