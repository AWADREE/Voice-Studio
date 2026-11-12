# Consistent commentary widths verification

Date: 2026-11-11.

- User requested reverting the unrequested Generate/Listen width change between Single commentary and Multiple.
- Multiple now inherits the original shared 2:1 desktop grid. Both tabs stack at 1299 CSS pixels, and the alignment coordinator uses the same breakpoint.
- Removed padding/border from Multiple's transparent Listen wrapper. Its separately painted controls now occupy the same width and horizontal position as the original Single Listen card.
- Shared subgrid rows, stable player identities, existing animations, seed controls, and unrelated current changes remain in place.

## Regression evidence

- Before the fix, the read-only browser probe failed on the 1:1 Multiple ratio. The added JavaScript boundary test also failed at 1299px because rows remained side by side.
- A second visual-card assertion failed before removing the redundant Listen wrapper inset.
- Final browser checks passed at actual CSS viewport widths 1600, 1300, 1298, 1000, 900 and 390. Single and Multiple retained equal corresponding section widths and x coordinates, including the painted Listen card. No horizontal document overflow.
- An isolated local fixture mocked speech inference with synthetic two-second tones and retained real Gradio player rendering. Three generated paragraph/player pairs stayed aligned at all checked widths. Wide pair top/height differences were 0px, including with Generation settings expanded. Narrow players followed their own paragraphs without overlapping the next paragraph.
- Final native-size check at 2400 CSS pixels passed: Generate 1221.35px, Listen 610.66px in both tabs.
- Exact 1299/1300 coordinator boundaries are covered by test_clip_alignment.cjs. Browser viewport overrides were reset after QA.
- Final complete suite: 241 Python tests and 21 JavaScript suites passed; git diff --check passed. Existing optional SoX/flash-attn and event-loop warnings remain non-fatal.
- Normal app servers 8003 and 8013 were restarted with final code and returned HTTP 200. The isolated fixture on 8019 was stopped. No user audio was generated or changed by this verification.
- Screenshot: Temp/width-restored-multiple.jpg. Python output: Temp/width-revert-python.log. Reusable read-only browser probe: test_commentary_widths.browser.js.
- No commits, pushes, merges or deployment were performed.