# Story Compiler — implementation contract

The user's current request owns scope. Existing V4 documents are reference guidance; this implementation is new, with no V3 migration target. Where references say 3–5 minutes, the current requirement of **60–240 seconds** wins.

## Primary journey

Upload UTF-8 text (or a supplied sample) → choose general/children, age range, painting style and episode duration → select local/API models → analyze the complete source → inspect and freeze the series bible → generate and approve character/location references → plan the complete episode sequence → select first 1, first 5, custom episode numbers or all → direct scenes then shots → write scene-scoped narration and dialogue → inspect and approve the production plan → preview the measured soundtrack → render clips serially → assemble episode video → human viewing review.

The UI has Create, Director Plan, Production, Watch and Evaluate. Model settings are a dialog. Empty, busy, interrupted, failed and review-required states are visible and recoverable.

## Boundaries

Python/FastAPI owns validated domain contracts, SQLite state, a single durable job queue, provider adapters, deterministic prompt compilation and FFmpeg assembly. React/TypeScript owns presentation. The browser never calls model providers directly. Secrets are encrypted locally with a file-permission-protected key, excluded from project exports and logs. The service binds to loopback and validates browser origins.

Model work is explicit at four layers: grounded story evidence; director intent; cinematic scene/shot representation; provider execution instructions. Separate analysis, bible, episode, scene, shot and critic calls have narrow ownership. Long sources are chunked with stable source IDs and checkpointed analyses; no silent source truncation. Semantics come from the selected LLM, never from a purportedly intelligent keyword-template substitute.

## Inheritance and approval

Series bible content and the approved character/location image manifest are hashed and frozen before episode division. The bible includes a shared historical and cultural setting profile (period, country/region, polity/dynasty, architecture, clothing, material culture, language and climate). Each setting detail records whether the source states it, the model cautiously infers it, or it is unspecified, along with evidence and confidence. Low-confidence guesses are valid and editable through the setting form before bible approval. User edits are labeled user_defined; NA (including legacy Unspecified values) adds no generation constraint and never blocks production. Unsaved setting edits disable the freeze action. Scenes and shots inherit this profile; compiled image and motion prompts include its visual guidance and guardrails. Episodes inherit both hashes. Scenes inherit episode identity and shared bible. Shots inherit scene geography, lighting, characters, locations, style and incoming continuity state. Generation adds an approved, content-hashed reference manifest. Every clip records inputs, provider/model, seed and prompt. Changing canon requires a new project revision; successful work is never silently overwritten. Reference rejection allows targeted regeneration before approval.

## Directing and gates

General direction searches the source for an immediate hook, emotion curve, supported reversals, episode-boundary hook, audience/character knowledge gap, open loops and setup/payoff distance. These are structured, inspectable decisions, not claims of professional quality. Children's direction uses age range, simpler action, recognizable subjects, moderate cuts, explicit cause/effect and a reassuring resolution when source-supported. Harmful source content requires adaptation disclosure and review.

Scene direction owns dramatic function, source-event coverage, emotional movement, spatial basis, light and sound. Shot direction owns purpose, filmable action, performance, framing/lens/movement/focus, blocking, start/end state, information reveal and sound/edit cues. Deterministic plan gates check IDs, coverage, lineage, duration, state handoff and capability. A semantic critic may request bounded repair. Repair exhaustion is review-required, not infinite retries.

Clips are individually generated and deterministically assembled, avoiding unsupported claims of arbitrary 1–4 minute single-call generation. Local diffusion is serial and lazily loaded in a separate process. A clearly labeled illustrated animatic option exists for fast editorial review; it is never represented as generated motion footage. Hosted generation requires explicit model selection, credentials and plan approval. No paid fallback.

Rendered verification checks technical validity, duration, streams and frame samples. Human review is required for visual identity, action readability and film quality unless a media-aware evaluator actually inspects the artifacts. Text-plan scores cannot approve rendered quality.

## Persistence and recovery

SQLite WAL stores projects and job states atomically. Artifacts live under project-scoped directories. One active job per project avoids conflicting writes. Heavy generation runs serially. Source analysis, reference images and completed clips are checkpointed. Restart marks unfinished jobs interrupted; explicit resume reuses checkpoints. Provider submission IDs are persisted before polling; ambiguous submission failures are surfaced rather than silently submitting paid work twice. Cancel stops between safe checkpoints and can terminate local inference.

## Proof required

