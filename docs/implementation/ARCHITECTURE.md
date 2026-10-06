# Story Compiler — implementation contract

The user's current request owns scope. Existing V4 documents are reference guidance; this implementation is new, with no V3 migration target. Where references say 3–5 minutes, the current requirement of **60–240 seconds** wins.

## Primary journey

Upload UTF-8 text (or a supplied sample) → choose general/children, age range, painting style and episode duration → select local/API models → analyze the complete source → inspect and freeze the series bible → plan the complete episode sequence → generate and approve character/location references → select first 1, first 5, custom episode numbers or all → direct scenes then shots → inspect and approve the production plan → render clips serially → assemble episode video → human viewing review.

The UI has Create, Director Plan, Production, Watch and Evaluate. Model settings are a dialog. Empty, busy, interrupted, failed and review-required states are visible and recoverable.

## Boundaries

Python/FastAPI owns validated domain contracts, SQLite state, a single durable job queue, provider adapters, deterministic prompt compilation and FFmpeg assembly. React/TypeScript owns presentation. The browser never calls model providers directly. Secrets are encrypted locally with a file-permission-protected key, excluded from project exports and logs. The service binds to loopback and validates browser origins.

Model work is explicit at four layers: grounded story evidence; director intent; cinematic scene/shot representation; provider execution instructions. Separate analysis, bible, episode, scene, shot and critic calls have narrow ownership. Long sources are chunked with stable source IDs and checkpointed analyses; no silent source truncation. Semantics come from the selected LLM, never from a purportedly intelligent keyword-template substitute.

## Inheritance and approval

Series bible content is hashed and frozen before episode division. Episodes inherit that hash. Scenes inherit episode identity and shared bible. Shots inherit scene geography, lighting, characters, locations, style and incoming continuity state. Generation adds an approved, content-hashed reference manifest. Every clip records inputs, provider/model, seed and prompt. Changing canon requires a new project revision; successful work is never silently overwritten. Reference rejection allows targeted regeneration before approval.

## Directing and gates

General direction searches the source for an immediate hook, emotion curve, supported reversals, episode-boundary hook, audience/character knowledge gap, open loops and setup/payoff distance. These are structured, inspectable decisions, not claims of professional quality. Children's direction uses age range, simpler action, recognizable subjects, moderate cuts, explicit cause/effect and a reassuring resolution when source-supported. Harmful source content requires adaptation disclosure and review.

Scene direction owns dramatic function, source-event coverage, emotional movement, spatial basis, light and sound. Shot direction owns purpose, filmable action, performance, framing/lens/movement/focus, blocking, start/end state, information reveal and sound/edit cues. Deterministic plan gates check IDs, coverage, lineage, duration, state handoff and capability. A semantic critic may request bounded repair. Repair exhaustion is review-required, not infinite retries.

Clips are individually generated and deterministically assembled, avoiding unsupported claims of arbitrary 1–4 minute single-call generation. Local diffusion is serial and lazily loaded in a separate process. A clearly labeled illustrated animatic option exists for fast editorial review; it is never represented as generated motion footage. Hosted generation requires explicit model selection, credentials and plan approval. No paid fallback.

Rendered verification checks technical validity, duration, streams and frame samples. Human review is required for visual identity, action readability and film quality unless a media-aware evaluator actually inspects the artifacts. Text-plan scores cannot approve rendered quality.

## Persistence and recovery

SQLite WAL stores projects and job states atomically. Artifacts live under project-scoped directories. One active job per project avoids conflicting writes. Heavy generation runs serially. Source analysis, reference images and completed clips are checkpointed. Restart marks unfinished jobs interrupted; explicit resume reuses checkpoints. Provider submission IDs are persisted before polling; ambiguous submission failures are surfaced rather than silently submitting paid work twice. Cancel stops between safe checkpoints and can terminate local inference.

## Proof required

Tests cover invalid inputs, source coverage, immutable inheritance, stale approvals, episode selection, duration arithmetic, continuity, prompt retention, encrypted secret exclusion, real persistence/restart, idempotent job submission and real FFmpeg output. Browser checks cover the primary flow and responsive layouts. Real local model evaluation and provider contract tests are reported separately. API integration remains NOT VERIFIED without user credentials; rendered artistic quality remains human review.

