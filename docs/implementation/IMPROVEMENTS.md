# Production improvements — 7 October 2026

## Acceptance requirements

1. More usable free models, with honest capability and installation status; deploy and exercise the selected local additions.
2. Natural neural voices, separate narration and character speech, and audio timing planned before animation. Speech must never be silently cut or squeezed into four-second sentences.
3. Investigate the reference-generation restart; prevent unsafe local model loading, retain work after interruption, and verify recovery without intentionally reproducing an OS crash.
4. Remove repeated page labels and other redundant interface elements; inspect desktop and mobile rendered views.

## Restart evidence

The user's Aladdin reference job started at 01:50:08 on 7 October. Qwen3.5 9B analysis finished at 01:49:52; the old adapter kept it resident for three minutes. The FLUX log ends immediately after all components loaded, before any denoising progress. macOS rebooted at 01:52:36.

The corresponding OS panic reports a watchdog timeout (no check-ins for 91 seconds), 16 swapfiles and **LOW swap space**. This establishes an OS-level stall and scarce swap; it does not prove a sole Python or GPU-driver cause. Unquantized FLUX loading alongside the retained LLM is a plausible, preventable contributor. Previous successful runs are not evidence that this concurrent workload is safe.

## Resource controls

Local image/video admission reserves 3 GiB beyond an estimated working set and requires 10 GiB free disk. Full-precision FLUX is refused below 32 GB physical memory. A process monitor stops generation when available RAM drops below 2 GiB, disk below 8 GiB, swap growth exceeds 2 GiB, or worker RSS exceeds its budget. PyTorch MPS receives an explicit allocator cap. A shared OS-backed lease serializes Studio local inference across processes; Ollama requests now unload immediately on completion. No unrelated app or model is forcibly stopped.

These are conservative protections, not a guarantee against operating-system faults. Interrupted jobs require explicit resume. Successfully published artifacts remain intact; partial files never become completed checkpoints.

## Evidence ledger

Resource admission, recovery, model installation, soundtracks and the rendered UI were exercised on this 24 GB Apple Silicon machine. Detailed results and limits are below; a passing software check does not establish automatic artistic quality.

## Local model additions and verified sources

- Apple Silicon image generation: `mlx-community/flux2-klein-4b-4bit`, pinned to `860e87183ceb29e39627c0612ebd66d8ea66e68c`, through isolated MFLUX 0.21.0. It supports the same native multiple-reference conditioning while avoiding the full-precision checkpoint's memory footprint. Real 512×512 reference smoke: peak MLX allocation 5.37 GiB. This is an observed sample, not a universal maximum.
- Neural English speech: Kokoro ONNX 0.6.1 / model-files-v1.1, CPU-only, two inference threads, six selectable English voices. Weight and voice files are SHA256-verified by the installer. Real 27-word narration sample: 8.20 seconds. No time compression is applied.
- Alternative local planner: Qwen3 8B Q4_K_M installed through Ollama. One real structured audio rewrite completed in 149.5 seconds with a 32K context; it copied legacy captions and was rejected for narrative/voice quality. It is an available alternative, **not a demonstrated quality upgrade** over Qwen3.5. Installed 1.5B, 4B and 9B alternatives remain available. Context size is explicit and resource admission uses model size plus headroom.

