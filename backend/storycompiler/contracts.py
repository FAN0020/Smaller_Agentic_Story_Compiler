"""Structured outputs shared by planners, critics, UI and generation adapters."""

from typing import Literal

from pydantic import Field, create_model, model_validator

from .domain import Contract


class ExtractedEvent(Contract):
    summary: str
    source_span_id: str = Field(
        default="", description="ID of the supplied original source passage supporting this event"
    )
    quote: str = Field(
        default="", description="Leave empty when using source_span_id; code copies original text"
    )
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


class SettingDetail(Contract):
    value: str = "Unspecified"
    basis: Literal["explicit", "inferred", "unspecified"] = "unspecified"
    evidence: str = ""
    confidence: Literal["high", "medium", "low"] = "low"


class StorySetting(Contract):
    period: SettingDetail = Field(default_factory=SettingDetail)
    country_or_region: SettingDetail = Field(default_factory=SettingDetail)
    polity_or_dynasty: SettingDetail = Field(default_factory=SettingDetail)
    cultural_context: SettingDetail = Field(default_factory=SettingDetail)
    architecture: SettingDetail = Field(default_factory=SettingDetail)
    clothing: SettingDetail = Field(default_factory=SettingDetail)
    material_culture: SettingDetail = Field(default_factory=SettingDetail)
    language: SettingDetail = Field(default_factory=SettingDetail)
    climate: SettingDetail = Field(default_factory=SettingDetail)
    visual_guidance: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


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
    story_setting: StorySetting = Field(default_factory=StorySetting)

    @model_validator(mode="after")
    def unique_identities(self):
        ids = [entity.id for entity in [*self.characters, *self.locations]]
        if any(not identity.strip() for identity in ids) or len(set(ids)) != len(ids):
            raise ValueError("Character and location IDs must be non-empty and globally unique")
        return self


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


class EpisodeBoundary(EpisodeOutline):
    end_event_number: int = Field(
        ge=1, description="One-based inclusive index of the LAST supplied event in this episode"
    )
    source_event_ids: list[str] = Field(
        default_factory=list, description="Leave empty; code assigns complete coverage from the boundary"
    )


class BoundaryBatch(Contract):
    episodes: list[EpisodeBoundary] = Field(min_length=1)


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


class SceneBoundary(ScenePlan):
    id: str = ""
    episode_number: int = 1
    bible_hash: str = ""
    source_event_ids: list[str] = Field(default_factory=list)
    duration: int = 4
    end_event_number: int = Field(ge=1)
    end_clip_number: int = Field(ge=1)


class SceneBoundaryBatch(Contract):
    scenes: list[SceneBoundary] = Field(min_length=1)


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


class SpeechCue(Contract):
    kind: Literal["narration", "dialogue"]
    speaker: str = Field(description="narrator for narration; exact bible character ID for dialogue")
    text: str = Field(min_length=1, max_length=1800)
    end_shot_id: str = Field(description="Last shot this complete sentence may span, within the same scene")
    delivery: str = "natural, conversational"
    pace: float = Field(default=1, ge=0.9, le=1.1)


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
    speech: list[SpeechCue] = Field(default_factory=list)
    edit: str
    information_change: str = ""
    hidden_information: str = ""


class ShotBatch(Contract):
    shots: list[ShotPlan] = Field(min_length=1)


class PlanRevision(Contract):
    scenes: list[ScenePlan] = Field(min_length=1)
    shots: list[ShotPlan] = Field(min_length=1)


class ShotDraft(ShotPlan):
    id: str = ""
    scene_id: str = ""
    bible_hash: str = ""
    duration: int = 4
    source_event_ids: list[str] = Field(default_factory=list)
    source_event_numbers: list[int] = Field(min_length=1)


class ShotDraftBatch(Contract):
    shots: list[ShotDraft] = Field(min_length=1)


class AudioLine(SpeechCue):
    shot_id: str


class AudioScript(Contract):
    lines: list[AudioLine] = Field(min_length=1)


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


def scene_audio_schema(shot_ids, character_ids):
    """Put canonical IDs into provider JSON grammar, not only natural-language prompts."""
    line = create_model(
        "SceneAudioLine",
        __base__=AudioLine,
        shot_id=(Literal[tuple(shot_ids)], ...),
        end_shot_id=(Literal[tuple(shot_ids)], ...),
        speaker=(Literal[("narrator", *sorted(character_ids))], ...),
    )
    return create_model(
        "SceneAudioScript",
        __base__=AudioScript,
        lines=(list[line], Field(min_length=1, max_length=len(shot_ids))),
    )
