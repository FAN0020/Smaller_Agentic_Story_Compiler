"""Pinned, resumable checkpoint downloads with disk admission and shared weights."""

import hashlib
import json
import os
import shutil
from pathlib import Path

from filelock import FileLock

from .video_models import LTX, video_profile

GIB = 1024**3
DISK_RESERVE = 10 * GIB


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_download_bytes(target, files, shared):
    return sum(
        f["size"]
        for f in files
        if not ((target / f["name"]).is_file() and (target / f["name"]).stat().st_size == f["size"])
        and f.get("sha256") not in shared
    )


def install_video(root, model, dry_run=False):
    # Avoid an additional Xet chunk cache competing with checkpoint disk space.
    os.environ.setdefault("HF_XET_CHUNK_CACHE_SIZE_BYTES", "0")
    from huggingface_hub import HfApi, hf_hub_download

    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    profile = video_profile(model)
    if model == LTX:
        raise ValueError("Use setup_models.py video for the existing LTX conversion installer")
    target = root / profile["folder"]
    with FileLock(str(root / ".video-install.lock"), timeout=0):
        info = HfApi().model_info(model, revision=profile["revision"], files_metadata=True, token=False)
        files = []
        for f in info.siblings:
            if f.rfilename in ("model_index.json", "README.md", "LICENSE", "LICENSE.txt", "LICENSE.md") or (
                f.rfilename.startswith(("scheduler/", "tokenizer/", "text_encoder/", "transformer/", "vae/"))
                and f.rfilename.endswith((".json", ".txt", ".model", ".safetensors"))
            ):
                if f.size is None:
                    raise ValueError("Provider did not report a file size; cannot safely admit this download")
                files.append({"name": f.rfilename, "size": f.size, "sha256": f.lfs.sha256 if f.lfs else None})
        if not all(
            any(f["name"].startswith(part + "/") and f["name"].endswith(".safetensors") for f in files)
            for part in ("text_encoder", "transformer", "vae")
        ):
            raise ValueError("Checkpoint metadata is incomplete")

        shared = {}
        for manifest in root.glob("*/installation.json"):
            installed = json.loads(manifest.read_text())
            if not (manifest.parent / "READY").exists():
                continue
            for f in installed["files"]:
                path = manifest.parent / f["name"]
                if (
                    f.get("sha256")
                    and path.is_file()
                    and path.stat().st_size == f["size"]
                    and path.stat().st_dev == root.stat().st_dev
                ):
                    shared[f["sha256"]] = path
        download_bytes = required_download_bytes(target, files, shared)
        free = shutil.disk_usage(root).free
        plan = {
            "model": model,
            "revision": profile["revision"],
            "target": str(target),
            "download_gib": round(download_bytes / GIB, 2),
            "required_free_gib": round((download_bytes + DISK_RESERVE) / GIB, 2),
            "free_gib": round(free / GIB, 2),
            "disk_ready": free >= download_bytes + DISK_RESERVE,
        }
        print(json.dumps(plan, indent=2), flush=True)
        if dry_run:
            return plan
        if not plan["disk_ready"]:
            raise RuntimeError(
                f"Need {plan['required_free_gib']} GiB free before downloading {profile['label']}; {plan['free_gib']} GiB available. Free space and rerun; nothing was downloaded."
            )

        target.mkdir(parents=True, exist_ok=True)
        (target / "READY").unlink(missing_ok=True)
        for f in files:
            output = target / f["name"]
            reusable = shared.get(f["sha256"])
            if not output.exists() and reusable:
                output.parent.mkdir(parents=True, exist_ok=True)
                os.link(reusable, output)
            else:
                if shutil.disk_usage(root).free < DISK_RESERVE + (0 if output.exists() else f["size"]):
                    raise RuntimeError(
                        "Disk headroom changed during download. Free space and rerun to resume."
                    )
                print("Downloading", f["name"], flush=True)
                hf_hub_download(model, f["name"], revision=profile["revision"], local_dir=target, token=False)
            if output.stat().st_size != f["size"] or (f["sha256"] and file_digest(output) != f["sha256"]):
                raise RuntimeError(
                    f"Checkpoint verification failed for {output}; installation remains incomplete"
                )
        (target / "installation.json").write_text(
            json.dumps({**plan, "license": "Apache-2.0", "files": files}, indent=2)
        )
        marker = target / "READY.tmp"
        marker.write_text(f"{model}; {profile['revision']}; official weights; inference not yet verified\n")
        marker.replace(target / "READY")
        print("Installed:", target, flush=True)
        return plan
