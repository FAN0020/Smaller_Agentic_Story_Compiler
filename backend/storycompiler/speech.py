"""Speech direction and measured timing, independent of four-second video chunks."""

from pathlib import Path

from .media import probe, run

KOKORO_VOICES = {
    "af_heart": "Heart · warm American narrator",
    "af_bella": "Bella · American female",
    "am_michael": "Michael · American male",
    "am_fenrir": "Fenrir · American male",
    "bf_emma": "Emma · British female",
    "bm_george": "George · British male",
}


def compile_cues(shots, characters, require_narration=True):
    positions, cursor = {}, 0
    for shot in shots:
        positions[shot["id"]] = (cursor, cursor + shot["duration"], shot["scene_id"])
        cursor += shot["duration"]
    cues = []
    for shot in shots:
        speech = shot.get("speech", [])
        if not speech and shot.get("narration", "").strip():
            speech = [
                {
                    "kind": "narration",
                    "speaker": "narrator",
                    "text": shot["narration"],
                    "end_shot_id": shot["id"],
                    "delivery": "natural storyteller",
                    "pace": 1,
                }
            ]
        for cue in speech:
            if cue["kind"] == "dialogue" and cue["speaker"] not in characters:
                raise ValueError("Audio speaker must be an approved character ID")
            if cue["kind"] == "narration" and cue["speaker"] != "narrator":
                raise ValueError("Narration speaker must be narrator")
            end = positions.get(cue["end_shot_id"])
            start = positions[shot["id"]]
            if not end or end[1] <= start[0] or end[2] != start[2]:
                raise ValueError(
                    f"Cue starting {shot['id']} cannot end at {cue['end_shot_id']}; choose an at-or-later shot in scene {shot['scene_id']}"
                )
            if not cue["text"].strip():
                raise ValueError("Use no cue for silence; spoken text cannot be empty")
            cues.append({**cue, "shot_id": shot["id"], "start": start[0], "deadline": end[1]})
    if require_narration and not any(c["kind"] == "narration" for c in cues):
        raise ValueError("Include narration to establish setting, cause and transitions, alongside dialogue")
    for i, cue in enumerate(cues):
        if i + 1 < len(cues):
            cue["deadline"] = min(cue["deadline"], cues[i + 1]["start"])
        if cue["deadline"] - cue["start"] < 0.3:
            raise ValueError(
                f"Speech cues overlap at {cue['shot_id']}. Use one cue per starting shot; combine the lines or start the next speaker in a later shot"
            )
    return cues


def schedule_cues(cues, durations):
    if len(cues) != len(durations):
        raise ValueError("Every speech cue needs a measured recording")
    result = []
    for cue, duration in zip(cues, durations, strict=True):
        available = cue["deadline"] - cue["start"] - 0.2
        if duration <= 0 or duration > available:
            raise ValueError(
                f"Speech at {cue['shot_id']} lasts {duration:.1f}s; {available:.1f}s available. "
                "Shorten the sentence or extend its end_shot_id in the plan before animation."
            )
        result.append({**cue, "end": cue["start"] + duration, "duration": duration})
    return result


class KokoroVoice:
    """CPU-only neural speech; a small session, released before image/video inference."""

    def __init__(self, root):
        import onnxruntime as ort
        from kokoro_onnx import Kokoro

        root = Path(root) / "models/kokoro"
        if not (root / "READY").exists():
            raise ValueError("Install neural speech: .venv/bin/python scripts/setup_models.py speech")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(root / "kokoro-v1.0.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.engine = Kokoro.from_session(session, str(root / "voices-v1.0.bin"))

    def speak(self, text, output, voice, pace=1):
        import soundfile as sf

        if voice not in KOKORO_VOICES:
            raise ValueError("Choose a supported Kokoro voice in Model settings")
        samples, rate = self.engine.create(
            text, voice=voice, speed=pace, lang="en-gb" if voice[0] == "b" else "en-us"
        )
        partial = output.with_name(output.stem + ".partial.wav")
        sf.write(partial, samples, rate)
        partial.replace(output)
        return float(probe(output)["format"]["duration"])


def write_audio_subtitles(cues, output):
    def stamp(seconds):
        ms = round(seconds * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"

    lines = ["WEBVTT\n"]
    for cue in cues:
        speaker = "Narrator" if cue["kind"] == "narration" else cue.get("speaker_name", cue["speaker"])
        text = cue["text"].replace("-->", "→").replace("<", "").replace(">", "")
        lines.append(f"{stamp(cue['start'])} --> {stamp(cue['end'])}\n{speaker}: {text}\n")
    output.write_text("\n".join(lines))


def mix_soundtrack(cues, directory, output, seconds):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    filters = []
    for i, cue in enumerate(cues):
        command += ["-i", str(directory / cue["file"])]
        filters.append(f"[{i}:a]aresample=48000,adelay={round(cue['start'] * 1000)}:all=1[a{i}]")
    inputs = "".join(f"[a{i}]" for i in range(len(cues)))
    filters.append(f"{inputs}amix=inputs={len(cues)}:normalize=0,apad,alimiter=limit=0.95[a]")
    partial = output.with_name(output.stem + ".partial.wav")
    run(
        command
        + [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[a]",
            "-t",
            str(seconds),
            "-ar",
            "48000",
            "-ac",
            "2",
            str(partial),
        ]
    )
    partial.replace(output)


def mux_soundtrack(video, audio):
    partial = video.with_name(video.stem + ".voiced.mp4")
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-filter_complex",
            "[0:a]volume=0.15[bg];[bg][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(partial),
        ]
    )
    partial.replace(video)


def cue_intervals(cues, start, duration):
    """Local performance timing without leaking a whole sentence's later plot facts."""
    return [
        {
            "speaker": cue.get("speaker_name", cue["speaker"]),
            "kind": cue["kind"],
            "delivery": cue.get("delivery", "natural"),
            "from_seconds": round(max(0, cue["start"] - start), 3),
            "to_seconds": round(min(duration, cue["end"] - start), 3),
        }
        for cue in cues
        if cue["start"] < start + duration and cue["end"] > start
    ]
