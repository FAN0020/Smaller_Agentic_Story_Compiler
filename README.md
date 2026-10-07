# Story Compiler Studio

A local web studio that turns a text story into a shared visual world, directed episode plans, and **1–4 minute videos**. General drama and children's adaptations share a consistent series bible but use different directing policies.

## Run

Requires Python 3.12, Node.js 22+, [uv](https://docs.astral.sh/uv/), FFmpeg, and [Ollama](https://ollama.com/). On this development Mac the model checkpoints have already been installed in `.studio/models`.

```sh
./scripts/setup.sh
ollama pull qwen3.5:9b
.venv/bin/python scripts/setup_models.py all
./scripts/start.sh
```

Open **http://127.0.0.1:8787**. Choose `qwen3.5:9b` in **Models & settings** for a stronger local planner, or enter an API model and key. `qwen3.5:4b` is the lighter default; it may require more repair and review. The app listens only on the local machine. Run one server process for a workspace.

Model installation is separate from startup and resumable. FLUX.2 Klein image weights use about 16 GB; the LTX checkpoint is converted shard by shard to bfloat16 to save disk. Installation needs extra temporary space for one original video shard. Actual local generation was exercised on Apple M5 Pro / 24 GB RAM. Inference on other hardware is not yet verified. CPU-only production is likely impractically slow.

## Workflow

1. **Create:** upload UTF-8 `.txt`/`.md` (up to 2 MB), paste a story, or select a sample. Choose general/children, target age, visual style, 1–4 minutes, aspect ratio and adaptation policy.
2. **Director Plan:** inspect the source-grounded bible and its historical/cultural setting profile. Period, region, polity/dynasty, architecture, clothing and related details are labeled as explicit, inferred or unspecified with evidence and confidence. Use **Edit setting** to correct or discard guesses before freezing the shared visual canon. Low-confidence guesses are allowed. With no supporting evidence, use **NA**; it adds no setting constraint and generation continues normally.
3. **Production:** generate character/location references and approve them, freezing the visual canon **before episode division**. Plan the episode structure, then choose the first episode, first five, first N, specific episode numbers or all. Generate and inspect scene/shot plans. Use the plan editor to correct actions, camera, dialogue or sound; edits preserve history and require renewed approval. Approve selected plans before producing video. Every episode inherits the frozen canon and reference manifest; boundaries cover the full analyzed event sequence.
4. **Watch:** play/download complete episodes and review their visual storytelling. Technical validation never automatically approves artistic quality.
5. **Evaluate:** inspect source evidence, plan reviews, lineage and sampled video frames.

Jobs persist in SQLite. Cancellation stops at a safe checkpoint; completed clips remain. Failed/interrupted work can resume. Each job freezes model choices when queued; global settings changes do not change that job. **New take** archives the previous output and receipts, retains the approved plan, and permits a fresh render with different model settings. An ambiguous paid-video submission requires checking the provider account rather than silently submitting twice.

## Local and API models

| Stage | Local | API |
|---|---|---|
| Analysis, bibles, direction, critics | Ollama structured-output models | OpenAI or compatible Chat Completions endpoint |
| Visual references and shot frames | FLUX.2 Klein 4B, bfloat16, native multi-reference input | OpenAI Images generation/edits |
| Motion clips | LTX-Video 0.9.1; optional Wan 2.2 TI2V 5B and Wan VACE 1.3B | Sora video creation/status/content |
| Narration | macOS `say` | OpenAI speech |
| Assembly | FFmpeg | Always local |

Local models incur no per-call API charge; their licenses and hardware costs still apply. Hosted calls use your credentials and provider billing. Keys are encrypted with a local 0600 master key, stored outside project artifacts, and omitted from exports and logs. Back up `.studio/secret.key` with `.studio/secrets.enc` if moving your encrypted credentials. This protects accidental disclosure, not a compromised local user account.

SD-Turbo is also available for fast reference studies (`scripts/setup_models.py fast-image`). It cannot compose production scenes from multiple approved images. A real evaluation exposed collage artifacts, so the application requires a native multi-reference model for that stage. Existing approved SD-Turbo reference designs can be used by FLUX or the image API.

An **illustrated animatic** option creates an editorial preview using generated stills, camera motion and narration. It is clearly labeled and does not substitute for generated character motion. Local video has no native audio: narration can be synthesized; Foley/music remain plan instructions unless the chosen video model supplies them. Captions are exported separately.

The initial local motion profile uses short 4-second generation units, composed into 60–240 second timelines. Small local models can distort identity, anatomy or motion; references and seeds improve conditioning but do not guarantee consistency. Review the actual episode. OpenAI/Sora has additional content and human-reference restrictions; API paths are contract-tested but require your credentials for live verification.

## Architecture

`source → grounded events → frozen series bible → approved visual references → episode boundaries → scene intent → shot coverage → approved plan → provider compilation → clips → deterministic assembly → technical checks → human viewing review`

The agents own semantic decisions. Code owns IDs, source evidence copying, ordered coverage, hashes, approvals, arithmetic, capability checks, persistence, and side effects. Source text is data, not executable instructions. Canonical plans are separate from provider prompts. Continuity uses explicit start/end state, causal changes and immutable visual locks. General mode exposes hook latency, emotional progression, supported reversals, ending hooks, knowledge gaps, open loops and setup/payoff distance. Children's mode applies target-age adaptations and clearer cause/effect.

See [architecture](docs/implementation/ARCHITECTURE.md) and [verification evidence](docs/implementation/VERIFICATION.md). Supplied references are preserved in `docs/`; current user requirements override the older references' 3–5 minute targets.

## Development

```sh
uv sync --locked --extra dev --extra local
.venv/bin/pytest -q
.venv/bin/ruff check backend tests scripts
.venv/bin/python scripts/verify_runtime.py
npm --prefix web run build
# Optional hot-reloading UI against the API on port 8787:
npm --prefix web run dev
```

`STORY_STUDIO_HOME` chooses an independent data directory; `STORY_STUDIO_PORT` sets the launch-script port. Data, model weights, videos and keys are gitignored. Source uploads and generation outputs stay in that directory. API configuration intentionally sends relevant story context/media to the selected provider; the local path does not.

## Provider references

Implementation checked against official [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [FLUX.2 Klein model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), [SD-Turbo model card](https://huggingface.co/stabilityai/sd-turbo), [Diffusers LTX documentation](https://huggingface.co/docs/diffusers/api/pipelines/ltx_video), and [OpenAI video documentation](https://developers.openai.com/api/docs/guides/video-generation), accessed October 6–7, 2026. Provider availability, limits and account permissions can change.

### Compact local models and natural speech

On Apple Silicon, select **FLUX.2 Klein · 4-bit Apple Silicon** for character/location references and native multiple-reference scene images. Full-precision FLUX now requires at least 32 GB RAM. Install the compact image and neural voice runtimes with:

```sh
.venv/bin/python scripts/setup_models.py mlx-image
uv sync --extra dev --extra local --extra speech
.venv/bin/python scripts/setup_models.py speech
ollama pull qwen3:8b
```

Qwen3 8B is an additional planner option, not a proven quality ranking. Qwen3.5 4B/9B and installed Gemma models remain selectable. Larger models and longer contexts require more free memory; the studio checks capacity before loading them. Each Ollama request releases its model on completion. Image/video jobs stop safely if machine headroom becomes scarce. Close memory-heavy apps, use a smaller model/context, then resume; completed artifacts are preserved.

Choose **Kokoro neural voices** for free English narration and character dialogue. Pick a narrator and optionally cast each character in Model settings. On an existing directed plan, **Write narration & dialogue** creates a fresh soundtrack script and requires renewed plan approval. Then **Preview soundtrack** records and measures the voices before animation. Listen for pronunciation, pacing and character fit. A complete sentence can span several cuts within a scene; the application never truncates speech or automatically speeds it up. If a line is too long, edit its text or its ending shot and create a new take. Older takes keep their original audio.

Kokoro is CPU-based and supports voice and pace selection; arbitrary emotional acting and lip synchronization are not implemented. Its six exposed presets are English. See [the improvement evidence](docs/implementation/IMPROVEMENTS.md) for measured results and limitations.

### Additional local video models

**Models & settings → Episode production → Video model** also offers Wan 2.2 TI2V 5B and Wan VACE 1.3B. Both use Apache 2.0 weights with no generation API fee. Wan 2.2 is a newer quality candidate; VACE is a smaller image-guided alternative. Neither has been benchmarked against LTX on this Mac. Their inference paths are experimental until a real render is completed.

```sh
.venv/bin/python scripts/setup_models.py wan-video --dry-run
.venv/bin/python scripts/setup_models.py wan-video
.venv/bin/python scripts/setup_models.py vace-video --dry-run
.venv/bin/python scripts/setup_models.py vace-video
```

Keep approximately **50 GiB free before installing both**. Wan alone needs about 42 GiB free; VACE alone about 28 GiB. The installer reports exact requirements, reserves 10 GiB, resumes downloads, verifies weight hashes, and shares identical files between these models. It marks a checkpoint installed only after all files finish. The existing `all` installer retains its original baseline choices; these larger alternatives are opt-in.

The initial presets generate approximately four seconds at **512×288** (or portrait): Wan at 24 fps and VACE at 16 fps. These reduced resolutions conserve memory and do not represent the models' advertised native-resolution quality. Both consume the approved opening image and the compiled shot prompt, including the frozen story setting. VACE locks its opening frame with a conditioning mask. The worker releases the text encoder before loading the motion model, uses the available GPU backend, and retains memory/disk guards. Admission requires 19 GiB available RAM for Wan or 16.5 GiB for VACE, including system headroom. These are provisional budgets, not measured peak memory guarantees.

After installation, select and save the desired model. Already queued jobs keep their frozen model selection; use **New take** for an existing rendered episode. Installation is not proof of successful inference or improved artistic quality. See [video model implementation notes](docs/implementation/LOCAL_VIDEO_MODELS.md).
