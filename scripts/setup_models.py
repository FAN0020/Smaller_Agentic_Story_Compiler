#!/usr/bin/env python3
"""Install official local checkpoints, converting float32 shards to bfloat16 once.

Only files inside the selected model directory are changed. Downloads are resumable.
Run outside active rendering: conversion and inference both need memory.
"""

import argparse
import json
import os
import platform
import shutil
from pathlib import Path

IMAGE_REVISION = "b261bac6fd2cf515557d5d0707481eafa0485ec2"
FLUX_REVISION = "e7b7dc27f91deacad38e78976d1f2b499d76a294"
VIDEO_REVISION = "0dfb9a9b26f48256bbafc4e9fa337445ff76dc1c"


def install_fast_image(root):
    from huggingface_hub import snapshot_download

    target = root / "sd-turbo"
    snapshot_download(
        "stabilityai/sd-turbo",
        revision=IMAGE_REVISION,
        local_dir=target,
        allow_patterns=["*.json", "*.txt", "*.model", "*fp16.safetensors"],
    )
    (target / "READY").write_text(f"stabilityai/sd-turbo; {IMAGE_REVISION}; fp16\n")
    print("Image model installed:", target, flush=True)


def install_image(root):
    from huggingface_hub import snapshot_download

    target = root / "flux2-klein-4b"
    snapshot_download(
        "black-forest-labs/FLUX.2-klein-4B",
        revision=FLUX_REVISION,
        local_dir=target,
        allow_patterns=[
            "model_index.json",
            "scheduler/*",
            "text_encoder/*",
            "tokenizer/*",
            "transformer/*",
            "vae/*",
            "LICENSE.md",
        ],
        max_workers=2,
        token=False,
    )
    (target / "READY").write_text(f"black-forest-labs/FLUX.2-klein-4B; {FLUX_REVISION}; bfloat16\n")
    print("Multi-reference image model installed:", target, flush=True)


def install_video(root):
    import torch
    from huggingface_hub import HfApi, hf_hub_download
    from safetensors.torch import load_file, save_file

    repo = "Lightricks/LTX-Video-0.9.1"
    target = root / "ltx-video"
    target.mkdir(parents=True, exist_ok=True)
    files = HfApi().list_repo_files(repo, revision=VIDEO_REVISION)
    selected = [
        f
        for f in files
        if f == "model_index.json"
        or f.startswith(("scheduler/", "tokenizer/", "text_encoder/", "transformer/", "vae/"))
    ]
    selected = [f for f in selected if f.endswith((".json", ".model", ".txt", ".safetensors"))]
    for name in selected:
        output = target / name
        marker = output.with_suffix(output.suffix + ".converted")
        if name.endswith(".safetensors") and marker.exists():
            continue
        if not name.endswith(".safetensors"):
            hf_hub_download(repo, name, revision=VIDEO_REVISION, local_dir=target)
            continue
        if shutil.disk_usage(root).free < 18 * 1024**3:
            raise RuntimeError("Need at least 18 GiB free for shard conversion and system headroom")
        print("Downloading and converting", name, flush=True)
        downloaded = Path(hf_hub_download(repo, name, revision=VIDEO_REVISION, local_dir=root / "downloads"))
        tensors = load_file(downloaded)
        converted = {
            key: value.to(torch.bfloat16) if value.is_floating_point() else value
            for key, value in tensors.items()
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(".tmp")
        save_file(converted, temp, metadata={"format": "pt"})
        temp.replace(output)
        marker.write_text("bfloat16\n")
        del tensors, converted
        downloaded.unlink()
    (target / "READY").write_text(f"{repo}; {VIDEO_REVISION}; bfloat16\n")
    print("Video model installed:", target, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "kind",
        choices=[
            "image",
            "fast-image",
            "video",
            "wan-video",
            "vace-video",
            "mlx-image",
            "speech",
            "all",
            "status",
        ],
    )
    parser.add_argument(
        "--root", type=Path, default=Path(os.environ.get("STORY_STUDIO_HOME", ".studio")) / "models"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Plan a Wan/VACE download without fetching weights"
    )
    args = parser.parse_args()
    if args.dry_run and args.kind not in ("wan-video", "vace-video"):
        parser.error("--dry-run is supported for wan-video and vace-video")
    args.root.mkdir(parents=True, exist_ok=True)
    if args.kind == "status":
        print(
            json.dumps(
                {
                    "image": (args.root / "flux2-klein-4b/READY").exists(),
                    "mlx_image": (args.root / "flux2-klein-4b-mlx/READY").exists(),
                    "speech": (args.root / "kokoro/READY").exists(),
                    "fast_image": (args.root / "sd-turbo/READY").exists(),
                    "video": (args.root / "ltx-video/READY").exists(),
                    "wan_video": (args.root / "wan-2.2-ti2v-5b/READY").exists(),
                    "vace_video": (args.root / "wan-2.1-vace-1.3b/READY").exists(),
                    "free_gib": round(shutil.disk_usage(args.root).free / 1024**3, 1),
                }
            )
        )
    else:
        if args.kind in ("wan-video", "vace-video"):
            from storycompiler.resources import inference_lease
            from storycompiler.video_install import install_video as install_wan_video
            from storycompiler.video_models import VACE, WAN

            with inference_lease():
                install_wan_video(args.root, WAN if args.kind == "wan-video" else VACE, args.dry_run)
        if args.kind == "fast-image":
            install_fast_image(args.root)
        if args.kind == "mlx-image" or (args.kind == "all" and platform.system() == "Darwin"):
            from install_extras import install_mlx

            install_mlx(args.root)
        if args.kind == "speech" or args.kind == "all":
            from install_extras import install_speech

            install_speech(args.root)
        if args.kind == "image" or (args.kind == "all" and platform.system() != "Darwin"):
            install_image(args.root)
        if args.kind in ("video", "all"):
            install_video(args.root)
