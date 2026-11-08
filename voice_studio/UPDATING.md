# Updating the fork safely

The official code stays at the repository root. Our independent UI is confined to voice_studio/. origin is the personal fork; upstream is QwenLM/Qwen3-TTS. There is no automatic synchronization.

1. Commit/stash local source changes and back up local voice/audio data outside Git. Do not add ignored personal files.
2. git fetch upstream
3. Create an update branch from our main and merge the desired upstream release/commit there. Inspect conflicts rather than blindly accepting either side.
4. Test in a separate environment/cache configuration and unused port. Do not upgrade the environment used by the running app until verification finishes.
5. Keep requirements.txt's Gradio baseline until the CSS/JS compatibility checks, upload/trim/playback, transcript toggles, tab transitions, storage controls, saved voice selection, generation, and downloads pass. Qwen private instruction helpers require explicit compatibility review.
6. Run all automated tests, then a consented real short clone and generation. Check instruction-free and instruction-supplied paths. Listen to the samples; audio differences alone do not establish quality.
7. Review git diff and the staged file list for personal data, logs, model files, machine paths, credentials, and unlicensed assets before push.
8. Merge the tested update branch into our main. Keep the previous working installation intact until verified. Roll back by returning to the previous commit/environment; never delete user audio or prompts.

Our main contains Voice Studio. Pristine official history is tracked by upstream/main; do not overwrite our main with it. Use an update branch for each upstream merge, resolve conflicts, test, then merge the proven result into our main. Use the separate Voice Studio launcher rather than replacing qwen-tts-demo.

