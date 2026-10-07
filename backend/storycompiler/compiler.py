"""Compile canon and cinematic decisions without mutating them or losing critical fields."""

import json

from .contracts import ShotPlan


def setting_prompt(bible: dict) -> str:
    setting = bible.get("story_setting") or {}
    details = {}
    for field, detail in setting.items():
        if isinstance(detail, dict) and "value" in detail:
            details[field] = {
                "value": detail.get("value", "Unspecified"),
                "basis": detail.get("basis", "unspecified"),
                "confidence": detail.get("confidence", "low"),
            }
    guidance = setting.get("visual_guidance", [])
    guardrails = setting.get("guardrails", [])
    return "\n".join(
        [
            "Story setting anchors (explicit facts and cautious inferences; unspecified means do not invent): "
            + json.dumps(details, ensure_ascii=False),
            "Setting visual guidance: " + "; ".join(guidance),
            "Setting guardrails: " + "; ".join(guardrails),
            "Keep architecture, clothing, objects and background consistent with these anchors. Do not add unsupported named places, dynasties, symbols or anachronistic details.",
        ]
    )


def compile_frame(shot: ShotPlan, bible: dict, scene: dict) -> str:
    characters = [c for c in bible["characters"] if c["id"] in shot.characters]
    location = next(l for l in bible["locations"] if l["id"] == shot.location_id)
    return "\n".join(
        [
            bible["style_instruction"],
            setting_prompt(bible),
            "A single unified cinematic opening frame. All subjects share one environment. No panels, collage, labels or text.",
            "Subjects: "
            + "; ".join(f"{c['name']}: {c['appearance']}; {c.get('costume', '')}" for c in characters),
            f"Location: {location['name']}, {location['appearance']}",
            "Scene: " + "; ".join(scene.get(k, "") for k in ("geography", "lighting", "environment")),
            "Depict this exact starting state before any movement: "
            + json.dumps(shot.start_state, ensure_ascii=False),
            "Framing: "
            + ", ".join(
                v for k, v in shot.camera.model_dump().items() if v and k not in ("movement", "motivation")
            ),
            "Keep unchanged: " + "; ".join(shot.locked),
        ]
    )


def compile_shot(shot: ShotPlan, bible: dict, limit: int = 12000, scene: dict | None = None) -> str:
    chars = [c for c in bible["characters"] if c["id"] in shot.characters]
    loc = next(x for x in bible["locations"] if x["id"] == shot.location_id)
    pieces = [
        bible["style_instruction"],
        setting_prompt(bible),
        "Subjects: " + "; ".join(f"{c['name']}: {c['appearance']}; {c.get('costume', '')}" for c in chars),
        "Visible action: " + shot.action,
        "Visual focus: " + shot.visual_focus,
        "Performance: "
        + "; ".join(p.behavior + ("; gaze " + p.gaze if p.gaze else "") for p in shot.performance),
        "Camera: " + ", ".join(v for v in shot.camera.model_dump().values() if v),
        f"Location: {loc['name']}, {loc['appearance']}. {loc.get('geography', '')}. {loc.get('lighting', '')}",
        "Scene geography, light and environment: "
        + "; ".join((scene or {}).get(field, "") for field in ("geography", "lighting", "environment")),
        "Blocking: " + shot.blocking,
        "Start: " + json.dumps(shot.start_state, ensure_ascii=False),
        "End: " + json.dumps(shot.end_state, ensure_ascii=False),
        "Keep unchanged: " + "; ".join(shot.locked),
        "Only change: " + "; ".join(shot.allowed_changes),
        "Sound: " + json.dumps(shot.sound.model_dump(), ensure_ascii=False),
        "No captions, watermarks, extra limbs, identity changes or unmotivated background changes.",
    ]
    prompt = "\n".join(pieces)
    if len(prompt) > limit:
        raise ValueError(
            f"Prompt exceeds provider budget ({len(prompt)}/{limit}); simplify the shot explicitly"
        )
    return prompt
