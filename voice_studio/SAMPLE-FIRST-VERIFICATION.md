# Sample-first verification — November 9, 2026

- Recovered four interrupted uncommitted implementation files atop 0727899.
- Python: 108 tests passed with NUMBA_DISABLE_JIT=1; all JavaScript test_*.cjs suites passed.
- Real cached-model smoke: 20.927 seconds. Design produced a 2.48s/24kHz sample, explicit save produced .pt, Generate produced 2.08s + 2.80s timed clips and ZIP. Clone produced 2.40s sample and explicit save retained the exact original speaker embedding. No .pt existed before explicit save. Release=true unloaded; release=false retained Base until explicit cleanup.
- Real-smoke receipt/artifacts remain locally in Temp/sample-first-real-20261109-170828/. These were isolated from user output/voice folders. WAV validity checked; no claim of listening or transcript accuracy.
- Browser at 8013: Clone and Design expose single text only; Generate exposes single and timestamped. Entered timed draft survived Clone/Design and was restored in Generate. Fixed a real restoration race where Gradio temporarily removes tab buttons during layout.
- Width bug reproduced on actual outer audio/transcript/description containers: 522.328125 -> 522.5 -> 522.328125 CSS px. Root cause: integer clientWidth-derived minimum overrode fractional form width.
- After fix, visible forms and outer fields stayed at 522.328125px desktop and 534px at 760px viewport in both directions (0 indicates fully hidden, not interpolated width). Sampled actual animation frames; opacity continued changing. Narrow captures had 5–6 sampled frames over 500ms. Desktop captures included intermediate fades and settled endpoints.
- Unit regression tests cover fractional geometry, rapid reversal, narrow/desktop, reduced motion and retained inputs. Existing fade/move/height/delivery animations retained.
- Temporary browser measurement code removed after verification. No push or merge.
