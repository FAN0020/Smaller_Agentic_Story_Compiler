# V4 Professional Directing System — Canonical Contract

## 0. Authority and purpose
This file is the canonical implementation contract for professional Scene/Shot planning in Story Director V4. It operationalizes the broader `Professional_Film_Directing_Scene_Shot_Planning_Framework.docx`. The DOCX is an expanded checklist/reference; this Markdown file decides what the running system and future prompts must implement.

Do not solve this contract by stuffing every filmmaking term into one giant prompt. Professional decisions must be owned by the correct planning layer, represented structurally when they need validation/reuse, persisted when they affect continuity, and compiled down for providers.

## 1. Four information layers
Keep separate: **Story truth** (grounded facts/events), **Director intent** (audience understanding/feeling), **Film representation** (Scene/Shot choices and state transitions), and **Generator instruction** (provider-limited concrete instruction). Provider prompt text is never canonical story/directing state.

## 2. Canonical planning flow
`Story Truth → Global Director/Bibles → Episode Planner → Scene Director → Shot Director → Gate A Plan Verification → Capability/Feasibility → Provider Prompt Compiler → Generation → Episode Assembly/Evidence Sampling → Gate B Rendered Episode Verification → bounded repair/regeneration → Human Review when needed`.

Scene Director and Shot Director are distinct responsibilities. They may share infrastructure, but one opaque LLM response must not be the only representation of both.

## 3. Global/Bible responsibilities
- **Story Bible:** grounded source events/facts with stable evidence/IDs; adaptation choices separate.
- **Director Bible:** global pacing, dialogue density, visual/dramatic principles, fidelity, transitions, motifs where useful, age/safety and production assumptions.
- **Character Bible:** canonical identity, durable face/distinctive features, hair, body/silhouette where useful, canonical costume/accessories, acting tendencies, voice/reference lineage. Distinguish immutable identity from evolving state.
- **Location Bible:** identity, architecture, meaningful doors/windows, major furniture/prop anchors, materials/set-dressing cues, palette, motivated light sources, time variants and references. Prefer qualitative spatial relationships to fake precision.
- **Style Bible:** medium/texture/palette/lighting/composition and motion language; constrains but does not replace Scene/Shot decisions.

## 4. Scene Director contract
A Scene is a dramatic/cinematic unit. Scene Director decides what the scene must accomplish and how space/time works before individual coverage is chosen.

Required Scene semantics:
- purpose/function; dramatic objective and conflict/obstacle where relevant;
- source-event coverage and narrative beats;
- emotional start → progression → end;
- participating characters and relevant objectives;
- audience-information plan: known/new/hidden/reveal/setup/payoff when relevant;
- location, time and environment context;
- beginning/end continuity state;
- spatial basis: entrances/exits, important actor/prop positions, movement routes and action axis when relevant;
- scene-level lighting logic: motivated sources/direction/mood/time;
- active production design: foreground/midground/background needed for storytelling;
- atmosphere/environment behavior when relevant;
- dialogue/sound/music/silence intent when relevant;
- target duration and continuity requirements.

Scene Director should not micromanage lens millimeters or every eyebrow movement unless scene-defining.

## 5. Shot Director contract
A Shot is the actual coverage/generation unit. Shot Director converts Scene intent into visible/audible film representation.

### Always considered / normally explicit
- primary Shot purpose/role;
- narrative focus and relevant information change/concealment;
- primary subject and visual focus;
- Shot size/framing (ELS/LS/Full/MLS/MS/MCU/CU/ECU/Insert or equivalent);
- camera angle/position/movement at the level needed to generate the Shot;
- exact visible action;
- performance direction for visible characters;
- blocking needed for start/action/end continuity;
- duration/timing and start/end state handoff;
- continuity locks and allowed changes;
- relationship to adjacent coverage/edit where relevant.

