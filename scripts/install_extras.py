"""Pinned, opt-in compact local runtimes. Never loads model weights during installation."""

import hashlib
import platform
import shutil
import subprocess

import httpx

FLUX_MLX_REVISION = "860e87183ceb29e39627c0612ebd66d8ea66e68c"
SPEECH_FILES = {
    "kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}


def install_mlx(root):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("This MLX preset requires an Apple Silicon Mac")
    if shutil.disk_usage(root).free < 18 * 1024**3:
        raise ValueError("Need 18 GiB free disk for installation and system headroom")
    if not shutil.which("uv"):
        raise ValueError("Install uv first, then rerun mlx-image setup")
    runtime = root.parent / "runtimes/mflux"
    if not (runtime / "bin/python").exists():
        subprocess.run(["uv", "venv", str(runtime), "--python", "3.12"], check=True)
    subprocess.run(
        ["uv", "pip", "install", "--python", str(runtime / "bin/python"), "mflux==0.21.0"], check=True
    )
    from huggingface_hub import snapshot_download

    target = root / "flux2-klein-4b-mlx"
    snapshot_download(
        "mlx-community/flux2-klein-4b-4bit",
        revision=FLUX_MLX_REVISION,
        local_dir=target,
        ignore_patterns=[".DS_Store"],
        max_workers=2,
    )
    (target / "READY").write_text(f"mlx-community/flux2-klein-4b-4bit; {FLUX_MLX_REVISION}; mflux 0.21.0\n")


def install_speech(root):
    if shutil.disk_usage(root).free < 11 * 1024**3:
        raise ValueError("Keep 11 GiB free before installing speech weights")
    target = root / "kokoro"
    target.mkdir(parents=True, exist_ok=True)
    for name, digest in SPEECH_FILES.items():
        output = target / name
        if output.exists() and hashlib.sha256(output.read_bytes()).hexdigest() == digest:
            continue
        partial = output.with_suffix(".partial")
        with httpx.stream(
            "GET",
            "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/" + name,
            follow_redirects=True,
            timeout=180,
        ) as response:
            response.raise_for_status()
            with partial.open("wb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
        if hashlib.sha256(partial.read_bytes()).hexdigest() != digest:
            raise ValueError("Speech model checksum mismatch; download not published")
        partial.replace(output)
    (target / "READY").write_text("kokoro-onnx 0.6.1; model-files-v1.1; SHA256 verified\n")
    print("Speech weights ready. Install runtime with: uv sync --extra dev --extra local --extra speech")
