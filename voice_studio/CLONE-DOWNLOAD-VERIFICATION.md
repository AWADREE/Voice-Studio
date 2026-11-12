# Clone save and download verification — November 11, 2026

## Fixed
- Clone saving was hidden unless transcript correction was checked. Identity-only cloning could therefore leave no usable save action. The correction-only hide rule now applies only to Design, which has its own download control.
- Clone's existing save action stays visible and clickable while a replacement audition generates. Design's existing loading behavior is retained.
- Clone and Design release their local model reference before CUDA cache cleanup, matching the existing Generate/Save paths. This fixes repeat-generation failures caused by retained VRAM.

## Verified
- Read-only browser regression failed before the visibility fix and passed after it.
- Real Clone inference from a non-personal, generated reference on an isolated local QA server.
- Normal explicit Clone saving produced a valid 10.4 KB prompt and Neat Download Manager confirmed automatic download completion.
- During an 18.1-second identity-only replacement generation, the prior Clone Save remained visible and enabled. The queued save completed and Neat confirmed its automatic download. Its payload retained the prior original-reference transcript and ICL mode, rather than accidentally saving the new identity-only audition.
- The new identity-only audition was explicitly saved to a valid 5.8 KB prompt with x_vector_only_mode=true, icl_mode=false, and ref_text=null.
- Repeated real generation succeeds after release. Free VRAM returned to approximately 10.7 GB after the final take.
- Final verification: 237 Python tests, all 20 JavaScript suites, browser save-availability probe, and git diff --check passed.
- Normal servers on ports 8003 and 8013 restarted with the changes and returned HTTP 200.

## Limits
- Browser file upload itself was not tested: the Chrome extension does not have file-URL access. The QA server used Gradio's normal component-default handling to preload the generated reference; inference and subsequent Save interactions were real browser actions.
- The identity-only save is verified on disk and in the UI. Its separate automatic browser-download completion was not confirmed. Normal Clone and during-generation downloads were confirmed independently.
- No voice-quality or listening claim. No push, merge, or deployment.
