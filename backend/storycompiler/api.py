"""Loopback application API. Mutations validate state before entering the durable queue."""

import os
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .contracts import BibleDraft
from .domain import STYLES, Contract, CreativeBrief
from .jobs import JobWorker
from .planning import Planner
from .production import Producer, assert_production_approved
from .settings import SettingsStore
from .storage import Repository

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
    kind: Literal["analyze", "episodes", "references", "direct", "render"]
    numbers: list[int] = Field(default_factory=list)
    only: str | None = None


class Approval(Contract):
    kind: Literal["bible", "references", "plans", "video"]
    numbers: list[int] = Field(default_factory=list)
    accept_findings: bool = False


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
                "llm": ["qwen3.5:4b", "qwen3.5:9b", "gemma3:4b"],
                "image": ["stabilityai/sd-turbo", "gpt-image-1"],
                "video": ["Lightricks/LTX-Video-0.9.1", "sora-2", "sora-2-pro"],
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

    @app.get("/api/providers/status")
    def provider_status():
        configured = settings.get()
        local = {
            "image": (root / "models/sd-turbo/READY").exists(),
            "video": (root / "models/ltx-video/READY").exists(),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "system_voice": bool(shutil.which("say")),
            "free_gib": round(shutil.disk_usage(root).free / 1024**3, 1),
        }
        models = []
        try:
            if configured.llm_provider == "ollama":
                response = httpx.get(configured.llm_endpoint + "/api/tags", timeout=3)
                response.raise_for_status()
                models = [m["name"] for m in response.json()["models"]]
                llm = {"available": configured.llm_model in models, "models": models}
            else:
                llm = {"available": bool(settings.secret(configured.llm_provider)), "verified": False}
        except (httpx.HTTPError, ValueError, KeyError):
            llm = {"available": False, "models": []}
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

    @app.post("/api/projects/{id}/jobs", status_code=202)
    def submit_job(id: str, body: JobRequest):
        with lock:
            p = repo.get_project(id)
            if body.kind in ("episodes", "references", "direct", "render"):
                Planner.assert_frozen(p)
            if body.kind in ("direct", "render"):
                validate_numbers(p, body.numbers)
            if body.kind == "render":
                assert_production_approved(p, body.numbers)
            if body.kind == "analyze" and p["bible_hash"]:
                raise ValueError("Create a revision to reanalyze a frozen story")
            return repo.enqueue(id, body.kind, body.model_dump(exclude={"kind"}))

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
