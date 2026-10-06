#!/usr/bin/env python3
"""Install official local checkpoints, converting float32 shards to bfloat16 once.

Only files inside the selected model directory are changed. Downloads are resumable.
Run outside active rendering: conversion and inference both need memory.
"""

import argparse
import json
import shutil
from pathlib import Path


def install_image(root):
    from huggingface_hub import snapshot_download

    target = root / "sd-turbo"
    snapshot_download(
        "stabilityai/sd-turbo",
        local_dir=target,
        allow_patterns=["*.json", "*.txt", "*.model", "*fp16.safetensors"],
    )
    (target / "READY").write_text("stabilityai/sd-turbo; fp16\n")
    print("Image model installed:", target, flush=True)


def install_video(root):
    import torch
    from huggingface_hub import HfApi, hf_hub_download
    from safetensors.torch import load_file, save_file

    repo = "Lightricks/LTX-Video-0.9.1"
    target = root / "ltx-video"
    target.mkdir(parents=True, exist_ok=True)
    files = HfApi().list_repo_files(repo)
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
            hf_hub_download(repo, name, local_dir=target)
            continue
        if shutil.disk_usage(root).free < 8 * 1024**3:
            raise RuntimeError("Need at least 8 GiB free for the next shard and conversion")
        print("Downloading and converting", name, flush=True)
        downloaded = Path(hf_hub_download(repo, name, local_dir=root / "downloads"))
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
    (target / "READY").write_text(repo + "; bfloat16\n")
    print("Video model installed:", target, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["image", "video", "all", "status"])
    parser.add_argument("--root", type=Path, default=Path(".studio/models"))
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    if args.kind == "status":
        print(
            json.dumps(
                {
                    "image": (args.root / "sd-turbo/READY").exists(),
                    "video": (args.root / "ltx-video/READY").exists(),
                    "free_gib": round(shutil.disk_usage(args.root).free / 1024**3, 1),
                }
            )
        )
    else:
        if args.kind in ("image", "all"):
            install_image(args.root)
        if args.kind in ("video", "all"):
            install_video(args.root)
