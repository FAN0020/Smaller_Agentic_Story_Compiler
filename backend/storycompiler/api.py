"""Loopback application API. Mutations validate state before entering the durable queue."""

import importlib.util
import os
import shutil
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .contracts import BibleDraft, PlanRevision
from .domain import STYLES, Contract, CreativeBrief
from .jobs import JobWorker
from .language_models import LANGUAGE_PROVIDERS, LLM_MODEL_OPTIONS, discover_language_models
from .planning import Planner
from .production import Producer, assert_production_approved, file_hash
from .resources import ResourceError, check_capacity, snapshot
from .review import revise_plan
from .settings import LOCAL_IMAGE_MODELS, ModelSettings, SettingsStore
from .speech import KOKORO_VOICES
from .storage import Repository
from .validation import assert_references_frozen
from .video_models import LOCAL_VIDEO_MODELS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = PROJECT_ROOT / "docs/stories"


class NewProject(Contract):
    title: str = Field(default="Untitled story", max_length=200)
    source: str = Field(min_length=1, max_length=2_000_000)
    brief: CreativeBrief = Field(default_factory=CreativeBrief)

    @field_validator("source")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Upload or paste a story first")
        if "\x00" in value:
            raise ValueError("Upload a UTF-8 text file, not a binary document")
        return value


class JobRequest(Contract):
    kind: Literal["analyze", "episodes", "references", "direct", "audio", "speech", "render"]
    numbers: list[int] = Field(default_factory=list)
    only: str | None = None
    prompt: str | None = Field(default=None, max_length=10000)

    @field_validator("prompt")
    @classmethod
    def nonempty_prompt(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Enter an image prompt before regenerating")
        return value


class Approval(Contract):
    kind: Literal["bible", "references", "plans", "video"]
    numbers: list[int] = Field(default_factory=list)
    accept_findings: bool = False


class ReferenceRevision(Contract):
    only: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=10000)

    @field_validator("prompt")
    @classmethod
    def nonempty_prompt(cls, value):
        return JobRequest.nonempty_prompt(value)


