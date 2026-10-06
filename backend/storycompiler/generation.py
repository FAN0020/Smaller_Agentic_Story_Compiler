"""Image, motion and speech adapters. Local and paid paths never silently interchange."""

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil
from PIL import Image, ImageOps

from .providers import ProviderError
from .resources import GIB, ResourceError, check_capacity, inference_lease, runtime_violation, snapshot
from .settings import LOCAL_IMAGE_MODELS


class Cancelled(RuntimeError):
    pass


def partial_path(output):
    return output.with_name(output.stem + ".partial" + output.suffix)


def publish_bytes(output, data):
    partial = partial_path(output)
    partial.write_bytes(data)
    partial.replace(output)


class LocalGenerator:
    def __init__(self, root: Path, cancelled):
        self.root = Path(root).resolve()
        self.cancelled = cancelled

    def _run(self, kind, prompt, output, seed, **options):
        with inference_lease():
            return self._run_locked(kind, prompt, output, seed, **options)

    def _run_locked(self, kind, prompt, output, seed, **options):
        model_id = options.get("model_id", "Lightricks/LTX-Video-0.9.1")
        model = LOCAL_IMAGE_MODELS[options["model_id"]] if kind == "image" else "ltx-video"
        if not (self.root / "models" / model / "READY").exists():
            raise ValueError(
                f"Local {kind} model is not installed. Run .venv/bin/python scripts/setup_models.py {kind}"
            )
        initial = snapshot(self.root)
        budget = check_capacity(model_id, initial)
        output = Path(output).resolve()
        partial = partial_path(output)
        request = output.with_suffix(".request.json")
        request.write_text(
            json.dumps(
                {
                    "kind": kind,
                    "prompt": prompt,
                    "output": str(partial),
                    "models": str(self.root / "models"),
                    "seed": seed,
                    "memory_limit_gib": min(budget * 1.25, initial.available - 2),
                    "resource_snapshot": initial.record(),
                    **options,
                }
            )
        )
        log = output.with_suffix(".inference.log")
        env = {
            **os.environ,
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "PYTORCH_MPS_HIGH_WATERMARK_RATIO": "1.0",
            "PYTORCH_MPS_LOW_WATERMARK_RATIO": "0.8",
        }
        with log.open("w") as stream:
            proc = subprocess.Popen(
                [sys.executable, "-m", "storycompiler.local_worker", str(request)],
                stdout=stream,
                stderr=stream,
                env=env,
            )
            started = time.monotonic()
            while proc.poll() is None:
                current = snapshot(self.root)
                try:
                    rss = psutil.Process(proc.pid).memory_info().rss / GIB
                except psutil.NoSuchProcess:
                    continue
                reason = runtime_violation(initial, current, rss, min(budget * 1.25, initial.available - 2))
                if reason or self.cancelled() or time.monotonic() - started > 2400:
                    proc.terminate()
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    if reason:
                        raise ResourceError(
                            "Local generation stopped safely: " + reason + ". Saved artifacts are retained."
                        )
                    if self.cancelled():
                        raise Cancelled("Production cancelled; completed clips are saved")
                    raise ProviderError("Local generation exceeded 40 minutes; reduce model settings")
                time.sleep(0.5)
        if proc.returncode or not partial.exists():
            # Local logs contain no credentials; preserve detailed diagnostics as an artifact.
            tail = log.read_text()[-800:]
            raise ProviderError("Local generation failed. " + tail)
        partial.replace(output)
        return output

    def image(
        self,
        prompt,
        output,
        seed,
        references=None,
        model="black-forest-labs/FLUX.2-klein-4B",
        size=(512, 512),
    ):
        if model not in LOCAL_IMAGE_MODELS:
            raise ValueError("Choose an installed supported local image model")
        if references and model == "stabilityai/sd-turbo":
            raise ValueError(
                "SD-Turbo does not support multi-reference scene composition. Choose FLUX.2 Klein or an image API."
            )
        return self._run(
            "image",
            prompt,
            output,
            seed,
            model_id=model,
            references=[str(p) for p in references or []],
            size=list(size),
        )

    def video(self, prompt, reference, output, seed, steps, portrait=False):
        return self._run(
            "video",
            prompt,
            output,
            seed,
            reference=str(reference),
            steps=steps,
            size=[288, 512] if portrait else [512, 288],
        )


