"""Narrow agents coordinated by deterministic, checkpointed application logic."""

import math
import re
import time

from .contracts import BibleDraft, ChunkAnalysis, CriticReport, EpisodeBatch, SceneBatch, ShotBatch, ShotPlan
from .domain import STYLE_BY_ID, CreativeBrief, chunk_source, fingerprint
from .validation import validate_outline, validate_shots, validate_timeline


class ReviewRequired(ValueError):
    pass


class Planner:
    def __init__(self, repo, llm, progress):
        self.repo, self.llm, self.progress = repo, llm, progress

    def checkpoint(self, p, message, progress=0):
        self.repo.save_project(p)
        self.progress(progress, message)

    def analyze(self, p):
        if p["bible_hash"]:
            raise ValueError("Frozen analysis cannot be overwritten; create a revision")
        chunks = chunk_source(p["source"])
        for i, chunk in enumerate(chunks):
            if chunk.id in p["analyses"]:
                continue
            self.progress(i / len(chunks) * 0.7, f"Reading story section {i + 1} of {len(chunks)}…")
            errors = []
            for attempt in range(3):
                analysis = self.llm.generate(
                    "source-analysis",
                    {"source": chunk.model_dump(), "repair_feedback": errors},
                    ChunkAnalysis,
                )
                errors = []
                for event in analysis.events:
                    pattern = r"\s+".join(re.escape(word) for word in event.quote.split())
                    match = re.search(pattern, chunk.text) if pattern else None
                    if match is None:
                        errors.append(
                            f"Copy a shorter exact evidence quote for: {event.summary}. Invalid quote: {event.quote}"
                        )
                    else:
                        event.quote = match.group(0)
                if not errors:
                    break
            if errors:
                raise ValueError(f"Source evidence could not be grounded in section {i + 1} after 3 attempts")
            p["analyses"][chunk.id] = analysis.model_dump()
            self.checkpoint(p, f"Read section {i + 1} of {len(chunks)}", (i + 1) / len(chunks) * 0.7)
        events = []
        for chunk in chunks:
            for j, event in enumerate(p["analyses"][chunk.id]["events"]):
                events.append(
                    {
                        **event,
                        "id": f"{chunk.id}-ev{j + 1}",
                        "source_id": chunk.id,
                        "source_start": chunk.start + chunk.text.index(event["quote"]),
                        "source_end": chunk.start + chunk.text.index(event["quote"]) + len(event["quote"]),
                        "source_characters": len(chunk.text) / len(p["analyses"][chunk.id]["events"]),
                    }
                )
        p["events"] = events
        brief = CreativeBrief.model_validate(p["brief"])
        # Rolling synthesis includes every section without sending a whole novel in one context.
        group_size = 8
        for start in range(p.get("bible_sections_done", 0), len(chunks), group_size):
            group = chunks[start : start + group_size]
            self.progress(0.7 + 0.25 * start / len(chunks), "Establishing the shared story world…")
            draft = self.llm.generate(
                "series-bible",
                {
                    "brief": brief.model_dump(),
                    "policy": brief.policy.model_dump(),
                    "source_sections": [p["analyses"][c.id] for c in group],
                    "previous_draft": p.get("bible"),
                    "style": STYLE_BY_ID[brief.style].model_dump(),
                    "is_final_section": start + group_size >= len(chunks),
                },
                BibleDraft,
            )
            bible = draft.model_dump()
            for name in ("characters", "locations"):
                ids = [x["id"] for x in bible[name]]
                if len(ids) != len(set(ids)):
                    raise ValueError(f"Duplicate {name} identities; retry analysis")
            bible.update(
                style_instruction=STYLE_BY_ID[brief.style].instruction,
                policy=brief.policy.model_dump(),
                brief=brief.model_dump(),
                source_hash=fingerprint(p["source"]),
            )
            p["bible"] = bible
            p["bible_sections_done"] = start + len(group)
            self.checkpoint(p, "Shared world drafted", 0.95)
        p["status"] = "bible_review"
        p["estimated_episode_count"] = max(
            1, math.ceil(len(p["source"].split()) / (brief.target_seconds * 2.2))
        )
        self.checkpoint(p, "Review and freeze the series bible", 1)

    def freeze(self, p):
        if not p["bible"]:
            raise ValueError("Analyze the story before freezing its bible")
        p["bible_hash"] = fingerprint(p["bible"])
        p["status"] = "bible_frozen"
        p["audit"].append({"action": "bible_approved", "hash": p["bible_hash"], "at": time.time()})
        self.repo.save_project(p)

    @staticmethod
    def assert_frozen(p):
        if not p["bible_hash"]:
            raise ValueError("Review and freeze the series bible before episode planning")
        if p["bible_hash"] != fingerprint(p["bible"]):
            raise ValueError("Frozen bible changed; create a new revision")

    def episodes(self, p):
        self.assert_frozen(p)
        brief = CreativeBrief.model_validate(p["brief"])
        completed = {e for ep in p["episodes"] for e in ep["source_event_ids"]}
        remaining = [e for e in p["events"] if e["id"] not in completed]
        for start in range(0, len(remaining), 24):
            group = remaining[start : start + 24]
            self.progress(start / max(1, len(remaining)), "Finding episode boundaries…")
            context = {
                "bible": p["bible"],
                "events": group,
                "target_seconds": brief.target_seconds,
                "next_number": len(p["episodes"]) + 1,
                "previous_episode": p["episodes"][-1:] or [],
                "is_final_batch": start + 24 >= len(remaining),
            }
            errors = []
            for attempt in range(3):
                batch = self.llm.generate(
                    "episode-planner", {**context, "repair_feedback": errors}, EpisodeBatch
                )
                eps = [e.model_dump() for e in batch.episodes]
                for i, ep in enumerate(eps):
                    ep["number"] = len(p["episodes"]) + i + 1
                    ep["bible_hash"] = p["bible_hash"]
                    ep["target_seconds"] = brief.target_seconds
                actual = [eid for ep in eps for eid in ep["source_event_ids"]]
                errors = (
                    []
                    if actual == [e["id"] for e in group]
                    else ["Partition every supplied event exactly once, in supplied order."]
                )
                for ep in eps:
                    if any(b["seconds"] > brief.target_seconds for b in ep["emotion_curve"]):
                        errors.append("Emotion beat timestamps exceed episode duration")
                    if ep["hook_latency"] > brief.policy.hook_latency_max_seconds:
                        errors.append(
                            f"Bring the source-supported entry hook within {brief.policy.hook_latency_max_seconds} seconds"
                        )
                    known = {e["id"] for e in p["events"]}
                    if any(
                        l["setup_event_id"] not in known
                        or (l["payoff_event_id"] and l["payoff_event_id"] not in known)
                        for l in ep["open_loop_ledger"]
                    ):
                        errors.append("Open loops must reference actual source events")
                if not errors:
                    break
            if errors:
                raise ReviewRequired("; ".join(errors))
            p["episodes"].extend(eps)
            self.checkpoint(
                p, f"{len(p['episodes'])} episodes planned", (start + len(group)) / len(remaining)
            )
        errors = validate_outline(p["episodes"], p["events"])
        if errors:
            raise ReviewRequired("; ".join(errors))
        p["status"] = "episodes_ready"
        self.checkpoint(p, "Choose episodes and approve the visual references", 1)

    def direct(self, p, numbers):
        self.assert_frozen(p)
        bible = p["bible"]
        brief = CreativeBrief.model_validate(p["brief"])
        for index, number in enumerate(numbers):
            key = str(number)
            if p["plans"].get(key, {}).get("status") == "ready":
                continue
            episode = next(ep for ep in p["episodes"] if ep["number"] == number)
            events = [e for e in p["events"] if e["id"] in episode["source_event_ids"]]
            context = {
                "episode": episode,
                "bible": bible,
                "bible_hash": p["bible_hash"],
                "source_events": events,
                "target_seconds": brief.target_seconds,
            }
            plan = p["plans"].get(key, {"scenes": [], "shots": [], "status": "planning", "attempts": []})
            if not plan["scenes"]:
                errors = []
                for attempt in range(3):
                    self.progress(index / len(numbers), f"Designing Episode {number} scenes…")
                    scenes = self.llm.generate(
                        "scene-director", {**context, "repair_feedback": errors}, SceneBatch
                    )
                    errors = []
                    if sum(s.duration for s in scenes.scenes) != brief.target_seconds:
                        errors.append(f"Scene durations must sum to {brief.target_seconds}")
                    if any(s.duration % 4 for s in scenes.scenes):
                        errors.append("Scene durations must be multiples of 4 seconds")
                    actual = {e for s in scenes.scenes for e in s.source_event_ids}
                    if actual != set(episode["source_event_ids"]):
                        errors.append("Scenes must cover all and only episode events")
                    for s in scenes.scenes:
                        if s.location_id not in {l["id"] for l in bible["locations"]} or not set(
                            s.characters
                        ) <= {c["id"] for c in bible["characters"]}:
                            errors.append("Use only canonical character/location IDs")
                    if not errors:
                        break
                if errors:
                    raise ReviewRequired("; ".join(errors))
                plan["scenes"] = [
                    {**s.model_dump(), "bible_hash": p["bible_hash"], "episode_number": number}
                    for s in scenes.scenes
                ]
                p["plans"][key] = plan
                self.checkpoint(p, f"Episode {number}: scenes saved")
            for scene_index, scene in enumerate(plan["scenes"]):
                if any(s["scene_id"] == scene["id"] for s in plan["shots"]):
                    continue
                errors = []
                for attempt in range(3):
                    self.progress(
                        (index + scene_index / len(plan["scenes"])) / len(numbers),
                        f"Directing Episode {number}, scene {scene_index + 1}…",
                    )
                    result = self.llm.generate(
                        "shot-director",
                        {
                            **context,
                            "scene": scene,
                            "shot_count": scene["duration"] // 4,
                            "previous_shot": plan["shots"][-1:] or [],
                            "repair_feedback": errors,
                        },
                        ShotBatch,
                    )
                    shots = result.shots
                    errors = validate_shots(
                        shots,
                        p["bible_hash"],
                        set(scene["source_event_ids"]),
                        {c["id"] for c in bible["characters"]},
                        {l["id"] for l in bible["locations"]},
                    )
                    if len(shots) != scene["duration"] // 4 or any(s.duration != 4 for s in shots):
                        errors.append(f"Exactly {scene['duration'] // 4} shots of 4 seconds are required")
                    if any(s.scene_id != scene["id"] for s in shots):
                        errors.append("Every shot must inherit the supplied scene ID")
                    if (
                        shots[0].start_state != scene["start_state"]
                        or shots[-1].end_state != scene["end_state"]
                    ):
                        errors.append("First start_state and last end_state must equal scene boundaries")
                    plan["attempts"].append(
                        {
                            "scene": scene["id"],
                            "attempt": attempt + 1,
                            "errors": errors,
                            "shots": [s.model_dump() for s in shots],
                        }
                    )
                    if not errors:
                        break
                if errors:
                    p["plans"][key] = plan
                    self.checkpoint(p, "Shot planning needs review")
                    raise ReviewRequired("; ".join(errors[:5]))
                plan["shots"].extend(s.model_dump() for s in shots)
                self.checkpoint(p, f"Episode {number}: scene {scene_index + 1} coverage saved")
            shots = [ShotPlan.model_validate(s) for s in plan["shots"]]
            errors = validate_shots(
                shots,
                p["bible_hash"],
                set(episode["source_event_ids"]),
                {c["id"] for c in bible["characters"]},
                {l["id"] for l in bible["locations"]},
            )
            errors += validate_timeline(shots, brief.target_seconds, 4)
            plan["hard_gate_errors"] = errors
            if errors:
                self.checkpoint(p, "Plan continuity requires review")
                raise ReviewRequired("; ".join(errors[:5]))
            self.progress((index + 0.9) / len(numbers), f"Checking Episode {number} direction…")
            critique = self.llm.generate(
                "plan-critic", {**context, "scenes": plan["scenes"], "shots": plan["shots"]}, CriticReport
            )
            plan["critique"] = critique.model_dump()
            plan["status"] = (
                "review_required" if any(f.severity == "error" for f in critique.findings) else "ready"
            )
            plan["hash"] = fingerprint(
                {"scenes": plan["scenes"], "shots": plan["shots"], "bible_hash": p["bible_hash"]}
            )
            p["status"] = "plan_review"
            self.checkpoint(p, f"Episode {number} is ready for plan review", (index + 1) / len(numbers))
