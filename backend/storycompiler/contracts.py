"""Structured outputs shared by planners, critics, UI and generation adapters."""

from typing import Literal

from pydantic import Field

from .domain import Contract


class ExtractedEvent(Contract):
    summary: str
    quote: str = Field(description="Exact short substring copied from the source, not a paraphrase")
    characters: list[str]
    location: str


class ChunkAnalysis(Contract):
    summary: str
    events: list[ExtractedEvent] = Field(min_length=1)
    content_notes: list[str] = Field(default_factory=list)


class Character(Contract):
    id: str
    name: str
    source_facts: str
    appearance: str
    costume: str
    acting: str
    voice: str
    design_choices: str = Field(
        description="Appearance not specified by the source is labeled adaptation design"
    )


class Location(Contract):
    id: str
    name: str
    source_facts: str
    appearance: str
    geography: str
    lighting: str
    design_choices: str


class BibleDraft(Contract):
    title: str
    logline: str
    genre: str
    themes: list[str]
    characters: list[Character] = Field(min_length=1)
    locations: list[Location] = Field(min_length=1)
    directing_principles: list[str]
    adaptation_notes: list[str]
    content_warnings: list[str]
    visual_motifs: list[str]


class EmotionBeat(Contract):
    seconds: float = Field(ge=0)
    emotion: str
    intensity: int = Field(ge=0, le=10)
    cause: str


class OpenLoop(Contract):
    question: str
    setup_event_id: str
    payoff_event_id: str | None = None


class EpisodeOutline(Contract):
    number: int = Field(ge=1)
    title: str
    chapter: str
    summary: str
    source_event_ids: list[str] = Field(min_length=1)
    hook: str
    hook_latency: float = Field(ge=0)
    emotion_curve: list[EmotionBeat]
    reversal_beats: list[str]
    episode_boundary_hook: str
    audience_character_knowledge_gap: str
    open_loop_ledger: list[OpenLoop]
    setup_to_payoff_distance: str
    adaptation_notes: list[str] = Field(default_factory=list)


class EpisodeBatch(Contract):
    episodes: list[EpisodeOutline] = Field(min_length=1)


class ScenePlan(Contract):
    id: str
    episode_number: int
    bible_hash: str
    title: str
    purpose: str
    objective: str
    conflict: str
    source_event_ids: list[str]
    characters: list[str]
    location_id: str
    emotional_progression: str
    information_plan: str
    geography: str
    lighting: str
    environment: str
    sound_intent: str
    duration: int = Field(ge=4, le=240)
    start_state: dict[str, str]
    end_state: dict[str, str]
    transition_reason: str = ""


class SceneBatch(Contract):
    scenes: list[ScenePlan] = Field(min_length=1)


class Camera(Contract):
    size: Literal["ELS", "LS", "FULL", "MLS", "MS", "MCU", "CU", "ECU", "INSERT"]
    angle: str
    movement: str
    motivation: str
    lens: str = ""
    focus: str = ""
    composition: str = ""


class Performance(Contract):
    character_id: str
    intent: str
    behavior: str
    gaze: str = ""
    intensity: int = Field(default=4, ge=0, le=10)


class Sound(Contract):
    ambience: str = ""
    foley: str = ""
    music: str = ""
    dialogue: str = ""
    silence: bool = False


class ShotPlan(Contract):
    id: str
    scene_id: str
    bible_hash: str
    source_event_ids: list[str]
    purpose: Literal[
        "ESTABLISHING",
        "GEOGRAPHY",
        "CHARACTER_INTRODUCTION",
        "CHARACTER_ENTRANCE",
        "MASTER",
        "ACTION",
        "DIALOGUE",
        "REACTION",
        "POV",
        "INSERT",
        "DETAIL",
        "REVEAL",
        "EMOTIONAL_EMPHASIS",
        "TRANSITION",
        "MONTAGE",
        "ATMOSPHERE",
        "SYMBOLIC",
        "FORESHADOWING",
        "PAYOFF",
        "EXIT",
        "AFTERMATH",
        "OTHER",
    ]
    narrative_focus: str
    visual_focus: str
    characters: list[str]
    location_id: str
    action: str
    duration: int = Field(ge=1, le=240)
    camera: Camera
    performance: list[Performance]
    blocking: str
    start_state: dict[str, str]
    end_state: dict[str, str]
    state_reason: str
    transition_reason: str = ""
    locked: list[str]
    allowed_changes: list[str]
    sound: Sound
    narration: str = ""
    edit: str
    information_change: str = ""
    hidden_information: str = ""


class ShotBatch(Contract):
    shots: list[ShotPlan] = Field(min_length=1)


class CriticFinding(Contract):
    severity: Literal["error", "warning"]
    artifact_id: str
    category: Literal["fidelity", "continuity", "direction", "children", "pacing", "sound"]
    finding: str
    repair: str


class CriticReport(Contract):
    findings: list[CriticFinding]
    strengths: list[str]
    summary: str
