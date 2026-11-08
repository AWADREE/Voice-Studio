# Verification

Date: 2026-11-08. Isolated checkout and port; original installation untouched.

- 44 Python unit/integration tests pass. Synthetic (non-personal) voice fixture. Most inference tests mock the model; storage round-trip writes actual WAV/JSON/PT files under ignored test storage.
- JavaScript tab-transition regression passes four viewport/reduced-motion combinations, animation cancellation, rapid reversal, width stability, inert state, and picker guards.
- Real CUDA smoke test using the fork's qwen_tts package: existing local voice prompt -> 24 kHz PCM24 WAV -> clone that generated reference using its exact transcript -> new saved prompt and second commentary WAV. Source prompt hash unchanged; model released afterward. Generated personal artifacts are not included.
- Isolated HTTP configuration: 141 components, 25 dependencies, expected endpoints. Three bundled fonts return HTTP 200.
- Personal voice/audio/model/cache/settings/logs excluded from tracked contents. The authorized original generated background and matching animation are included, with portable asset URLs.

These checks establish execution and wiring, not subjective voice quality or that the experimental delivery prompt always works. Full manual browser verification of every waveform/trim/microphone interaction remains necessary before replacing a live installation. Existing installation and launcher remain available and were not switched.