def create_app(root: Path | None = None, start_worker=True):
    root = Path(root or os.environ.get("STORY_STUDIO_HOME", PROJECT_ROOT / ".studio"))
    repo = Repository(root)
    settings = SettingsStore(root)
    worker = JobWorker(repo, settings)
    lock = threading.RLock()

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
        yield
        if start_worker:
            worker.close()

    app = FastAPI(title="Story Compiler Studio", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", "[::1]"])
    app.state.repo = repo
    app.state.settings = settings

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1", "::1", "testserver"):
                return JSONResponse({"detail": "Only this local studio can submit changes"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "Not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    def idle(id):
        if any(j["status"] in ("queued", "running") for j in repo.jobs(id)):
            raise ValueError("Wait for the active job or cancel it before changing this project")

    def validate_numbers(p, numbers):
        valid = {e["number"] for e in p["episodes"]}
        if not numbers or not set(numbers) <= valid or len(numbers) != len(set(numbers)):
            raise ValueError("Choose valid, distinct episode numbers")

    @app.get("/api/catalog")
    def catalog():
        samples = [
            {
                "file": p.name,
                "title": p.read_text(encoding="utf-8-sig").splitlines()[0],
                "bytes": p.stat().st_size,
            }
            for p in sorted(SAMPLES.glob("*.txt"))
        ]
        return {
            "styles": [s.model_dump() for s in STYLES],
            "samples": samples,
            "models": {
                "llm": LLM_MODEL_OPTIONS,
                "language_providers": LANGUAGE_PROVIDERS,
                "image": [
                    {
                        "id": "mlx-community/flux2-klein-4b-4bit",
                        "label": "FLUX.2 Klein · 4-bit Apple Silicon",
                        "tier": "balanced",
                        "description": "Native multi-reference image composition with a smaller Apple Silicon memory footprint.",
                    },
                    {
                        "id": "black-forest-labs/FLUX.2-klein-4B",
                        "label": "FLUX.2 Klein · full precision",
                        "tier": "quality",
                        "description": "Full precision multi-reference composition; requires at least 32 GB RAM.",
                    },
                    {
                        "id": "stabilityai/sd-turbo",
                        "label": "SD-Turbo",
                        "tier": "preview",
                        "description": "Fast reference studies only; not supported for multi-reference production scenes.",
                    },
                    {
                        "id": "gpt-image-1",
                        "label": "OpenAI Images",
                        "tier": "hosted",
                        "description": "Hosted image generation; requires an OpenAI API key.",
                    },
                ],
                "voices": KOKORO_VOICES,
                "video": [
                    *[
                        {
                            "id": model,
                            "label": p["label"],
                            "tier": "local",
                            "description": p["description"],
                            "recommended_steps": 20 if p["installer"] == "video" else 50,
                            "install_command": f".venv/bin/python scripts/setup_models.py {p['installer']}",
                        }
                        for model, p in LOCAL_VIDEO_MODELS.items()
                    ],
                    {
                        "id": "sora-2",
                        "label": "Sora 2",
                        "tier": "hosted",
                        "description": "Hosted video generation; requires an OpenAI API key and account access.",
                    },
                    {
                        "id": "sora-2-pro",
                        "label": "Sora 2 Pro",
                        "tier": "quality",
                        "description": "Higher-quality hosted video option; requires an OpenAI API key and account access.",
                    },
                ],
            },
        }

    @app.get("/api/samples/{filename}")
    def sample(filename: str):
        names = {p.name for p in SAMPLES.glob("*.txt")}
        if filename not in names:
            raise HTTPException(404, "Sample not found")
        return {"source": (SAMPLES / filename).read_text(encoding="utf-8-sig")}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "worker_alive": worker.thread.is_alive() if start_worker else False}

    @app.get("/api/settings")
    def get_settings():
        return settings.public()

    @app.put("/api/settings")
    def put_settings(changes: dict):
        return settings.update(changes)

    @app.post("/api/providers/language-models")
    def language_models(changes: dict):
        allowed = {"llm_provider", "llm_endpoint", "llm_model"}
        if not set(changes) <= allowed:
            raise ValueError("Discovery accepts only the language provider, endpoint and model")
        configured = ModelSettings.model_validate({**settings.get().model_dump(), **changes})
        return discover_language_models(configured, settings)

    @app.get("/api/providers/status")
    def provider_status():
        configured = settings.get()
        local = {
            "image": (
                root / "models" / LOCAL_IMAGE_MODELS.get(configured.image_model, "unavailable") / "READY"
            ).exists(),
            "video": configured.video_provider == "local"
            and (root / "models" / LOCAL_VIDEO_MODELS[configured.video_model]["folder"] / "READY").exists(),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "system_voice": bool(shutil.which("say")),
            "free_gib": round(shutil.disk_usage(root).free / 1024**3, 1),
        }
        local["speech"] = (root / "models/kokoro/READY").exists() and importlib.util.find_spec(
            "kokoro_onnx"
        ) is not None
        local["voices"] = KOKORO_VOICES
        local["resources"] = snapshot(root).record()
        local["image_options"] = []
        local["video_options"] = []
        for model, profile in LOCAL_VIDEO_MODELS.items():
            reason = ""
            try:
                check_capacity(model, snapshot(root))
            except ResourceError as e:
                reason = str(e)
            local["video_options"].append(
                {
                    "id": model,
                    "installed": (root / "models" / profile["folder"] / "READY").exists(),
                    "resource_warning": reason,
                }
            )
        for model, folder in LOCAL_IMAGE_MODELS.items():
            reason = ""
            try:
                check_capacity(model, snapshot(root))
            except ResourceError as e:
                reason = str(e)
            local["image_options"].append(
                {
                    "id": model,
                    "installed": (root / "models" / folder / "READY").exists(),
                    "resource_warning": reason,
                }
            )
        llm = discover_language_models(configured, settings)
        return {"local": local, "llm": llm, "credentials": settings.public()["credentials"]}

    @app.post("/api/projects", status_code=201)
    def create_project(body: NewProject):
        return repo.create_project(body.title, body.source, body.brief.model_dump())

    @app.get("/api/projects")
    def projects():
        return [
            {k: p[k] for k in ("id", "title", "brief", "status", "updated")}
            | {"episode_count": len(p["episodes"])}
            for p in repo.list_projects()
        ]

    @app.get("/api/projects/{id}")
    def project(id: str):
        return {**repo.get_project(id), "jobs": repo.jobs(id)}

    @app.get("/api/projects/{id}/export")
    def export(id: str):
        return JSONResponse(
            repo.get_project(id),
            headers={"Content-Disposition": f'attachment; filename="story-{id[:8]}.json"'},
        )

    @app.post("/api/projects/{id}/revision", status_code=201)
    def revision(id: str, brief: CreativeBrief):
        p = repo.get_project(id)
        new = repo.create_project(p["title"] + " · revision", p["source"], brief.model_dump())
        new["parent_project"] = id
        repo.save_project(new)
        return new

    @app.put("/api/projects/{id}/bible")
    def edit_bible(id: str, bible: BibleDraft):
        with lock:
            idle(id)
            p = repo.get_project(id)
            if p["bible_hash"]:
                raise ValueError("This bible is frozen; create a revision")
            if not p["bible"]:
                raise ValueError("Analyze the story first")
            p["bible"].update(bible.model_dump())
            repo.save_project(p)
            return p

    @app.post("/api/projects/{id}/reference-revision", status_code=201)
    def reference_revision(id: str, body: ReferenceRevision):
        with lock:
            idle(id)
            p = repo.get_project(id)
            Planner.assert_frozen(p)
            entity_ids = {e["id"] for kind in ("characters", "locations") for e in p["bible"][kind]}
            if body.only not in entity_ids or body.only not in p["references"]:
                raise ValueError("Choose an existing character or location reference in this story")
            directory = repo.artifact_dir(id).resolve()
            for reference in p["references"].values():
                path = (directory / reference["file"]).resolve()
                if path.parent != directory or not path.is_file():
                    raise ValueError("A reference image is missing; restore it before creating a revision")
                if file_hash(path) != reference["sha256"]:
                    raise ValueError(
                        "A reference image changed on disk; restore it before creating a revision"
                    )
            payload = {**body.model_dump(), "model_settings": settings.get().model_dump()}
            new = repo.create_reference_revision(p, payload)
            return {**new, "jobs": repo.jobs(new["id"])}

    @app.post("/api/projects/{id}/jobs", status_code=202)
    def submit_job(id: str, body: JobRequest):
        with lock:
            p = repo.get_project(id)
            if body.kind in ("episodes", "references", "direct", "audio", "speech", "render"):
                Planner.assert_frozen(p)
            if body.prompt is not None and body.kind != "references":
                raise ValueError("Image prompts can only be supplied when generating references")
            if body.kind == "references":
                entity_ids = {e["id"] for kind in ("characters", "locations") for e in p["bible"][kind]}
                if body.only and body.only not in entity_ids:
                    raise ValueError("Choose a character or location in this story")
                if body.prompt is not None and not body.only:
                    raise ValueError("Choose one character or location for a custom image prompt")
                if p["episodes"]:
                    raise ValueError(
                        "References are locked by episode plans; create a revision to redesign them"
                    )
            if body.kind in ("direct", "audio", "speech", "render"):
                validate_numbers(p, body.numbers)
            if body.kind == "episodes":
                assert_references_frozen(p)
            if body.kind in ("speech", "render"):
                assert_production_approved(p, body.numbers)
            if body.kind == "analyze" and p["bible_hash"]:
                raise ValueError("Create a revision to reanalyze a frozen story")
            payload = {**body.model_dump(exclude={"kind"}), "model_settings": settings.get().model_dump()}
            return repo.enqueue(id, body.kind, payload)

    @app.put("/api/projects/{id}/plans/{number}")
    def edit_plan(id: str, number: int, revision: PlanRevision):
        with lock:
            idle(id)
            p = repo.get_project(id)
            validate_numbers(p, [number])
            return revise_plan(repo, p, number, revision)

    @app.post("/api/projects/{id}/productions/{number}/new-take")
    def new_take(id: str, number: int):
        with lock:
            idle(id)
            p = repo.get_project(id)
            validate_numbers(p, [number])
            prior = p["productions"].pop(str(number), None)
            if prior is None:
                raise ValueError("No existing take to archive")
            p.setdefault("production_takes", {}).setdefault(str(number), []).append(prior)
            p["audit"].append({"action": "new_production_take", "episode": number, "at": time.time()})
            p["status"] = "plan_review"
            repo.save_project(p)
            for job in repo.jobs(id):
                if (
                    job["kind"] == "render"
                    and number in job["payload"].get("numbers", [])
                    and job["status"] in ("cancelled", "interrupted", "failed", "review_required")
                ):
                    repo.update_job(
                        job["id"],
                        status="superseded",
                        message="Previous take archived; produce a new take with current settings",
                    )
            return p

    @app.post("/api/projects/{id}/approve")
    def approve(id: str, body: Approval):
        with lock:
            idle(id)
            p = repo.get_project(id)
            producer = Producer(repo, settings, lambda *_: None, lambda: False)
            if body.kind == "bible":
                if not p["bible_hash"]:
                    Planner(repo, None, lambda *_: None).freeze(p)
            elif body.kind == "references":
                producer.approve_references(p)
            elif body.kind == "plans":
                validate_numbers(p, body.numbers)
                producer.approve_plans(p, body.numbers, body.accept_findings)
            else:
                validate_numbers(p, body.numbers)
                for number in body.numbers:
                    output = p["productions"].get(str(number))
                    if not output or not output.get("file"):
                        raise ValueError("Render the episode before reviewing it")
                    output["visual_status"] = "human_approved"
                    output["status"] = "approved"
                repo.save_project(p)
            return p

    @app.post("/api/jobs/{id}/cancel")
    def cancel_job(id: str):
        with lock:
            job = repo.get_job(id)
            changes = {"cancel": 1}
            if job["status"] == "queued":
                changes["status"] = "cancelled"
            repo.update_job(id, **changes)
            return repo.get_job(id)

    @app.post("/api/jobs/{id}/resume")
    def resume_job(id: str):
        with lock:
            job = repo.get_job(id)
            if job["status"] not in ("failed", "interrupted", "cancelled", "review_required"):
                raise ValueError("This job does not need resuming")
            idle(job["project_id"])
            repo.update_job(id, status="queued", cancel=0, error=None, message="Resuming saved work")
            return repo.get_job(id)

    @app.post("/api/jobs/{id}/retry-with-settings")
    def retry_with_settings(id: str):
        with lock:
            return repo.retry_language_job(id, settings.get().model_dump())

    @app.get("/api/artifacts/{id}/{filename}")
    def artifact(id: str, filename: str):
        repo.get_project(id)
        directory = repo.artifact_dir(id).resolve()
        path = (directory / filename).resolve()
        if (
            path.parent != directory
            or path.suffix not in (".mp4", ".png", ".jpg", ".vtt", ".wav")
            or not path.is_file()
        ):
            raise HTTPException(404, "Artifact not found")
        return FileResponse(path, media_type="text/vtt" if path.suffix == ".vtt" else None)

    dist = PROJECT_ROOT / "web/dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="studio")
    return app


app = create_app()
