"""Conservative admission and runtime limits for a shared local machine.

These limits protect headroom; they cannot promise immunity from an OS/driver panic.
All quantities are GiB. Never disable the framework's allocator limits.
"""

import shutil
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil
from filelock import FileLock, Timeout

from .video_models import LOCAL_VIDEO_MODELS

GIB = 1024**3
RESERVE = 3
WORKING_SETS = {
    "hexgrad/Kokoro-82M": 1,
    "mlx-community/flux2-klein-4b-4bit": 5.8,
    "black-forest-labs/FLUX.2-klein-4B": 20,
    "stabilityai/sd-turbo": 4,
    **{model: profile["memory_gib"] for model, profile in LOCAL_VIDEO_MODELS.items()},
}


class ResourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    total: float
    available: float
    disk_free: float
    swap_used: float

    def record(self):
        return {key: round(value, 2) for key, value in asdict(self).items()}


def snapshot(path):
    memory = psutil.virtual_memory()
    return Snapshot(
        memory.total / GIB,
        memory.available / GIB,
        shutil.disk_usage(path).free / GIB,
        psutil.swap_memory().used / GIB,
    )


def check_capacity(model, state):
    required = WORKING_SETS[model]
    if model == "black-forest-labs/FLUX.2-klein-4B" and state.total < 31:
        raise ResourceError(
            "Full-precision FLUX needs at least 32 GB RAM. Choose the quantized FLUX model or an image API."
        )
    if state.disk_free < 10:
        raise ResourceError(
            "Local generation stopped: keep at least 10 GiB of disk space free for system swap and artifacts."
        )
    if state.available < required + RESERVE:
        raise ResourceError(
            f"Local generation needs {required + RESERVE:.1f} GiB available memory including system headroom; "
            f"{state.available:.1f} GiB available. Close memory-heavy apps or choose a smaller model."
        )
    return required


@contextmanager
def inference_lease(path=None):
    """OS-backed lock survives crashes without a stale lock blocking recovery."""
    path = path or Path.home() / ".cache/storycompiler/local-inference.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(path)
    try:
        lock.acquire(timeout=0)
    except Timeout as e:
        raise ResourceError(
            "Local inference is already running in another Studio process. Try again after it finishes."
        ) from e
    try:
        yield
    finally:
        lock.release()


def runtime_violation(initial, current, rss, limit):
    if current.disk_free < 8:
        return "disk headroom fell below 8 GiB"
    if current.available < 2:
        return "available memory fell below 2 GiB"
    if current.swap_used - initial.swap_used > 2:
        return "swap grew by more than 2 GiB during inference"
    if rss > limit:
        return f"worker memory exceeded its {limit:.1f} GiB limit"
    return None


def wait_for_headroom(required, initial, refresh, cancelled=lambda: False, timeout=30):
    """Allow recently unloaded models to release memory before refusing admission."""
    state = initial
    deadline = time.monotonic() + timeout
    while state.available < required and state.total >= required and state.disk_free >= 10:
        if cancelled() or time.monotonic() >= deadline:
            break
        time.sleep(0.5)
        state = refresh()
    return state
