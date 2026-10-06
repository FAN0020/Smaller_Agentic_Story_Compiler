# Verification evidence

Development run: October 6–7, 2026. Runtime: macOS, Apple M5 Pro, 24 GB RAM. Scope: a local single-user application. No hosted deployment or paid API execution was requested or performed.

## Deterministic verification

- Backend regression and integration suite: **58 passed**, including real FFmpeg assembly and frequency-based verification that narration preserves the original soundtrack.
- Ruff checks, diff whitespace checks, and TypeScript/Vite production build: passed.
- Clean Python environment installed from `uv.lock`: 58 tests passed, followed by a successful real server recovery check.
- Actual isolated Uvicorn process: startup, UI response, worker health, queued job execution, abrupt process termination, persisted source, interrupted-job recovery, explicit resume, and approval rejection passed (`scripts/verify_runtime.py`).
- Four-minute timeline assembly was exercised with real media: 60 four-second units, 5,760 video frames, duration within 0.35 seconds of 240 seconds. This tests assembly, not 60 independent model generations.
- All seven supplied stories, including the 748,131-character novel, round-trip through source chunking without missing characters. This is a preprocessing check, **not** a full novel model evaluation.
- API adapter contracts passed with an explicitly mocked HTTP transport: image generation/edit upload, four-second video submission, receipt persistence before polling, existing job retrieval without duplicate submission, ambiguous submission rejection, secret-safe errors, and the local reasoning flag.
- Plan revisions invalidate approval and reject invalid timing or cross-scene event reassignment. New production takes preserve previous receipts and reject resuming superseded jobs. Failed local generation cannot publish a partial file as a completed checkpoint.

## Browser verification

Real Chromium against the running backend, using the installed Playwright skill:

- Desktop 1440×1000 and mobile 390×844 layouts inspected; mobile has no horizontal overflow.
- Create, models dialog, Production, and Evaluate screens passed the executed axe WCAG 2 A/AA and 2.1 AA checks. This is not an accessibility certification.
- Actual text-file upload, sample selection, first-N/custom episode entry, project navigation, model selection, generated reference display, individual reference regeneration, reference approval, episode planning, plan revision, plan approval, new take, and video queueing exercised through the UI.
- The plan editor displays malformed-JSON errors without discarding the draft. A valid reviewer correction was saved through the UI and recorded in the project audit.
- Source form remains mounted during navigation. Stale project responses cannot replace the newly selected project.
- Local screenshots are under `output/playwright/` (excluded from Git).

## Real local model evidence

Pinned weights:

| Component | Checkpoint / configuration |
|---|---|
| Planner | Ollama `qwen3.5:9b`, Q4_K_M, digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`; 32,768 context; temperature 0.2; bounded repairs |
| Production images | `black-forest-labs/FLUX.2-klein-4B`, revision `e7b7dc27f91deacad38e78976d1f2b499d76a294`, bfloat16, 4 steps, native reference inputs |
| Reference studies | `stabilityai/sd-turbo`, revision `b261bac6fd2cf515557d5d0707481eafa0485ec2`, fp16 |
| Video | `Lightricks/LTX-Video-0.9.1`, revision `0dfb9a9b26f48256bbafc4e9fa337445ff76dc1c`, local bfloat16 conversion, 20 steps |
| Narration | macOS `say`, Samantha |

Development case: `01_lion_mouse`, children's mode, ages 6–9, watercolor, landscape, 60 seconds. Local project: `c363495d529a4644885716e754197863`. This is an internal evaluation project; its QA approvals are not approvals from the user.

The case exposed real failures: unstable copied quotes, omitted event IDs, reversed sleeping/capture roles, cross-scene event leakage, continuity resets, critic false positives **and false negatives**. One critic approved a misplaced plea in the opening. After contextual repair it caught that leak, and the director repaired the opening. A later scene still exhausted three attempts because the source extraction overlapped arrival/rescue events and the critic recommended violating the scene's fixed boundary states. Automated shot planning therefore **failed this case**. A reviewer-assisted correction, saved via the real plan editor, supplies the final 4 scenes, 15 shots and narration. This is not an autonomous planning success.

Code owns source passage copying, event partitioning, lineage IDs, duration arithmetic, and inheritance. Semantic reviews are advisory evidence; they do not establish source fidelity by themselves. Failed candidates and superseded plans remain in the project export.

Five SD-Turbo references were generated through the public UI queue and inspected; the mouse was regenerated once. SD-Turbo then failed production composition by preserving a reference-sheet collage. That take was stopped and archived. The application now uses FLUX.2 Klein's native multiple-image inputs for local composition and prevents SD-Turbo from being used for this operation. A real FLUX frame produced a coherent watercolor scene consistent with the reference design.

The FLUX/LTX take is **in progress** at this report checkpoint. Its first two completed clips are each four seconds with video and narration. Measured frame generation was about 50 seconds and motion generation 72–81 seconds per clip on this host. The render was cancelled and the application restarted; the two completed clips were reused with identical SHA-256 hashes and unchanged file timestamps. Full-episode playback and final artifact review remain pending until assembly finishes.

Mid-clip inspection already shows anatomy and scale drift in a mouse close-up, despite the improved opening frames. Visual approval remains unset. The local motion baseline is not accepted as professional-quality footage; the generated episode is an engineering evaluation artifact.

## Boundaries of the evidence

- Live paid API generation: **NOT VERIFIED** without credentials. Protocol tests do not prove account permissions or provider output quality.
- Protected model cases in `evaluations/cases.v1.json`: **NOT VERIFIED** unless a subsequent result explicitly names them.
- Full-novel semantic planning, multi-episode visual consistency, general drama output quality, all painting styles, other hardware/operating systems, and multi-user hosting: **NOT VERIFIED**.
- Local Foley/music synthesis is not implemented. Directing intent is preserved in the plan and provider prompt; available provider audio is mixed with narration. Local videos receive narration or silence.
- Text critics do not inspect generated video. Final viewing review remains a human decision. A technically valid file is not a professional-quality film.
- Model outputs are stochastic. Frozen seeds/configuration support traceability; they do not guarantee identical images across devices or software changes.
