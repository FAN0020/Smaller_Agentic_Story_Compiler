"""Deterministic hard gates; deliberately make no claim about artistic quality."""

from .contracts import ShotPlan


def validate_scenes(scenes, target_seconds, event_ids, character_ids, location_ids):
    errors = []
    if sum(s["duration"] for s in scenes) != target_seconds or any(s["duration"] % 4 for s in scenes):
        errors.append(f"Scene durations must sum to {target_seconds}, in multiples of 4 seconds")
    if {e for s in scenes for e in s["source_event_ids"]} != event_ids:
        errors.append("Scenes must cover all and only assigned episode events")
    if len({s["id"] for s in scenes}) != len(scenes):
        errors.append("Scene IDs must be unique")
    previous = None
    for s in scenes:
        if not set(s["characters"]) <= character_ids or s["location_id"] not in location_ids:
            errors.append("Use only canonical character/location IDs")
        if previous and not s.get("transition_reason") and s["start_state"] != previous["end_state"]:
            errors.append(
                f"Scene {s['id']}: continuity start_state must exactly inherit previous end_state {previous['end_state']}"
            )
        previous = s
    return errors


def validate_shots(
    shots: list[ShotPlan],
    bible_hash: str,
    event_ids: set[str],
    character_ids: set[str],
    location_ids: set[str],
) -> list[str]:
    errors, covered, seen = [], set(), set()
    previous = None
    for shot in shots:
        if shot.id in seen:
            errors.append(f"{shot.id}: duplicate shot ID")
        seen.add(shot.id)
        if shot.bible_hash != bible_hash:
            errors.append(f"{shot.id}: stale bible inheritance")
        if not set(shot.characters) <= character_ids:
            errors.append(f"{shot.id}: unknown character identity")
        if shot.location_id not in location_ids:
            errors.append(f"{shot.id}: unknown location identity")
        if not set(shot.source_event_ids) <= event_ids:
            errors.append(f"{shot.id}: unknown source event")
        covered.update(shot.source_event_ids)
        if previous and not shot.transition_reason:
            for key, value in previous.end_state.items():
                if shot.start_state.get(key) != value:
                    errors.append(f"{shot.id}: continuity mismatch for {key}; inherit {value!r}")
        if shot.start_state != shot.end_state and not shot.state_reason.strip():
            errors.append(f"{shot.id}: state change needs a visible causal action")
        if not shot.action.strip() or not shot.locked:
            errors.append(f"{shot.id}: missing action or continuity locks")
        if any(p.character_id not in shot.characters for p in shot.performance):
            errors.append(f"{shot.id}: performance references a non-participating character")
        previous = shot
    missing = event_ids - covered
    if missing:
        errors.append(f"Uncovered source events: {', '.join(sorted(missing))}")
    return errors


def validate_timeline(
    shots: list[ShotPlan],
    target_seconds: int,
    max_clip_seconds: int,
    allowed_durations: list[int] | None = None,
) -> list[str]:
    errors = []
    duration = sum(s.duration for s in shots)
    if duration != target_seconds or not 60 <= duration <= 240:
        errors.append(f"Timeline is {duration}s; it must equal the approved {target_seconds}s (60–240s)")
    for shot in shots:
        if shot.duration > max_clip_seconds:
            errors.append(
                f"{shot.id}: {shot.duration}s exceeds provider limit {max_clip_seconds}s; re-direct"
            )
        if allowed_durations and shot.duration not in allowed_durations:
            errors.append(f"{shot.id}: choose a supported duration {allowed_durations}")
    return errors


def validate_outline(episodes: list[dict], events: list[dict]) -> list[str]:
    expected = [e["id"] for e in events]
    actual = [i for ep in episodes for i in ep["source_event_ids"]]
    errors = []
    if actual != expected:
        errors.append("Episode boundaries must cover every source event exactly once and in source order")
    if [e["number"] for e in episodes] != list(range(1, len(episodes) + 1)):
        errors.append("Episode numbers must be consecutive from 1")
    return errors
