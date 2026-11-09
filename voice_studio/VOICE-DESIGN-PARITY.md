# VoiceDesign parity audit

Reference: `qwen_tts/cli/demo.py`, `voice_design` branch and `_collect_gen_kwargs`, in this checkout.

| Reference GUI or CLI control | Voice Studio Design tab |
| --- | --- |
| Text (required) | Preview text (required, 1–2000 characters) |
| Language (default Auto) | Language (default Auto, same language list) |
| Voice Design Instruction (required) | Voice design instruction (required) |
| Generate, audio, status | Design voice & preview, shared Listen & export audio/WAV/status |
| Optional CLI generation overrides: maximum new tokens, temperature, top-k, top-p, repetition penalty, subtalker top-k, top-p, temperature | Generation settings accordion, forwarded through `generate_voice_design` |
| Model generation defaults | Same ten controls and defaults already present in Voice Studio, including speech and subtalker sampling switches |
| CLI checkpoint, device, dtype, FlashAttention, concurrency, server and SSL options | Local VoiceDesign cache; fixed CUDA:0, bfloat16, no FlashAttention, one queued request, local server. These are deployment settings, not per-take GUI controls. |

Design preview uses `generate_voice_design(text, language, instruct, **generation_options)` with the VoiceDesign checkpoint. Its WAV and settings metadata go to the configured Outputs directory. A successful preview populates the shared confirmation flow. Listen and confirm the captured script, or correct the actual spoken words, before saving it as a reusable Base voice prompt. Saving loads Base to encode the audio; subsequent generation uses that saved prompt. The saved file is a reference prompt, not a persistent VoiceDesign identity. Mode changes in the header preserve the existing Clone and Generate forms and values. The separate hidden legacy API endpoints retain their prior contracts.
