# VoiceDesign parity audit

Audited against `qwen_tts/cli/demo.py` (`build_demo`, its `voice_design` branch, `build_parser`, and `_collect_gen_kwargs`), `qwen_tts/inference/qwen3_tts_model.py` (`generate_voice_design`), `qwen_tts/core/models/modeling_qwen3_tts.py` (supported languages), `README.upstream.md` (Voice Design then Clone), and the local `Start-VoiceDesign.ps1` launcher. The upstream `build_demo` Gradio configuration was also built with the cached VoiceDesign checkpoint's language map to verify its actual components and initial values. No upstream source was changed.

## Upstream VoiceDesign GUI

| Upstream component | Voice Studio Design tab |
| --- | --- |
| Text, four lines, with a starter example | Shared central Commentary text, four lines, required and at most 2,000 characters. The original sample is not prefilled so switching modes never replaces the user's script. |
| Language, default Auto | Shared central Language dropdown; all 11 choices are present. It starts at English, Voice Studio's established default, and retains the user's selection through mode switches. |
| Voice Design Instruction, three lines, with a starter example | Voice design instruction, three lines, required; the upstream example is a placeholder so an unedited example is never submitted |
| Generate button | Shared central Generate commentary button routes to the selected workflow, with a busy state. |
| Output Audio player | Shared Generated audio player and WAV download |
| Status textbox | Shared status message; reports validation, model, and generation errors and the saved output path |
| Checkpoint and model-type header | Read-only Base and VoiceDesign model/cache fields in General settings |
| Global disclaimer | Voice Studio's local-use and rights guidance is in its README. This is informational text, not a generation control. |

The upstream dropdown builds its choices from `model.get_supported_languages()`. The cached 1.7B VoiceDesign checkpoint exposes Auto, Chinese, English, German, Italian, Portuguese, Spanish, Japanese, Korean, French, and Russian. Voice Studio exposes exactly that set. The voice instruction initially has an empty value and displays the upstream example as a placeholder. The shared script and language keep Voice Studio's established initial state, so mode changes preserve entered commentary and settings.

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

The upstream GUI has no sampling controls; its eight CLI overrides are set at launch and forwarded to every call. Voice Studio exposes them in one shared Generation settings section along with both sampling switches and a Reset sampling defaults button. The ten initial values match the cached VoiceDesign `generation_config.json`. Seed and Release GPU memory after generation are Voice Studio controls, not upstream GUI or CLI controls. The call uses `generate_voice_design(text, language, instruct, **generation_options)` with the VoiceDesign checkpoint, never Base's private instruction route.

The API also accepts `non_streaming_mode=False`, which currently simulates streaming text input rather than providing true streaming generation. The upstream GUI and CLI leave it at its default `True`; Voice Studio does the same. List-valued batch inference and arbitrary Transformers `generate` kwargs exist in the Python API and examples, but are not controls in the upstream VoiceDesign GUI. Voice Studio's shared timestamped workflow generates each Design clip sequentially with the real VoiceDesign model and the shared settings; Clone and saved Base voices use that same clip editor and output panel.

## Operator settings and output

| CLI or local launcher option | Voice Studio behavior |
| --- | --- |
| Positional checkpoint / `-c`, `--checkpoint` | Separate local Base and VoiceDesign caches; `VOICE_STUDIO_MODEL_CACHE` and `VOICE_STUDIO_DESIGN_MODEL_CACHE` may override them. No automatic weight download. |
| `--device cuda:0`, `--dtype bfloat16` | Fixed CUDA:0 and bfloat16, matching the local VoiceDesign launcher. |
| `--flash-attn` / `--no-flash-attn` | FlashAttention disabled, matching the local launcher rather than the CLI default. |
| `--concurrency` | One queued operation, matching the local launcher. |
| `--ip`, `--port`, `--share` | Loopback only, configurable `VOICE_STUDIO_PORT`, sharing disabled. |
| `--ssl-certfile`, `--ssl-keyfile`, `--ssl-verify` | Local HTTP instance; these HTTPS deployment flags are not per-take voice settings. |

Preview WAV and JSON settings metadata use the configured Outputs directory. The upstream README's Voice Design then Clone workflow is provided through the shared Save as new voice action for a single take: after listening, the user confirms or corrects the spoken transcript, then Base encodes the preview into a reusable `.pt` prompt in the configured Voices directory. It does not train a persistent VoiceDesign identity or guarantee identical delivery on later text. In Clone and Design, the saved voice `.pt` selector is hidden; Generate reveals it. Shared commentary, settings and timestamped clip values remain mounted across mode changes. Design uses the same dark, filled, rounded form controls and panels as those workflows.