### Conditional — populate only when useful
Lens/perspective; DOF/focus/rack focus; composition devices/negative space; detailed foreground/midground/background; micro-expression/action (fist tightening, brow furrowing, half-smile, swallow, gaze shift, tremble); breathing/posture; environmental motion (wind, curtain, rain, dust, smoke, fire, vegetation, reflections); special lighting; POV; insert/reveal/symbolic/foreshadow/payoff detail; Foley/music/silence; special transition/edit motivation; extras/background behavior.

Do not fill conditional fields merely to satisfy a checklist.

## 6. Shot-purpose vocabulary
Support a controlled primary role plus optional secondary role: `ESTABLISHING`, `GEOGRAPHY`, `CHARACTER_INTRODUCTION`, `CHARACTER_ENTRANCE`, `MASTER`, `ACTION`, `DIALOGUE`, `REACTION`, `POV`, `INSERT`, `DETAIL`, `REVEAL`, `EMOTIONAL_EMPHASIS`, `TRANSITION`, `MONTAGE`, `ATMOSPHERE`, `SYMBOLIC`, `FORESHADOWING`, `PAYOFF`, `EXIT`, `AFTERMATH`, `OTHER`. It supports validation/analysis without forcing formulaic coverage.

## 7. Structured cinematography
Where downstream behavior depends on it, represent separately rather than burying everything in `camera: string`: shot size; angle/height/position when relevant; lens/perspective when useful; composition; focus/DOF; camera movement/path; movement motivation. Human-readable summary prose may coexist as derived data.

## 8. Structured performance
Prefer observable behavior over labels such as “sad.” Support character objective/intent and emotion/intensity where useful, plus facial/micro-expression, gaze/eyeline, gesture/micro-action, posture/body tension, breathing and interaction. Example: “suppresses anger” may manifest as jaw tightening + fixed gaze + right hand slowly forming a fist.

## 9. Blocking and screen geography
Scene owns spatial basis; Shot applies it. Represent start/end positions and movement only to continuity-required precision. Track orientation, eyeline, screen direction/action axis and prop interaction when relevant. Do not invent exact coordinates unless useful.

## 10. Lighting, environment and production design
Scene establishes motivated lighting/environment logic. Shot applies visible details. Preserve source positions/directions across coverage unless the world changes. Track weather/time/atmosphere and story-relevant environmental state when persistent. Background is storytelling space: architecture, furniture, practicals, clutter, extras and cues should be intentional, not random decoration.

## 11. Continuity as state transition
Continuity is not merely prose reminders. Each Shot has `START STATE → ACTION → STATE DELTA → END STATE`.

Persist only continuity-relevant state, as applicable: costume/hair/makeup; wounds/dirt/blood/wetness/fatigue; held/carried story-relevant objects; character location/position/orientation; story-relevant prop owner/location/condition; door/window/furniture state; weather/time/atmosphere; active lighting; knowledge/reveal state when required. The next Shot starts compatibly with the prior end state unless a motivated temporal/spatial transition explains the difference.

Each Shot may state **immutable/locked** elements (canonical face, unchanged costume, wound location, room anchors, current prop hand, light source) and **allowed changes** (expression, gaze, hand tension, camera distance, action-caused object state).

## 12. Props and object identity
Create first-class Prop/ObjectState only for story/continuity-relevant objects. Track stable identity, owner/holder/location, condition/state and transitions. Do not create entities for meaningless background clutter.

## 13. Information and dramaturgy
Where important, track audience knowledge before, character knowledge, new information, deliberately hidden information, reveal timing, setup/payoff dependency and dramatic irony. Generator instructions receive visible manifestation, not abstract hidden reasoning unless needed for the frame.

## 14. Sound and editing
Shot planning may specify dialogue, ambience, Foley, music/silence and native-audio intent according to capabilities. Editing representation supports duration, adjacent-Shot relation, cut motivation and special transition only when useful. Assembly remains deterministic where possible.

## 15. Feasibility and semantic decomposition
Capability validation occurs after canonical directing. If duration/capability is infeasible, do not mechanically duplicate action or invent generic reaction coverage. Re-direct/decompose into meaningful sub-Shots with distinct purpose/action/performance, then revalidate. Deterministic splitting is allowed only when it provably preserves semantic and continuity intent.

