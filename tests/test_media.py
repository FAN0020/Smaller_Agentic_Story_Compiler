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
