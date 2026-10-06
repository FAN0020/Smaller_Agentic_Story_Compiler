import importlib.util

import pytest
from PIL import Image


def test_real_ffmpeg_assembly_preserves_order_duration_and_audio(tmp_path):
    assert importlib.util.find_spec("storycompiler.media"), "Media pipeline is missing"
    from storycompiler.media import animatic_clip, assemble, probe

    red = tmp_path / "red.png"
    blue = tmp_path / "blue.png"
    Image.new("RGB", (320, 180), "red").save(red)
    Image.new("RGB", (320, 180), "blue").save(blue)
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    animatic_clip(red, first, 1, (320, 180))
    animatic_clip(blue, second, 1, (320, 180))
    output = tmp_path / "episode.mp4"
    assemble([first, second], output, 2)
    info = probe(output)
    assert abs(float(info["format"]["duration"]) - 2) < 0.15
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    from storycompiler.media import extract_frame

    extract_frame(output, tmp_path / "a.png", 0.2)
    extract_frame(output, tmp_path / "b.png", 1.2)
    a = Image.open(tmp_path / "a.png").getpixel((100, 100))
    b = Image.open(tmp_path / "b.png").getpixel((100, 100))
    assert a[0] > 200 and a[2] < 30
    assert b[2] > 200 and b[0] < 30


def test_render_gate_rejects_unapproved_or_stale_references(tmp_path):
    assert importlib.util.find_spec("storycompiler.production"), "Production gate is missing"
    from storycompiler.production import assert_production_approved

    p = {"bible": {}, "bible_hash": None, "references": {}, "references_hash": None, "plans": {}}
    with pytest.raises(ValueError):
        assert_production_approved(p, [1])


def test_missing_local_model_is_actionable_without_paid_fallback(tmp_path):
    assert importlib.util.find_spec("storycompiler.generation"), "Generation adapters are missing"
    from storycompiler.generation import LocalGenerator

    with pytest.raises(ValueError, match="setup_models"):
        LocalGenerator(tmp_path, lambda: False).image("A tree", tmp_path / "out.png", 42)


def test_narration_mix_keeps_original_video_sound(tmp_path):
    import math
    import wave
    from array import array

    from storycompiler.media import normalize_clip, run

    source, voice, output = (tmp_path / n for n in ("source.mp4", "voice.wav", "mixed.mp4"))
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=160x90:r=24:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=400:duration=2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ]
    )
    run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=800:duration=1", str(voice)])
    normalize_clip(source, output, 2, (160, 90), voice)
    decoded = tmp_path / "decoded.wav"
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(output),
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "pcm_s16le",
            str(decoded),
        ]
    )
    with wave.open(str(decoded)) as audio:
        samples = array("h", audio.readframes(12000))

    def energy(hz):
        real = sum(v * math.cos(2 * math.pi * hz * i / 24000) for i, v in enumerate(samples))
        imaginary = sum(v * math.sin(2 * math.pi * hz * i / 24000) for i, v in enumerate(samples))
        return real * real + imaginary * imaginary

    assert energy(400) > energy(600) * 100
    assert energy(800) > energy(600) * 100


def test_changed_reference_hash_cannot_reuse_prior_approval():
    from storycompiler.domain import fingerprint
    from storycompiler.validation import assert_references_frozen, reference_manifest

    p = {
        "bible": {"characters": [{"id": "mouse"}], "locations": [{"id": "forest"}]},
        "bible_hash": "canon",
        "references": {
            name: {"sha256": "original", "bible_hash": "canon", "approved": True}
            for name in ("mouse", "forest")
        },
    }
    p["references_hash"] = fingerprint(reference_manifest(p))
    assert_references_frozen(p)
    p["references"]["mouse"]["sha256"] = "changed"
    with pytest.raises(ValueError, match="changed"):
        assert_references_frozen(p)


def test_four_minute_episode_does_not_accumulate_audio_padding(tmp_path):
    from storycompiler.media import animatic_clip, assemble, probe

    image = tmp_path / "frame.png"
    Image.new("RGB", (160, 90), "blue").save(image)
    clip = tmp_path / "clip.mp4"
    animatic_clip(image, clip, 4, (160, 90))
    episode = tmp_path / "long-episode.mp4"
    duration = assemble([clip] * 60, episode, 240)
    assert abs(duration - 240) < 0.35
    video = next(s for s in probe(episode)["streams"] if s["codec_type"] == "video")
    assert int(video["nb_frames"]) == 24 * 240
