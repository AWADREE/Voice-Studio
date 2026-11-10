# Voxover rebrand verification

2026-11-10, `feature/multiple-clip-combine`. Source changes remain local and uncommitted; no push.

## Identity and scope

- Chosen name: **Voxover**, a play on "voiceover." Tagline: "Find your voice. Shape every line. Create commentary locally."
- Confirmed `AWADREE/Voxover` did not exist in the authenticated account before renaming `AWADREE/CadentVox` to **[AWADREE/Voxover](https://github.com/AWADREE/Voxover)**. Verified the unchanged repository ID, `1450104771`, and updated its About description. Ownership, public visibility and default branch are unchanged. This repository collision check is not a global name or trademark clearance.
- Updated the shared local Git origin to the new URL. Upstream remains `QwenLM/Qwen3-TTS`. GitHub ordinarily redirects previous repository URLs; do not reuse the former repository names if those redirects are needed.
- Updated the visible header, browser title, startup-splash styling, app messages, documentation, project URLs, shortcut/icon names, JavaScript namespaces and events to Voxover.
- Nonempty environment settings resolve in this order: `VOXOVER_*`, `CADENTVOX_*`, then `VOICE_STUDIO_*`. The internal `voice_studio/` directory and `qwen-tts` package identity remain unchanged for existing imports, environments and saved-data locations.
- Preserved the existing geometric microphone and night-sky artwork bytes. This changes the name, not the visual theme.
- Created the local `Voxover.lnk` and `local-Voxover.ps1` launcher for port 8013. The previous local shortcut and launcher path remain usable as compatibility entries and point to Voxover.
- Kept the branch, HEAD and staging tree unchanged. No commits, pushes, merges or model/dependency installations were performed.

## Automated checks

- Updated branding tests first failed against the old title, splash, icon names and settings precedence. A separate launcher behavior test also failed for the missing `VOXOVER_*` precedence before implementation. All five branding tests then passed.
- Full Python unittest discovery: **214 tests passed**.
- Every `test_*.cjs` script: **18 files passed**, including the existing artwork, generation, clip, playback and randomization regressions.
- Both public PowerShell launch helpers and both local launcher paths parsed successfully. Project TOML metadata parsed successfully. `git diff --check` passed.
- Independent review compared the pre-task file snapshot against current bytes: no actionable rebrand defect found. The 37 changed existing files at review time consisted of brand substitutions, compatible settings fallbacks, tests/docs and the local-launcher wrapper.
- Independent settings checks passed **81 Python combinations** and **27 PowerShell combinations**, covering missing and empty values, prefix precedence and browser destination.
- Independent comparison confirmed unchanged upstream engine files, examples, finetuning code, upstream assets, workflows, license, original README, manifest, ignore rules and all non-renamed bundled assets. Both renamed icon files are byte-identical to their predecessors.

## Running installation

- Restarted only the verified worktree app on **http://127.0.0.1:8013/**. The separate port-8003 app retained its original process.
- Fresh HTTP checks verified the Voxover title and header from the live Gradio config and a successful favicon response (40,646 bytes).
- Live Chrome checks verified the heading and browser title and no visible prior app names. Clone and Generate screenshots were captured and inspected: desktop layout was clean, aligned and unclipped.
- Repeated Clone/Design/Generate and Single/Multiple transitions passed. Randomize correctly disabled the shared seed and exposed per-clip seeds; turning it off restored the shared seed.
- No visible app errors or app-origin console errors occurred. Only unrelated browser-extension warnings appeared.
- The startup splash passed too quickly to observe in this browser pass. Its new branding is covered by automated styling checks, not a fresh visible-splash assertion. The favicon was checked by HTTP, not independently in browser chrome. No new narrow-layout pass is claimed.

## Limits

- Existing missing-SoX, missing-flash-attn, Gradio deprecation and unittest event-loop warnings remain. They did not fail the checks.
- No real GPU inference was needed for the name change. Automated inference tests use mocks and synthetic prompts; no personal voices or generated audio were published.
- Existing generated files and storage paths were not moved. The snapshot review did not include private runtime audio/model directories.
- The repository name and About are live on GitHub. README and code changes remain local until explicitly committed and pushed with the other pending feature work.
