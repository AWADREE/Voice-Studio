# Voice Studio

Project: https://github.com/AWADREE/Voice-Studio

An independent, local-only Gradio frontend for Qwen3-TTS Base: reusable voice prompts, cloning with preview, optional experimental delivery instructions, generation controls, and audio/voice export. Upstream engine and original demo are unmodified.

## Install and start
Use Python 3.12 and a CUDA-capable PyTorch installation appropriate to your GPU. The verified local baseline was torch 2.11.0+cu128, qwen-tts 0.1.1, transformers 4.57.3, accelerate 1.12.0, gradio 6.17.3, numpy 2.5.4, soundfile 0.14.0. This is a compatibility baseline, not a guarantee for every platform.

From this folder:
```
python -m pip install -e ..
python -m pip install -r requirements.txt
python -B app.py
```
Open http://127.0.0.1:8003. Windows users can run Open-GUI.ps1. Set VOICE_STUDIO_PYTHON to an existing environment's python executable for that launcher.

Download the official Qwen/Qwen3-TTS-12Hz-1.7B-Base model separately following upstream instructions. This frontend intentionally uses local files only and never downloads weights on startup. Set HF_HOME to your existing Hugging Face cache, or VOICE_STUDIO_MODEL_CACHE to the model cache directory containing refs/main and snapshots/. VOICE_STUDIO_PORT selects another local port. No model loads until generation; CUDA and at least 6 GB free VRAM are checked, and default generation unloads afterward. This minimum is not a guarantee against OOM for long inputs.

## Storage and privacy
Outputs/, Voices/, and Temp/ are local runtime data, excluded from Git. Saved voice prompts can encode voice identity: never commit them, recordings, logs, or machine settings. Only use trusted voice prompts and voices you have rights to use. No public Gradio sharing is enabled.

## Important limitations
Base does not expose a supported plain-text instruction interface. This frontend passes instruct_ids via private helpers into the shared generation path. Instructions may not be followed; producing different audio is not proof of stylistic adherence. Save-as-new-voice re-encodes the generated preview; it does not fine-tune model weights.

## Theme
The public distribution includes an original procedural night/star backdrop. Unverified artwork and animation from the private project were deliberately excluded. Optional ignored local-night-sky.js plus assets/local-background.png can retain an existing installation's theme by setting VOICE_STUDIO_LOCAL_THEME=1; these files are not required or distributed. Sora and IBM Plex Sans font licenses are in assets/. The microphone app icon is a locally authored geometric design.

## Tests
With the Base model cached, run:
```
python -B -m unittest discover -v
node test_mode_transition.cjs
```
Tests use a synthetic speaker embedding and codec tokens, not a person's voice. Most inference tests use a mocked model. Real inference and browser interactions must additionally be checked before changing the live installation. See VERIFICATION.md and UPDATING.md.
