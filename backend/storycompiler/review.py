"""Human plan corrections preserve history and require renewed production approval."""

import time

from .domain import CreativeBrief, fingerprint
from .planning import Planner
from .validation import validate_scenes, validate_shots, validate_timeline


def revise_plan(repo, p, number, revision):
    Planner.assert_frozen(p)
    if p["productions"].get(str(number), {}).get("clips"):
        raise ValueError("Production has started; create a project revision before changing its plan")
    episode = next(e for e in p["episodes"] if e["number"] == number)
    brief = CreativeBrief.model_validate(p["brief"])
    characters = {c["id"] for c in p["bible"]["characters"]}
    locations = {l["id"] for l in p["bible"]["locations"]}
    events = set(episode["source_event_ids"])
    scenes = [s.model_dump() for s in revision.scenes]
    shots = [s.model_dump() for s in revision.shots]
    errors = validate_scenes(scenes, brief.target_seconds, events, characters, locations)
    errors += validate_shots(revision.shots, p["bible_hash"], events, characters, locations)
    errors += validate_timeline(revision.shots, brief.target_seconds, 4, [4])
    if [eid for scene in scenes for eid in scene["source_event_ids"]] != episode["source_event_ids"]:
        errors.append("Scene boundaries must preserve the episode's ordered source coverage")
    expected_order = []
    for scene in scenes:
        group = [s for s in shots if s["scene_id"] == scene["id"]]
        expected_order.extend(s["id"] for s in group)
        if scene["bible_hash"] != p["bible_hash"] or scene["episode_number"] != number:
            errors.append("Every scene must inherit the current episode and frozen bible")
        if not group or sum(s["duration"] for s in group) != scene["duration"]:
            errors.append(f"Scene {scene['id']} needs complete shot coverage")
            continue
        if group[0]["start_state"] != scene["start_state"] or group[-1]["end_state"] != scene["end_state"]:
            errors.append(f"Scene {scene['id']} shots must match its start/end states")
        if any(s["location_id"] != scene["location_id"] for s in group):
            errors.append("Shots must inherit scene location")
        if {e for s in group for e in s["source_event_ids"]} != set(scene["source_event_ids"]):
            errors.append(f"Scene {scene['id']} shots must cover only that scene's assigned events")
        if any(not set(s["characters"]) <= set(scene["characters"]) for s in group):
            errors.append("Shot characters must belong to their scene")
    if expected_order != [s["id"] for s in shots]:
        errors.append("Shots must be ordered under their scenes")
    if errors:
        raise ValueError("; ".join(errors[:5]))
    plan = p["plans"].setdefault(str(number), {})
    plan.setdefault("revisions", []).append({k: plan.get(k) for k in ("hash", "scenes", "shots", "critique")})
    new_hash = fingerprint({"scenes": scenes, "shots": shots, "bible_hash": p["bible_hash"]})
    plan.update(
        scenes=scenes,
        shots=shots,
        hash=new_hash,
        status="review_required",
        hard_gate_errors=[],
        shot_reviews={},
        scene_reviews=[],
        critique={
            "findings": [],
            "strengths": [],
            "summary": "Reviewer revision. Timing and inheritance checks passed; review source fidelity before approving. Previous model review is superseded.",
        },
    )
    plan.pop("approved_hash", None)
    plan.pop("approved_at", None)
    p["audit"].append(
        {"action": "plan_manually_edited", "episode": number, "hash": new_hash, "at": time.time()}
    )
    p["status"] = "plan_review"
    repo.save_project(p)
    return p
