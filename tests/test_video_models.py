import pytest
from PIL import Image

WAN = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
VACE = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"


def test_selected_local_video_model_reaches_worker_without_ltx_fallback(tmp_path, monkeypatch):
    from storycompiler.generation import LocalGenerator

    generator = LocalGenerator(tmp_path, lambda: False)
    requests = []
    monkeypatch.setattr(generator, "_run", lambda *args, **kwargs: requests.append(kwargs))
    for model in (WAN, VACE):
        generator.video(
            "A bird flies", tmp_path / "frame.png", tmp_path / "clip.mp4", 42, 30, True, model=model
        )
    assert [r["model_id"] for r in requests] == [WAN, VACE]
    assert all(r["size"][0] < r["size"][1] for r in requests)
    with pytest.raises(ValueError, match="supported"):
        generator.video("Bird", tmp_path / "frame.png", tmp_path / "clip.mp4", 42, 30, model="unknown")


def test_vace_conditions_first_frame_and_generates_the_remaining_frames():
    from storycompiler.video_models import video_inputs

    image = Image.new("RGB", (512, 288), "red")
    inputs = video_inputs(VACE, image)
    assert len(inputs["video"]) == len(inputs["mask"]) == 65
    assert inputs["video"][0].getpixel((0, 0)) == (255, 0, 0)
    assert inputs["mask"][0].getextrema() == ((0, 0), (0, 0), (0, 0))
    assert inputs["mask"][-1].getextrema() == ((255, 255), (255, 255), (255, 255))
    assert video_inputs(WAN, image)["image"] is image


def test_missing_selected_checkpoint_cannot_pass_with_only_ltx_installed(tmp_path):
    from storycompiler.generation import LocalGenerator

    ready = tmp_path / "models/ltx-video/READY"
    ready.parent.mkdir(parents=True)
    ready.touch()
    with pytest.raises(ValueError, match="wan-video"):
        LocalGenerator(tmp_path, lambda: False).video(
            "Bird", tmp_path / "frame.png", tmp_path / "clip.mp4", 42, 30, model=WAN
        )


def test_unknown_local_video_selection_is_rejected():
    from storycompiler.settings import ModelSettings

    with pytest.raises(ValueError, match="supported"):
        ModelSettings(video_provider="local", video_model="unknown")