Sources checked on 7 October 2026: [MFLUX implementation and multiple-reference API](https://github.com/mflux-community/mflux/blob/main/src/mflux/models/flux2/README.md), [quantized checkpoint](https://huggingface.co/mlx-community/flux2-klein-4b-4bit), [Kokoro ONNX runtime](https://github.com/thewh1teagle/kokoro-onnx), [upstream voice model](https://huggingface.co/hexgrad/Kokoro-82M), [Ollama Qwen3 8B](https://ollama.com/library/qwen3:8b), [PyTorch memory limits](https://docs.pytorch.org/docs/stable/generated/torch.mps.set_per_process_memory_fraction.html).

## Audio-first production contract

The audio director receives source-grounded events and shot timing windows, without obsolete per-shot narration that can bias it toward mechanical captions. A cue declares narration/dialogue, a narrator or canonical character ID, a complete sentence, delivery intent, pace and the last shot it may span. Speech may bridge cuts inside one scene. At least one narration cue is required when speech is selected.

Production records each cue before generating any new visual material, measures its duration and verifies its allocated window. An oversized line stops the job with a concrete edit instruction. The application never truncates speech or automatically accelerates it. Recordings have checksums and are reused after interruption; a changed plan/cast requires a new take. A full-length soundtrack preserves pauses, and captions use actual measured start/end times. The final mux retains subdued original scene audio beneath speech.

The UI allows a soundtrack-only preview after plan approval and before animation. It also exposes a separate “Write narration & dialogue” action for existing plans and per-character casting. The narrator and character defaults differ and remain stable across episodes of the same bible. Kokoro supports voice selection and pace, not arbitrary emotion instructions; expressive acting and lip synchronization are not claimed. API speech receives delivery instructions. Older takes containing per-clip voices require a new take for this workflow, preventing doubled speech.

## UI necessity decisions

Keep the top bar's current page label for orientation and the story title as the primary content heading. Remove the repeated page eyebrow labels, the second global model-settings entry point, the redundant new-story plus button, the fake user avatar, repeated privacy badge, and decorative footer. Preserve source review, approvals, recovery controls, provider status and artifact access. The new soundtrack preview and cast controls support decisions the user could not previously make.

## Current verification results

- **Reference recovery PASS:** the original Aladdin project `94c867db32994449b0a136d1c4570626` now has all 13 quantized references. Job `509dfd71103f42ea8ce457605b1114b1` resumed after a safe capacity rejection, reused its saved first reference and completed the batch. All references remain unapproved for user review. The older pre-panic job is retained as interrupted.
- **Runtime protection PASS:** a test launches a real disposable subprocess, injects low-headroom telemetry at the system boundary, and verifies termination without publishing an output. Resource tests also exercise cross-process lease exclusion and rejection of full-precision FLUX on 24 GB. Actual low-headroom requests were rejected without a reboot.
- **Speech preview PASS (reviewer-authored script):** job `088d4becbf9e4271ad1c26727b16136f` recorded 9 utterances and mixed a 60-second track. Seven narration cues use Heart; Mouse uses Bella and Lion uses George. Cue lengths measured 1.956–6.911 seconds, with sentences spanning multiple video cuts. No fitting-time acceleration or truncation. The internal voice evaluation project is `3e6a5e33d75a4527b99a7def131e1325`.
- **Automatic audio writing FAIL / held for review:** real Qwen3 8B, Qwen3.5 4B and Gemma3 4B attempts showed caption copying, speaker-ID mistakes or overly wordy/overlapping cues. Attempts and repair feedback are retained. Scene-scoped schema enums now constrain valid IDs, but these tests do not establish autonomous writing quality. The successful preview used a disclosed reviewer-authored script through the same plan editor/approval/production APIs. A stronger selected planner or manual script review is still needed.
- **Automated regressions PASS:** 72 tests cover the previous pipeline plus headroom, process termination, audio schema constraints, cross-cut timing, speaker/narration validation, actual FFmpeg mixing, checkpoint reuse and ensuring failed speech timing precedes visual calls.
- **Completed soundtrack integration PASS:** render job `44d43d467b9543a2811867d463e56793` produced `take-74a6eea5-episode-1.mp4` in the internal voice evaluation project. All nine speech recordings retained their SHA256 and modification time after a server restart and full production. The final 768×432 movie decodes completely with FFmpeg; browser playback reports 60.032 seconds, an audio track and timed captions. This test reused 15 previously generated silent video clips and a reviewed script. It establishes soundtrack timing, persistence and final assembly, not a new motion-model quality result.
- **Runtime restart PASS:** `scripts/verify_runtime.py` starts a real isolated server and worker, kills it during an HTTP provider request, restarts it and checks persisted source, interrupted job status, no automatic retry, explicit resume and production approval gates. Its provider is a deliberately slow local mock, not a live model. The harness now implements model inspection and consumes request bodies before replying, matching the updated adapter contract.
- **Clean installation PASS:** `UV_PROJECT_ENVIRONMENT=output/verify-venv uv sync --frozen --extra dev` followed by all 72 tests passed without optional model runtimes. Ruff, frontend TypeScript/Vite build, Prettier and `git diff --check` passed. Installed optional runtimes were exercised separately as described above.
- **Rendered UI PASS:** desktop 1440×1000 and mobile 390×844 views were inspected. Production, model settings and Watch had no automated accessibility violations or horizontal overflow after labeling the two Watch-page landmarks. Keyboard Escape closes model settings. The global settings entry point appears once; repeated page eyebrows are gone. Completed soundtracks expose an audio player without a duplicate preview action, and completed episodes offer Watch as the primary action. Browser audio and video playback advance without media errors.

Measured speech intervals are also passed into each clip's motion prompt (speaker, local start/end, delivery), while later plot text is excluded to avoid leaking a sentence's payoff into an earlier shot. This is voice-over direction, not forced lip synchronization.

## Evidence locations and remaining limits

Local, ignored evidence is under `output/evaluation/improvements/`: `runtime-recovery.json`, `clean-install.log`, `clean-tests.log`, `soundtrack-manifest.json`, `speech-checkpoints.json`, `failed-auto-audio.json`, and the reviewed audio plan. Rendered screenshots are under `output/playwright/improvements-*`. The final evaluation movie is `.studio/artifacts/3e6a5e33d75a4527b99a7def131e1325/take-74a6eea5-episode-1.mp4`. The Aladdin references remain available in the original project for user approval.

A native two-reference MLX edit smoke was rejected before loading because available memory was below the admission threshold. Its live multi-reference output is therefore not verified in this run. Quantized single-image generation and the complete 13-reference batch were verified. Paid API adapters were not exercised because no API credentials were supplied. No new video model was deployed, and existing local visual quality limitations remain. The original Qwen3.5 9B planner selection was restored after comparative testing; the smaller installed alternatives remain selectable when resource admission rejects the larger model. Quantized images and Kokoro are selected for the new local production path.
