# VoiceDesign parity audit

Audited against `qwen_tts/cli/demo.py` (`build_demo`, its `voice_design` branch, `build_parser`, and `_collect_gen_kwargs`), `qwen_tts/inference/qwen3_tts_model.py` (`generate_voice_design`), `qwen_tts/core/models/modeling_qwen3_tts.py` (supported languages), `README.upstream.md` (Voice Design then Clone), and the local `Start-VoiceDesign.ps1` launcher. The upstream `build_demo` Gradio configuration was also built with the cached VoiceDesign checkpoint's language map to verify its actual components and initial values. No upstream source was changed.

## Upstream VoiceDesign GUI

| Upstream component | Voice Studio Design tab |
| --- | --- |
| Text, four lines, with a starter example | Preview text, four lines, with the same starter example; required, at most 2,000 characters |
| Language, default Auto | Language, default Auto; all 11 choices are present. Voice Studio retains its established choice order. |
| Voice Design Instruction, three lines, with a starter example | Voice design instruction, three lines, with the same starter example; required |
| Generate button | Design voice & preview button, with duplicate-request guard and busy state |
| Output Audio player | Shared Generated audio player and WAV download |
| Status textbox | Shared status message; reports validation, model, and generation errors and the saved output path |
| Checkpoint and model-type header | Read-only Base and VoiceDesign model/cache fields in General settings |
| Global disclaimer | Voice Studio's local-use and rights guidance is in its README. This is informational text, not a generation control. |

The upstream dropdown builds its choices from `model.get_supported_languages()`. The cached 1.7B VoiceDesign checkpoint exposes Auto, Chinese, English, German, Italian, Portuguese, Spanish, Japanese, Korean, French, and Russian. Voice Studio exposes exactly that set. Upstream's example text and instruction are starter values, so they are now present as initial field values rather than placeholders.

## Generation settings

| Upstream source | Voice Studio setting |
| --- | --- |
| `--max-new-tokens` | Maximum new tokens |
| `--temperature` | Temperature |
| `--top-k` | Top-k |
| `--top-p` | Top-p |
| `--repetition-penalty` | Repetition penalty |
| `--subtalker-temperature` | Subtalker temperature |
| `--subtalker-top-k` | Subtalker top-k |
| `--subtalker-top-p` | Subtalker top-p |
| Model generation config and `generate_voice_design` API | Enable speech sampling (`do_sample`) and Enable subtalker sampling (`subtalker_dosample`) |

The upstream GUI has no sampling controls; its eight CLI overrides are set at launch and forwarded to every call. Voice Studio exposes them per take along with both sampling switches and a Reset sampling defaults button. The ten initial values match the cached VoiceDesign `generation_config.json`. Seed and Release GPU memory after generation are Voice Studio controls, not upstream GUI or CLI controls. The call uses `generate_voice_design(text, language, instruct, **generation_options)` with the VoiceDesign checkpoint, never Base's private instruction route.

The API also accepts `non_streaming_mode=False`, which currently simulates streaming text input rather than providing true streaming generation. The upstream GUI and CLI leave it at its default `True`; Voice Studio does the same. List-valued batch inference and arbitrary Transformers `generate` kwargs exist in the Python API and examples, but are not controls in the upstream VoiceDesign GUI. Design is a single preview workflow, with the established separate timestamped commentary workflow retained for saved Base voices.

## Operator settings and output

| CLI or local launcher option | Voice Studio behavior |
| --- | --- |
| Positional checkpoint / `-c`, `--checkpoint` | Separate local Base and VoiceDesign caches; `VOICE_STUDIO_MODEL_CACHE` and `VOICE_STUDIO_DESIGN_MODEL_CACHE` may override them. No automatic weight download. |
| `--device cuda:0`, `--dtype bfloat16` | Fixed CUDA:0 and bfloat16, matching the local VoiceDesign launcher. |
| `--flash-attn` / `--no-flash-attn` | FlashAttention disabled, matching the local launcher rather than the CLI default. |
| `--concurrency` | One queued operation, matching the local launcher. |
| `--ip`, `--port`, `--share` | Loopback only, configurable `VOICE_STUDIO_PORT`, sharing disabled. |
| `--ssl-certfile`, `--ssl-keyfile`, `--ssl-verify` | Local HTTP instance; these HTTPS deployment flags are not per-take voice settings. |

Preview WAV and JSON settings metadata use the configured Outputs directory. The upstream README's Voice Design then Clone workflow is provided through the shared Save as new voice action: after listening, the user confirms or corrects the spoken transcript, then Base encodes the preview into a reusable `.pt` prompt in the configured Voices directory. It does not train a persistent VoiceDesign identity or guarantee identical delivery on later text. Clone, saved-voice generation, and timestamped commentary keep their existing controls and public API contracts. Design uses the same dark, filled, rounded form controls and panels as those workflows.
