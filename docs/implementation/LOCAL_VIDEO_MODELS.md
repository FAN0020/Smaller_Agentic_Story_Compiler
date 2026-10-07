# Additional local video models

## Implementation

1. `video_models.py` defines the supported IDs, pinned revisions, installation directories, compact dimensions, frames, frame rates and provisional RAM budgets.
2. Settings validate local model IDs. The catalog and settings UI expose each model with its own installation and memory status.
3. Queued jobs freeze settings as before. Production forwards the selected model to `LocalGenerator.video`; no selected Wan model silently falls back to LTX.
4. `video_install.py` reads the pinned official file metadata, checks disk space with a 10 GiB reserve, downloads resumably and checks sizes/SHA-256 hashes. Identical weights can share disk space through hard links. A final READY marker means all weights were installed; it does not certify inference.
5. The existing monitored subprocess selects MPS, CUDA or CPU. Wan loads and runs its T5 encoder first, releases it, then loads the denoiser and VAE. On a unified-memory Mac, moving weights to CPU alone would not recover physical memory.
6. Wan TI2V receives the approved opening image. VACE receives that image as the opening video frame, a black opening mask and white masks for the remaining frames. Both receive the compiled shot prompt, retaining the frozen story setting and continuity constraints.
7. Clips enter the existing audio/timeline/FFmpeg assembly flow. Neither new path creates native audio. Prompts above 512 tokenizer tokens are rejected explicitly instead of silently truncated.

## Profiles and installation

| Model | Pinned revision | Fresh files | Compact preset | Available RAM admission |
|---|---|---|---|---|
| Wan 2.2 TI2V 5B | `b8fff7315c768468a5333511427288870b2e9635` | ~31.85 GiB | 97 frames, 24 fps, 512×288 | 19 GiB |
| Wan 2.1 VACE 1.3B | `ec4d2cb062b548996b179d493fdd05340de702a1` | ~17.73 GiB | 65 frames, 16 fps, 512×288 | 16.5 GiB |

Portrait swaps width and height. Both suggest 50 denoising steps. Disk admission adds 10 GiB to missing download bytes; approximately 10.6 GiB of identical text encoder weights can be shared between the two installations. No pre-existing checkpoints or user artifacts are deleted. The original LTX default remains available.

## Evidence and limits — October 7, 2026

Official model cards identify both checkpoints as Apache 2.0. The installed Diffusers interfaces support their image/video conditioning paths. Dependencies and application integration are present; **neither new checkpoint has yet been installed or rendered on this Mac**. At the last installation preflight only about 20 GiB of disk space was available, below either download requirement. Do not interpret model selection or a passing application build as successful model deployment.

The frontend production build and Ruff checks passed. The idle local studio was restarted with the new application code; `/api/health` reported `status: ok` and `worker_alive: true`. The actual Wan installer refused the download at 20.2 GiB free versus 41.85 GiB required. VACE preflight reported 27.73 GiB required. Model inference and visual quality remain unverified.

Wan 2.2 is a candidate for improved visual quality, not a measured improvement over LTX here. VACE is a smaller alternative, not a quality ranking. The reduced-resolution presets and provisional RAM estimates need real generation evidence. Native Wan 720p requirements for a dedicated CUDA GPU cannot be equated to 24 GiB of shared Apple memory. Runtime guards may reject or stop a render when headroom is insufficient.

## Primary references

- [Official Wan 2.2 TI2V 5B checkpoint](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers)
- [Official Wan 2.1 VACE 1.3B checkpoint](https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B-diffusers)
- [Diffusers Wan pipeline documentation](https://huggingface.co/docs/diffusers/api/pipelines/wan)
