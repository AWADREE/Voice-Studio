<p align="center">
  <img src="voice_studio/assets/app-icon/voxover.png" alt="Voxover microphone icon" width="112">
</p>

# Voxover

**Find your voice. Shape every line. Create commentary locally.**

Voxover is a play on *voiceover*: a local workspace for voice cloning, voice design, and spoken commentary.

Voxover is a custom desktop-browser frontend built on [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), developed for creating and refining reusable voices and spoken commentary. It adds a dark, animated interface and a streamlined clone → preview → save → generate workflow. The speech-generation engine and model research are the work of the **Qwen team at Alibaba Cloud**, not this project.

This repository is a fork: the upstream engine and original demo remain available, while the custom application lives in [`voice_studio/`](voice_studio/). This is an independent project, not an official Qwen release.

[Get started](#get-started) · [App guide](voice_studio/README.md) · [Verification](voice_studio/VERIFICATION.md) · [Original Qwen documentation](README.upstream.md)

## What Voxover adds

- **Clone, Design, and Generate:** audition a reference voice or a voice described in words, save the take you approve as a reusable `.pt` prompt, and use it for commentary.
- **Reference audio workflow:** upload or record a reference, include its transcript or use voice-identity-only mode, and generate a sample before saving a reusable voice.
- **Preview and reuse:** listen to commentary, export WAV audio, and re-clone a generated preview into a new voice prompt. An optional transcript correction field lets you match the text to what was actually spoken.
- **A clip-based commentary workflow:** import timestamped scripts, align clips, regenerate individual takes, randomize or reuse per-clip seeds, and combine approved clips.
- **Generation controls:** language, seed, advanced sampling controls, and optional experimental Base delivery instructions.
- **Local file management:** configurable output and voice directories, saved voice downloads, and companion generation-settings JSON files.
- **A consistent workstation UI:** dark filled controls, animated panels, a generated night-sky background, subtle moving artwork and stars, and reduced-motion support.
- **Practical GPU handling:** lazy model loading, a free-memory check, model unloading controls, and single-generation concurrency within this app.
- **Windows conveniences:** a launcher, a bundled multi-resolution icon, and a helper that creates a shortcut beside the app without adding a Start menu entry.

### Scope and honest limitations

The custom UI uses **Qwen3-TTS-12Hz-1.7B-Base** for cloning and saved-voice generation, plus **Qwen3-TTS-12Hz-1.7B-VoiceDesign** for voice design. It has been tested on Windows with an NVIDIA CUDA GPU. Upstream CustomVoice, tokenizer, fine-tuning and other capabilities are documented in the [original README](README.upstream.md).

**Delivery instructions in Base are experimental.** The supported Base wrapper does not expose a plain-text instruction parameter. Voxover uses private formatting/tokenization helpers and passes `instruct_ids` into the shared generation path. Successful audio generation does not prove that the requested delivery was followed, and upstream changes can break this integration.

A saved `.pt` is a reusable voice-conditioning prompt, not a trained model. Saving a generated preview as a new voice re-encodes that audio; it does not fine-tune weights or guarantee identical delivery on future text.

## Get started

### 1. Prepare an environment

Use Python 3.12 and install a CUDA-enabled PyTorch build suitable for your GPU using the [official PyTorch installation instructions](https://pytorch.org/get-started/locally/). Follow the [upstream environment guidance](README.upstream.md#environment-setup) for the engine's dependencies and optional acceleration.

The verified local baseline is documented in the [app guide](voice_studio/README.md). It is not a guarantee for every operating system or GPU. No fresh cross-platform installer qualification is claimed.

```sh
git clone https://github.com/AWADREE/Voxover.git
cd Voxover
python -m pip install -e .
python -m pip install -r voice_studio/requirements.txt
```

Use a separate environment if you already have a working Qwen installation. Do not upgrade its dependencies in place just to try this frontend.

### 2. Download the models separately

Download [Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) into a Hugging Face cache, following the [upstream download instructions](README.upstream.md#released-models-description-and-download). Add [Qwen3-TTS-12Hz-1.7B-VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) if you want the Design mode.

The app uses local model files only and does **not** download weights on startup. Its current resolver expects the standard cache layout: `models--Qwen--Qwen3-TTS-12Hz-1.7B-Base/refs/main` and `snapshots/<revision>/`. A plain standalone folder of weights is not interchangeable with that cache directory.

| Environment variable | Purpose |
| --- | --- |
| `HF_HOME` | Existing Hugging Face cache root; defaults to `~/.cache/huggingface`. |
| `VOXOVER_MODEL_CACHE` | Optional direct override for the Base model's cache directory containing `refs/` and `snapshots/`. |
| `VOXOVER_DESIGN_MODEL_CACHE` | Optional direct override for the VoiceDesign model cache directory. |
| `VOXOVER_PORT` | Local server port; defaults to `8003`. |
| `VOXOVER_PYTHON` | Python executable to use with the Windows launcher. |

Nonempty `VOXOVER_*` environment variables take priority, followed by the earlier `CADENTVOX_*` names and then `VOICE_STUDIO_*`. Existing launchers remain supported. The internal `voice_studio/` folder and `qwen-tts` engine package name are retained for compatibility with existing environments, imports, output paths, and saved voices. No model or personal audio is moved by the rebrand.

### 3. Open the app

```sh
cd voice_studio
python -B app.py
```

Visit **http://127.0.0.1:8003**.

On Windows, run `voice_studio/Open-GUI.ps1` instead if you want the browser to open automatically. Set `VOXOVER_PYTHON` when using an existing environment. `Create-Shortcut.ps1` creates a local **Voxover** shortcut using the included icon. Both launch helpers stay separate from the original `qwen-tts-demo` entry point.

The model loads when generation begins. The app checks for at least 6 GB free GPU memory, but long text and references can require more. Closing a browser tab does not stop its server or unload a model held by another app.

## Files, privacy and responsible use

By default, audio and settings go to `voice_studio/Outputs/`, reusable prompts to `voice_studio/Voices/`, and temporary files to `voice_studio/Temp/`. The UI can change future output locations without moving existing files.

These runtime directories, personal voice prompts, recordings, generated audio, local settings and logs are excluded from Git. Model weights are not shipped in this repository. Review staged files before publishing, particularly if you choose a custom output directory outside the default ignored folders.

The server binds to localhost and public Gradio sharing is disabled. Saved voice prompts encode voice identity: only use trusted files and voices you have permission to use. Do not use voice cloning to deceive or impersonate someone without authorization.

## Verification

The original baseline checks include **44 Python tests**, JavaScript tab-transition regressions, **2,121 artwork-boundary geometry cases**, a real CUDA generation → re-clone → saved-prompt → generation round trip, and isolated Chrome rendering checks. The original theme was also checked from a clean checkout.

Most automated inference tests use a mocked model and a synthetic, non-personal voice fixture. These checks do not establish subjective voice quality or exhaustive microphone/trim/download behavior. See [original results and limits](voice_studio/VERIFICATION.md) and [rebrand verification](voice_studio/REBRAND-VERIFICATION.md).

```sh
cd voice_studio
python -B -m unittest discover -v
# Run every test_*.cjs script with Node.js (PowerShell):
Get-ChildItem test_*.cjs | ForEach-Object { node $_.FullName; if ($LASTEXITCODE) { throw "JavaScript test failed" } }
```

The Base model cache is needed for validation tests; Node.js is needed for JavaScript tests.

## Keeping up with Qwen

Our `main` contains Voxover. Add the official repository as `upstream` if needed, then integrate updates on a **separate branch**, resolve conflicts, run compatibility and real-generation checks, and only then merge into our `main`. There is no automatic synchronization.

See [the update and rollback workflow](voice_studio/UPDATING.md). UI compatibility depends on the tested Gradio version, and the experimental instruction path depends on private Qwen helpers.

## Credits and license

- **Qwen team / Alibaba Cloud:** Qwen3-TTS engine, models, research and original demo. The complete original README is preserved **unchanged** in [README.upstream.md](README.upstream.md), including model descriptions, examples, evaluation and citation information.
- **Voxover:** custom frontend, workflow, project-generated background and app icon. See [asset provenance](voice_studio/ASSET-PROVENANCE.md).
- **Sora and IBM Plex Sans:** bundled fonts under SIL Open Font License 1.1. Their copyright and license texts are included in [`voice_studio/assets/`](voice_studio/assets/).

Code is distributed under [Apache License 2.0](LICENSE). Keep upstream notices and the [third-party notices](voice_studio/THIRD_PARTY_NOTICES.md) when redistributing. Model downloads have their own model cards and applicable terms. This fork does not claim official Qwen affiliation or ownership of its technology.
