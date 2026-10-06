"""Compile canon and cinematic decisions without mutating them or losing critical fields."""

import json

from .contracts import ShotPlan


def compile_shot(shot: ShotPlan, bible: dict, limit: int = 12000) -> str:
    chars = [c for c in bible["characters"] if c["id"] in shot.characters]
    loc = next(x for x in bible["locations"] if x["id"] == shot.location_id)
    pieces = [
        bible["style_instruction"],
        "Subjects: " + "; ".join(f"{c['name']}: {c['appearance']}; {c.get('costume', '')}" for c in chars),
        "Visible action: " + shot.action,
        "Visual focus: " + shot.visual_focus,
        "Performance: "
        + "; ".join(p.behavior + ("; gaze " + p.gaze if p.gaze else "") for p in shot.performance),
        "Camera: " + ", ".join(v for v in shot.camera.model_dump().values() if v),
        f"Location: {loc['name']}, {loc['appearance']}. {loc.get('geography', '')}. {loc.get('lighting', '')}",
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
