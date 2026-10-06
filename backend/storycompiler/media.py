"""Deterministic FFmpeg media operations. No model or story logic belongs here."""

import json
import shutil
import subprocess
from pathlib import Path


def run(command, timeout=300):
    if not shutil.which(command[0]):
        raise ValueError(f"{command[0]} is required. Install FFmpeg before production.")
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise ValueError(f"{command[0]} failed: {result.stderr[-1500:]}")
    return result.stdout


def probe(path: Path):
    return json.loads(
        run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    )


def extract_frame(video: Path, output: Path, seconds: float):
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(seconds),
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(output),
        ]
    )


def animatic_clip(image: Path, output: Path, seconds: int, size=(768, 432)):
    width, height = size
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf",
            (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
                f"zoompan=z='min(zoom+0.0003,1.06)':d=1:s={width}x{height}:fps=24,format=yuv420p"
            ),
            "-t",
            str(seconds),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def normalize_clip(source: Path, output: Path, seconds: int, size=(768, 432), narration: Path | None = None):
    width, height = size
    info = probe(source)
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    if narration:
        duration = float(probe(narration)["format"]["duration"])
        rate = max(1, duration / max(0.1, seconds - 0.15))
        if rate > 1.35:
            raise ValueError("Narration is too long for the shot. Shorten it in the plan before rendering.")
        cmd += [
            "-i",
            str(narration),
            "-filter_complex",
            f"[1:a]atempo={rate},apad[a]",
            "-map",
            "0:v:0",
            "-map",
            "[a]",
        ]
    elif has_audio:
        cmd += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
        ]
    cmd += [
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p",
        "-t",
        str(seconds),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(output),
    ]
    run(cmd)


def assemble(clips: list[Path], output: Path, target_seconds: int):
    if not clips:
        raise ValueError("No clips to assemble")
    listing = output.with_suffix(".concat.txt")
    listing.write_text("\n".join("file '" + str(p.resolve()).replace("'", "'\\''") + "'" for p in clips))
    partial = output.with_name(output.stem + ".partial.mp4")
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(partial),
        ]
    )
    duration = float(probe(partial)["format"]["duration"])
    if abs(duration - target_seconds) > 0.35:
        raise ValueError(f"Assembled duration {duration:.2f}s does not match {target_seconds}s")
    partial.replace(output)
    return duration


def system_voice(text: str, output: Path, voice: str):
    if not shutil.which("say"):
        raise ValueError(
            "System voice requires macOS. Choose OpenAI speech or no narration in Model settings."
        )
    textfile = output.with_suffix(".speech.txt")
    textfile.write_text(text)
    run(
        ["say", "-v", voice, "-r", "145", "-f", str(textfile), "-o", str(output), "--data-format=LEI16@24000"]
    )


def write_subtitles(shots: list[dict], output: Path):
    def stamp(seconds):
        milliseconds = round(seconds * 1000)
        return f"{milliseconds // 3600000:02}:{milliseconds // 60000 % 60:02}:{milliseconds // 1000 % 60:02}.{milliseconds % 1000:03}"

    parts = ["WEBVTT\n"]
    cursor = 0
    for shot in shots:
        text = shot.get("narration", "") or shot.get("sound", {}).get("dialogue", "")
        if text:
            parts.append(
                f"{stamp(cursor)} --> {stamp(cursor + shot['duration'])}\n{text.replace('-->', '→')}\n"
            )
        cursor += shot["duration"]
    output.write_text("\n".join(parts))