## 16. Prompt compiler
Keep provider compilation deterministic and traceable. Under provider limits preserve, in priority order: visible subject/identity, exact action, critical performance/micro-action, framing/camera movement, current visible continuity state, location/environment, critical lighting, negative constraints/references. Translate abstract Director intent into visible/audible instruction. Provider-specific compacting needs tests proving retained/lost information; never silently truncate critical action/continuity.

## 17. Repair context
Shot repair receives enough context to avoid local damage: Scene intent/spatial basis, current Shot, relevant previous/next Shot, Character/Location Bibles, start/end continuity state, assigned source events, repair finding and provider constraints. Repair the smallest artifact but revalidate affected neighbors/state transitions.

## 18. Validation split
**Deterministic:** schema/IDs/lineage/source coverage; state transition compatibility; prop possession/location; required locks; capability/duration; prompt traceability; timeline arithmetic; credential absence; spatial/screen-direction checks where mechanically decidable.

**Semantic plan review:** source fidelity, Scene objective, coverage sufficiency, Shot purpose, visual focus, performance appropriateness, cinematography coherence, reveal timing, lighting/environment logic, reaction/edit logic and style/mode suitability.

**Rendered-media review:** separate evidence path for actual visual/audio continuity and prompt adherence. Without a media-aware validator, require human review and label status accordingly. Never treat text-plan review as proof of rendered continuity.

## 19. Migration compatibility
Existing V4 artifacts with free-text `camera`, `performance` and `continuity` remain readable. Add versioned structured fields/models and compatibility conversion rather than destructive migration. Preserve V3.1 frozen evidence. Old prose may remain as derived summaries during migration but must not be the sole canonical representation once structured contracts are active.

## 20. Prompt design rules for all future LLM prompts
Every planning prompt must:
1. state its ownership boundary and avoid unnecessary downstream decisions;
2. receive required context plus relevant continuity/Bibles;
3. distinguish source facts from adaptation/directing choices;
4. produce structured decisions for anything later validated/reused;
5. prefer observable/filmable behavior;
6. preserve IDs/lineage without machine IDs in user-facing/generator prose;
7. avoid filling irrelevant optional filmmaking fields;
8. preserve continuity start/end contracts;
9. avoid provider compromise before capability gate unless explicitly provider-constrained;
10. never claim media inspection without media evidence.

## 21. Required tests
Add controlled cases for Shot purpose; Scene→Shot intent propagation; shot-size/camera fields; micro-action; costume/prop/state transitions; room/spatial continuity; screen direction where applicable; lighting/environment continuity; reveal timing; meaningful duration decomposition; repair with neighbor context; prompt compiler retention/budget; persistence/resume/version migration; and no regression of source coverage/approval/resource/provider boundaries.

## 22. Implementation priority
**P0:** Scene Director/Shot Director responsibility split; structured ScenePlan/ShotPlan; purpose, cinematography, performance, blocking, start/end continuity; repair context; meaningful feasibility decomposition; compiler alignment.

**P1:** richer Character/Location structured Bibles; persistent Character/Environment/Prop state; deterministic transition validators; information/reveal/edit/sound fields where useful.

**P2:** rendered-media continuity/adherence review, provider reference/start/end-frame handoff where supported, and deeper directing-quality evaluation.

## 20. Rendered temporal coherence and action readability
Rendered review must verify more than prompt adherence. Check character identity/proportion/relative scale, style, location identity/geography/landmarks, prop identity/topology/state, contact plausibility, physical causality, emotional continuity, Shot-purpose fulfillment, reaction/reveal readability and intra-/inter-Shot continuity. A frame that contains the correct characters but does not visibly communicate the intended action (for example “releases,” “crosses paw,” “is trapped,” or “gnaws rope”) may fail `ACTION_READABILITY`.

For persistent/deformable objects, distinguish legal deformation from identity/topology mutation. State changes without an observable or explicitly motivated cause are continuity failures even when both endpoint images look individually plausible. Detailed automation belongs to `V4_AUTOMATED_VERIFICATION_SYSTEM.md`.
