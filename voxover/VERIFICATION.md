# Verification

Date: 2026-11-08. Isolated checkout and port; original installation untouched.

- 44 Python unit/integration tests pass. Synthetic (non-personal) voice fixture. Most inference tests mock the model; storage round-trip writes actual WAV/JSON/PT files under ignored test storage.
- JavaScript tab-transition regression passes four viewport/reduced-motion combinations, animation cancellation, rapid reversal, width stability, inert state, and picker guards.
- Real CUDA smoke test using the fork's qwen_tts package: existing local voice prompt -> 24 kHz PCM24 WAV -> clone that generated reference using its exact transcript -> new saved prompt and second commentary WAV. Source prompt hash unchanged; model released afterward. Generated personal artifacts are not included.
- Isolated HTTP configuration: 141 components, 25 dependencies, expected endpoints. Three bundled fonts return HTTP 200.
- Personal voice/audio/model/cache/settings/logs excluded from tracked contents. The authorized original generated background and matching animation are included, with portable asset URLs.

These checks establish execution and wiring, not subjective voice quality or that the experimental delivery prompt always works. Full manual browser verification of every waveform/trim/microphone interaction remains necessary before replacing a live installation. Existing installation and launcher remain available and were not switched.

## Original-theme publication verification

Owner-authorized original generated raster matches the existing installation byte-for-byte (SHA256 6f3367fb6c206e4b79c85ebd7945083b7d06988fe07713f07a3c0c4b995721a3), with no embedded PNG metadata. A clean tracked-only checkout passed all 44 Python tests, the tab-transition test, and 2,121 bounded-art-drift geometry cases. The original theme is now self-contained and does not require ignored local assets. Personal runtime data remains excluded.

Clean-checkout headless Chrome verification passed: original raster and all three fonts HTTP 200 from that checkout, original celestial background visually inspected, Clone/Generate tabs functional, zero page JavaScript errors. Verification server stopped afterward.
