# Combine display refinements

Verified 2026-11-10 on feature/multiple-clip-combine.

- Multiple Listen paints the controls and individual audio cards, leaving the shared-row empty space transparent so the app's animated sky is visible. Existing loading, transitions and Updated outline/gradient remain.
- A small persistent status directly under Combine shows the minimum whole-second duration. It uses the maximum current timestamp plus actual WAV frames, rounded upward with integer sample arithmetic. Source/format checks are shared with export; changed commentary, row counts or impossible limits show guidance rather than a misleading minimum. It refreshes after edits and full/individual generation while the last combined output remains untouched.
- Previous clips has a counted, keyboard-accessible disclosure, collapsed initially. Native audio cards stay mounted; hidden cards consume no grid tracks. Play all excludes collapsed cards, and collapsing pauses hidden previous audio without interrupting visible matched audio.

## Verification

- New minimum/status/layout regressions failed before implementation. Final run: 183 Python tests and all 15 JavaScript scripts passed. git diff --check passed. Independent read-only review found no substantive issue.
- Production UI in isolated port-8017 fixture used synthetic test voice plus existing real QA WAVs, not new neural inference. Initial minimum 0:18 updated to 0:23 when the last timestamp moved from 15 to 20 seconds. Actual clip end 22.080: 22 seconds was rejected and exactly 23 succeeded. The hint stayed separate from export results/errors.
- Editing commentary invalidated the hint; individual regeneration restored a correct minimum. Removing a paragraph showed the existing row-count validation and kept the exact prior combined URL through a failed Combine.
- Desktop paragraph/audio pairs retained 0px top and height differences. Gap computed transparent and visibly showed the animated sky. At 390px, matched pairs/Add/Previous/orphans occupied distinct tracks with 20px gaps and no horizontal overflow. Mouse expansion and Enter-key collapse worked.
- Independently played previous audio advanced to 0.232842 seconds, then collapse paused it at 0.430791 seconds. Node tests additionally cover visible audio continuity, hidden-player sequence adjustment, stale completions and no auto-resume.
- Normal app port 8013 restarted (HTTP 200) and existing browser tab refreshed, left in Generate / Multiple. Disk audio/voices and existing uncommitted work retained. No push or merge.
- Local QA images: Temp/previous-clips-collapsed.png and Temp/combine-minimum-background.png. Existing optional SoX/flash-attn and Gradio event-loop warnings remain non-fatal.

## Listen border consistency correction (2026-11-10)

- Removed the visible outline from Multiple Listen controls and generated clip surfaces by matching the transparent section-border treatment. Border width and all padding/layout rules stay unchanged, preserving alignment and the transparent shared-track gap.
- Browser computed-style assertion failed before the fix (Listen rgb(54,80,101), Generate transparent) and passed after the normal port-8013 restart. Visually checked both the live Listen controls and generated/previous audio cards in the isolated fixture.
- Fixture verified all three generated cards have transparent borders, minimum duration still reports 0:18, and a removed third clip is initially collapsed under Previous clips (1) and expands correctly.
- Full validation: 183 Python tests passed; all 15 JavaScript test scripts passed; git diff --check clean. Existing optional SoX/flash-attn and Gradio warnings remain non-fatal. No push or merge.