Tests cover invalid inputs, source coverage, immutable inheritance, stale approvals, episode selection, duration arithmetic, continuity, prompt retention, encrypted secret exclusion, real persistence/restart, idempotent job submission and real FFmpeg output. Browser checks cover the primary flow and responsive layouts. Real local model evaluation and provider contract tests are reported separately. API integration remains NOT VERIFIED without user credentials; rendered artistic quality remains human review.

## Director decisions and ownership

| Concern | LLM / director decision | Application enforcement | Final viewing check |
|---|---|---|---|
| Hook latency | Source-supported opening and planned latency | Mode-specific maximum in outline; critic compares plan to source | Does the opening actually establish curiosity? |
| Emotion curve | Time, emotion, intensity and cause | Timestamps must fit the episode | Are performance, framing and sound legible? |
| Reversal beats | Earned reversals already supported by the story | Fidelity critic; empty reversals are valid | Does the change read without confusion? |
| Episode boundary hook | Carry unresolved stakes, or resolve the final installment | Complete ordered source coverage; final source context supplied | Does the ending invite continuation or feel complete? |
| Knowledge gap | What the audience and characters each know | Shot fields separate visible and hidden information; critic review | Does the image accidentally disclose a secret? |
| Open loops / payoff distance | Event-linked setups, payoffs and distance rationale | Only real source-event references; coverage and chronology checks | Is the payoff understandable and satisfying? |
| Camera language | Shot size, angle, lens, movement, focus, composition and motivation | Typed shot purpose/camera contracts; scene geography inherited into prompts | Screen direction, staging, continuity and useful emphasis |
| Performance / sound | Observable behavior, gaze, intensity, dialogue, silence, ambience and Foley intent | Character identity validation; narration fit and audio mixing | Anatomy, acting, speech clarity, emotional effect |

The director's plan is the editable specification before approval. The interface exposes JSON editors for the bible and complete scene/shot plans. Plan corrections preserve prior revisions, validate timing, scene scope and inheritance, invalidate approval, and add an audit entry. Critics' semantic errors require explicit acceptance. Frozen canon changes use a new project revision. A graphical timeline editor is outside the current interface.

Image details offer a visual revision after episode planning locks the references. The revision copies the source analysis, frozen bible and reference image files, clears reference approvals, and queues the selected image prompt with current model settings. Project creation and job insertion share one transaction after artifact copying; failures discard the partial copy. Episode outlines, plans, productions and reviews stay in the original project. The revised look must be approved and episodes planned again. Ordinary reference regeneration remains available before episode planning.

## Execution choice

The first production profile deliberately uses four-second motion units. Models do not universally support a one-call 1–4 minute episode, and a single call cannot provide clip-level retries or checkpoint reuse. Scene and shot agents allocate meaningful coverage; code assigns exact duration and lineage. FFmpeg assembles the clips into the selected 60, 120, 180 or 240 second target. Provider adapters own native duration/resolution constraints, credentials, submission receipts and errors. No model can bypass reference/plan approval by writing a different status string.

```mermaid
flowchart LR
  S[Story + brief] --> A[Grounded analysis]
  A --> B[Review and freeze bible]
  B --> R[Generate and approve shared references]
  R --> E[Episode boundaries]
  E --> D[Scene direction]
  D --> H[Shot coverage]
  H --> C[Hard gates + source critic]
  C --> P[User plan approval]
  P --> T[Record speech + validate actual timing]
  T --> G[Image and motion adapters]
  G --> F[FFmpeg assembly]
  F --> V[Technical checks + viewing review]
  C -->|bounded repair| D
```


## Local resource admission and audio production

See [IMPROVEMENTS.md](IMPROVEMENTS.md) for the October 2026 incident and verification. A machine-wide Studio inference lease prevents its local image/video/speech/planner work from overlapping. Admission accounts for free RAM and disk, with bounded waiting for recently unloaded weights. MPS/MLX allocations are capped and the diffusion worker is monitored for memory, disk and swap growth. Local Ollama contexts are explicit; models unload after every request. This limits preventable exhaustion and does not purport to fix macOS kernel defects.

Audio has its own structured scene-scoped director and source critic. Narration and character cues inherit canonical speaker IDs and may span consecutive shots within one scene. Code rejects overlap, missing narration, invalid speakers, scene crossings and unreasonably wordy windows. Production synthesizes and measures all cues before any new frame or motion call. Utterances are never automatically accelerated or cut. The mixed episode soundtrack and VTT use measured timing; TTS recordings are separately checkpointed with hashes and a stable voice cast. Soundtrack-only preview is an explicit job. Source/plan changes require renewed approval and a new take when recordings or clips must be preserved.
