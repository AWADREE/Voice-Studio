# Screenshot provenance and documentation checks

Captured on **2026-11-10** from the production Voxover UI at main commit `8a57b4b228b406addd6a9410e78b20a59ffe8e46`.

## What the images show

| File | View |
| --- | --- |
| `clone-workspace.jpg` | Clone reference inputs, shared commentary controls, and the empty Listen panel. |
| `design-workspace.jpg` | A fictional documentary-narrator description with shared audition text. |
| `multiple-workspace.jpg` | Imported fictional paragraphs and a successful 12-second combined timeline. |
| `clip-editor.jpg` | Two paired paragraph/player rows, editable seeds, and the second take's Updated state. |

These are actual Chrome screenshots of `app.build_ui()`, cropped at capture time to the relevant app regions. The application markup and styles were not replaced with a mockup. An isolated localhost fixture preselected a **synthetic, non-personal** voice prompt and replaced only the speech-generation callback with locally synthesized test tones. Normal import, batch, per-row replacement, ZIP, and Combine callbacks produced the displayed UI state.

**The waveforms are test tones, not Qwen speech or evidence of voice quality.** Clone and Design were shown before inference. No microphone capture, personal voice files, external uploads, model downloads, or live-session resets were used. Only JPEG screenshots are distributed; fixture prompts, audio, archives, logs, and the temporary runner stay outside the tracked documentation.

The timeline image was captured before the second clip was regenerated. The editor image shows that later replacement. As in the real app, regeneration leaves the previous combined snapshot unchanged until Combine is pressed again.

## Validation

- Fresh **214 Python tests passed** with Python 3.12 and `NUMBA_DISABLE_JIT=1`.
- All **18 `test_*.cjs` JavaScript scripts passed**, including **2,121** artwork-boundary geometry cases.
- The screenshot session exercised mode switching, paragraph splitting, Randomize, full batch generation, a successful 12-second Combine, and confirmed replacement of the second clip. Synthetic WAVs were used; no fresh neural inference was run.
- Documentation paths, heading anchors, image readability, upstream README preservation, and whitespace were checked separately from application tests.

Known non-failing test warnings: missing optional flash-attn, existing unclosed-file/event-loop ResourceWarnings, and an upstream Gradio notice about constructor parameters moving to `launch()`. The browser fixture also emitted existing Starlette HTTP status-name deprecation warnings.

This documentation task did not repeat a fresh dependency installation, GPU model inference, microphone/recording tests, or browser download-save completion. For historical real-model and broader browser evidence, use the verification links in the [app guide](../../voice_studio/README.md#tests-and-verification).