class OpenAIGenerator:
    def __init__(self, settings, cancelled):
        self.settings = settings
        self.cancelled = cancelled
        key = settings.secret("openai")
        if not key:
            raise ValueError("Add your OpenAI API key in Model settings")
        self.client = httpx.Client(
            base_url="https://api.openai.com/v1", headers={"Authorization": "Bearer " + key}, timeout=180
        )

    def request(self, method, path, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.RequestError as e:
            raise ProviderError(
                "Provider connection failed. A submission may have been accepted; inspect the saved receipt before retrying."
            ) from e
        if response.is_error:
            raise ProviderError(
                f"OpenAI returned HTTP {response.status_code}; check account access, model and content restrictions"
            )
        return response

    def image(self, prompt, output, model="gpt-image-1", references=None, size="1024x1024"):
        if references:
            files = [("image[]", (p.name, p.read_bytes(), "image/png")) for p in references]
            response = self.request(
                "POST",
                "/images/edits",
                data={"model": model, "prompt": prompt, "size": size},
                files=files,
            )
        else:
            response = self.request(
                "POST",
                "/images/generations",
                json={"model": model, "prompt": prompt, "size": size, "n": 1},
            )
        try:
            data = response.json()["data"][0]["b64_json"]
            partial = partial_path(output)
            partial.write_bytes(base64.b64decode(data, validate=True))
            Image.open(partial).verify()
            partial.replace(output)
        except (KeyError, ValueError) as e:
            raise ProviderError("Image provider returned an invalid image payload") from e
        return output

    def video(self, prompt, reference, output, model, receipt, save_receipt, portrait=False):
        if receipt.get("submission_pending") and not receipt.get("provider_id"):
            raise ProviderError(
                "A prior video submission has an unknown outcome. Check your provider account before explicitly clearing this attempt."
            )
        if not receipt.get("provider_id"):
            prepared = output.with_suffix(".reference.png")
            size = (720, 1280) if portrait else (1280, 720)
            ImageOps.fit(Image.open(reference).convert("RGB"), size).save(prepared)
            receipt["submission_pending"] = True
            save_receipt()
            response = self.request(
                "POST",
                "/videos",
                data={"model": model, "prompt": prompt, "seconds": "4", "size": f"{size[0]}x{size[1]}"},
                files={"input_reference": ("reference.png", prepared.read_bytes(), "image/png")},
            )
            receipt["provider_id"] = response.json()["id"]
            receipt["submission_pending"] = False
            save_receipt()
        started = time.monotonic()
        while time.monotonic() - started < 2400:
            if self.cancelled():
                raise Cancelled("Stopped polling. Resume to retrieve the existing provider job.")
            data = self.request("GET", "/videos/" + receipt["provider_id"]).json()
            if data["status"] == "completed":
                publish_bytes(
                    output, self.request("GET", "/videos/" + receipt["provider_id"] + "/content").content
                )
                return output
            if data["status"] == "failed":
                raise ProviderError(
                    "Video provider rejected or failed this clip. Review content and provider account."
                )
            time.sleep(5)
        raise ProviderError("Video is still processing. Resume to poll the saved provider job.")

    def speech(self, text, output, voice="alloy"):
        response = self.request(
            "POST",
            "/audio/speech",
            json={"model": "gpt-4o-mini-tts", "input": text, "voice": voice, "response_format": "wav"},
        )
        publish_bytes(output, response.content)

    def close(self):
        self.client.close()
