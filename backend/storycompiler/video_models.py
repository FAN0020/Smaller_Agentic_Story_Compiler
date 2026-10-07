"""Supported local motion profiles; all consume the approved opening frame."""

from PIL import Image

LTX = "Lightricks/LTX-Video-0.9.1"
WAN = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
VACE = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"

LOCAL_VIDEO_MODELS = {
    LTX: {
        "folder": "ltx-video",
        "installer": "video",
        "label": "LTX-Video 0.9.1",
        "description": "Existing compact motion baseline. Locally exercised on this Mac.",
        "revision": "0dfb9a9b26f48256bbafc4e9fa337445ff76dc1c",
        "frames": 97,
        "fps": 24,
        "size": (512, 288),
        "memory_gib": 12,
    },
    WAN: {
        "folder": "wan-2.2-ti2v-5b",
        "installer": "wan-video",
        "label": "Wan 2.2 TI2V · 5B",
        "description": "Newer image-to-video quality candidate. Apache 2.0. Compact 512×288 preset; Mac performance and quality need a real render.",
        "revision": "b8fff7315c768468a5333511427288870b2e9635",
        "frames": 97,
        "fps": 24,
        "size": (512, 288),
        "memory_gib": 16,
    },
    VACE: {
        "folder": "wan-2.1-vace-1.3b",
        "installer": "vace-video",
        "label": "Wan VACE · 1.3B",
        "description": "Smaller image-guided alternative using first-frame conditioning. Apache 2.0. Compact 512×288 preset; quality is not ranked above LTX.",
        "revision": "ec4d2cb062b548996b179d493fdd05340de702a1",
        "frames": 65,
        "fps": 16,
        "size": (512, 288),
        "memory_gib": 13.5,
    },
}


def video_profile(model):
    if model not in LOCAL_VIDEO_MODELS:
        raise ValueError("Choose a supported local video model")
    return LOCAL_VIDEO_MODELS[model]


def video_inputs(model, image):
    """VACE black pixels lock the opening frame; white masks request new motion."""
    profile = video_profile(model)
    if model != VACE:
        return {"image": image}
    blank = Image.new("RGB", image.size, "black")
    generate = Image.new("RGB", image.size, "white")
    return {
        "video": [image] + [blank] * (profile["frames"] - 1),
        "mask": [blank] + [generate] * (profile["frames"] - 1),
    }
