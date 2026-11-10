# Startup splash verification

2026-11-10, local feature/multiple-clip-combine worktree. No push.

- Replaced the stock orange Gradio startup logo with a gold/ice-blue waveform, Voxover title, navy background and the existing bundled artwork.
- Scoped entirely to the native startup tracker containing its additional-loading-text slot. Gradio still owns completion and error states; no new JavaScript, timers, minimum display time or component-loader changes.
- Reduced-motion media rule stops waveform movement while preserving the loading text.
- Real localhost:8013 startup screenshots verified at 1905px desktop and 390px mobile widths. In both cases the branded loader appeared, then was removed and the normal UI became available (zero boot loaders remaining).
- Restarted the normal app on 8013 with the completed randomizer changes. Verified live Randomize disables shared Seed and reveals Clip seed plus New seed before generation.
- Focused loader/packaging tests: 6 passed. git diff --check passed. Randomizer worker separately verified 187 Python tests and all 16 JS test scripts before this CSS-only change.
- Style detector found no issues in the new startup block; existing unrelated border/layout-animation warnings remain.
- Existing missing-SoX/flash-attn warnings remain. No GPU inference performed by this splash update.
