"""Checkpoint speech before visual generation; bind actual timing to the approved plan."""

import gc
import hashlib

from .domain import fingerprint
from .generation import Cancelled
from .media import probe, system_voice
from .resources import check_capacity, inference_lease, snapshot
from .speech import KokoroVoice, compile_cues, mix_soundtrack, schedule_cues


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_soundtrack(producer, project, number, production, directory):
    settings = producer.settings
    names = {c["id"]: c["name"] for c in project["bible"]["characters"]}
    characters = sorted(c["id"] for c in project["bible"]["characters"])
    cues = compile_cues(project["plans"][str(number)]["shots"], set(characters))
    prefix = production["prefix"] + f"ep{number}-"
    defaults = {
        "kokoro": ["am_michael", "af_bella", "am_fenrir", "bf_emma", "bm_george"],
        "system": ["Alex", "Victoria"],
        "openai": ["ash", "coral", "onyx", "nova"],
    }
    options = [v for v in defaults[settings.voice_provider] if v != settings.voice]
    cast = {
        key: (
            settings.character_voices.get(project["id"] + "/" + key)
            or settings.character_voices.get(key)
            or options[i % len(options)]
        )
        for i, key in enumerate(characters)
    }
    cast["narrator"] = settings.voice
    basis = fingerprint({"cues": cues, "cast": cast, "provider": settings.voice_provider})
    manifest = production.setdefault("soundtrack", {"basis": basis, "recordings": {}, "cast": cast})
    if manifest["basis"] != basis:
        raise ValueError("Speech plan or cast changed. Create a new take to preserve this recording.")
    durations = []
    recorded = []
    neural = None
    try:
        # Keep speech from overlapping another Studio GPU/LLM job.
        with inference_lease():
            if settings.voice_provider == "kokoro":
                check_capacity("hexgrad/Kokoro-82M", snapshot(producer.repo.root))
            for i, cue in enumerate(cues):
                if producer.cancelled():
                    raise Cancelled("Speech stopped; completed recordings are saved")
                file = f"{prefix}speech-{i + 1:03}.wav"
                output = directory / file
                receipt = manifest["recordings"].get(str(i))
                if not receipt or not output.exists() or receipt["sha256"] != checksum(output):
                    voice = cast[cue["speaker"]]
                    producer.progress(0, f"Recording {cue['speaker']}, sentence {i + 1} of {len(cues)}…")
                    if settings.voice_provider == "kokoro":
                        neural = neural or KokoroVoice(producer.repo.root)
                        neural.speak(cue["text"], output, voice, cue.get("pace", 1))
                    elif settings.voice_provider == "system":
                        system_voice(cue["text"], output, voice)
                    else:
                        producer.hosted().speech(
                            cue["text"], output, voice, cue.get("delivery", "Natural delivery")
                        )
                    receipt = {
                        "file": file,
                        "sha256": checksum(output),
                        "duration": float(probe(output)["format"]["duration"]),
                    }
                    manifest["recordings"][str(i)] = receipt
                    producer.repo.save_project(project)
                durations.append(receipt["duration"])
                recorded.append({**cue, "file": file, "speaker_name": names.get(cue["speaker"], "Narrator")})
    finally:
        del neural
        gc.collect()
    timed = schedule_cues(recorded, durations)
    output = directory / f"{prefix}soundtrack.wav"
    mix_soundtrack(timed, directory, output, project["brief"]["target_seconds"])
    manifest.update(file=output.name, sha256=checksum(output), cues=timed, status="timed", cast=cast)
    producer.repo.save_project(project)
    return manifest
