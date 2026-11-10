# Numeric-field wheel verification

Verified on 2026-11-09 in the `feature/multiple-clip-combine` worktree.

## Change

- One passive, capture-phase wheel guard applies to all native number inputs, including dynamically added controls and inputs reached through an open shadow root's event path.
- The input is readonly only during the wheel's default processing, so the wheel scrolls natively without changing the value or moving keyboard focus. Editing events restore the input immediately, even before the next animation frame.
- Number types, labels, bounds, integer/decimal steps and existing validation remain intact. Range sliders and ordinary text controls are untouched. No animation code changed.

## Automated verification

- The new JavaScript regression was observed failing before implementation.
- 143 Python tests passed, including real UI registration and numeric-component contract checks.
- All 11 JavaScript regression scripts passed, including repeated wheel events, stale restoration callbacks, focus/editing, dynamic inputs, composed shadow paths, existing readonly/disabled fields, slider exclusion and Ctrl-wheel zoom.
- Independent read-only review found no actionable issue.

## Live Chrome verification

- Before the fix, scrolling over focused Seed changed 42 to 41 while page scroll stayed at 199.
- After restarting port 8013, the same focused Seed gesture kept 42 and moved page scroll from 199 to 390, preserving focus.
- The Temperature numeric companion kept 0.85 while scrolling from 726 to 869. Keyboard slider stepping produced 0.90 and mouse dragging produced 1.35; resetting sampling defaults still worked.
- The existing isolated port-8014 fixture loaded previously generated QA audio into the normal production UI. No new inference was necessary.
- A newly added clip's seconds stayed at 12 during focused scrolling (1556 to 1691); ArrowUp changed it to 13. Unfocused upward scrolling kept 13 (1669 to 1534).
- Total-duration seconds stayed at 15 during focused scrolling (280 to 414); ArrowUp changed it to 16. Unfocused scrolling kept 16 (134 to 269).
- Native clip seconds validation still reported range overflow for 60 with max 59, and alphabetic typing did not change a valid 13. Seed accepted -1 and ArrowUp produced 0.
- Numeric controls retained their accessible spinbutton labels/roles. No dedicated screen-reader or cross-browser qualification was performed; shadow retargeting was exercised in the JavaScript regression rather than a live shadow fixture.
- The normal app was restarted and the user's existing port-8013 tab reloaded. Temporary QA tabs and the port-8014 fixture were closed. No push, merge, or voice-file changes.

Environment warnings remain unchanged: optional SoX and flash-attn are absent; Gradio tests emit unclosed-event-loop ResourceWarnings. No test failed.
