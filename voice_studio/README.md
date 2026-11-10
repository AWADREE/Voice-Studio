# Voxover

Project: https://github.com/AWADREE/Voxover

An independent, local-only Gradio frontend for Qwen3-TTS Base and VoiceDesign: reusable voice prompts, cloning and prompt-based voice design with preview, optional experimental Base delivery instructions, generation controls, and audio/voice export. Upstream engine and original demo are unmodified.

## Install and start
Use Python 3.12 and a CUDA-capable PyTorch installation appropriate to your GPU. The verified local baseline was torch 2.11.0+cu128, qwen-tts 0.1.1, transformers 4.57.3, accelerate 1.12.0, gradio 6.17.3, numpy 2.5.4, soundfile 0.14.0. This is a compatibility baseline, not a guarantee for every platform.

From this folder:
```
python -m pip install -e ..
python -m pip install -r requirements.txt
python -B app.py
```
Open http://127.0.0.1:8003. Windows users can run Open-GUI.ps1. Run Create-Shortcut.ps1 to create a local Voxover shortcut with the included multi-resolution icon. This creates no Start menu entry. Set VOXOVER_PYTHON to an existing environment's python executable for that launcher.

Download the official Qwen/Qwen3-TTS-12Hz-1.7B-Base and Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign models separately following upstream instructions. This frontend uses local files only and never downloads weights on startup. Set HF_HOME to your existing Hugging Face cache, VOXOVER_MODEL_CACHE to the Base model cache directory, or VOXOVER_DESIGN_MODEL_CACHE to the VoiceDesign model cache directory. Each cache directory must contain refs/main and snapshots/. VOXOVER_PORT selects another local port. No model loads until generation or voice saving; CUDA and at least 6 GB free VRAM are checked, and default generation unloads afterward. Loading a different checkpoint for an operation unloads the previous model first. This minimum is not a guarantee against OOM for long inputs.

### Existing installations

Legacy `CADENTVOX_*` and `VOICE_STUDIO_*` environment variables still work. Nonempty settings are resolved in this order: `VOXOVER_*`, `CADENTVOX_*`, then `VOICE_STUDIO_*`. The `voice_studio/` folder and upstream `qwen-tts` package name stay unchanged so existing environments and storage locations continue to work. The application and repository are now named **Voxover**.

## Storage and privacy
Outputs/, Voices/, and Temp/ are local runtime data, excluded from Git. Saved voice prompts can encode voice identity: never commit them, recordings, logs, or machine settings. Only use trusted voice prompts and voices you have rights to use. No public Gradio sharing is enabled.

## Important limitations
Base does not expose a supported plain-text instruction interface. Its optional delivery field passes instruct_ids via private helpers into the shared generation path. Instructions may not be followed; producing different audio is not proof of stylistic adherence. The Design tab uses the official VoiceDesign API and its own checkpoint. Save-as-new-voice re-encodes the generated preview with Base after you listen and confirm or correct the transcript; it does not fine-tune model weights or guarantee that later takes keep the same delivery.

See [VOICE-DESIGN-PARITY.md](VOICE-DESIGN-PARITY.md) for the reference GUI field audit and workflow details.

## Shared commentary workflow

Choose Clone, Design, or Generate at the top. Clone and Design create a single audition without saving a `.pt` automatically. Listen, confirm or correct the transcript, and save an approved audition as a reusable voice prompt. Generate uses an existing `.pt` for single commentary or multiple timestamped clips. The shared script, language and settings remain intact while switching modes. Multiple clips support per-clip seeds, regeneration, timing alignment, playback and combined export. Timestamp labels identify clips; they are not forced silence durations.

## Theme
The public distribution includes our generated night-sky artwork and matching animated stars, authorized by the project owner for publication. Asset URLs resolve from the checkout, so no private local overrides are required. Sora and IBM Plex Sans font licenses are in assets/. The microphone app icon is a locally authored geometric design. See ASSET-PROVENANCE.md.


## Tests
With the Base model cached, run:
```
python -B -m unittest discover -v
Get-ChildItem test_*.cjs | ForEach-Object { node $_.FullName; if ($LASTEXITCODE) { throw "JavaScript test failed" } }
```
Tests use a synthetic speaker embedding and codec tokens, not a person's voice. Most inference tests use a mocked model. Real inference and browser interactions must additionally be checked before changing the live installation. See VERIFICATION.md and UPDATING.md.

## Sample-first Clone and Design

Clone and Design generate one audition from the shared Commentary text and generation settings. Neither automatically saves a .pt. Listen, confirm (and correct the reference/sample transcript if needed), then use Save audition as voice .pt. Clone preserves the original reference prompt; Design encodes its generated sample using Base. Load that .pt in Generate for single commentary or Multiple clips. Timed drafts remain intact while visiting Clone/Design.
