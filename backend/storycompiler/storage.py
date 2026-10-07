"""SQLite snapshots and durable job queue. Each write is an explicit transaction."""

import json
import shutil
import sqlite3
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import uuid4


class Repository:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "studio.sqlite3"
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, version INTEGER, updated REAL, data TEXT);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, payload TEXT,
                  status TEXT, progress REAL, message TEXT, error TEXT, created REAL, updated REAL,
                  cancel INTEGER DEFAULT 0, FOREIGN KEY(project_id) REFERENCES projects(id));
                CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, created);
            """)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            with c:
                yield c
        finally:
            c.close()

    def create_project(self, title, source, brief):
        now = time.time()
        p = {
            "id": uuid4().hex,
            "title": title,
            "source": source,
            "brief": brief,
            "status": "draft",
            "version": 1,
            "created": now,
            "updated": now,
            "analyses": {},
            "events": [],
            "bible": None,
            "bible_hash": None,
            "episodes": [],
            "references": {},
            "references_hash": None,
            "plans": {},
            "productions": {},
            "reviews": {},
            "audit": [],
        }
        with self.connect() as c:
            c.execute("INSERT INTO projects VALUES(?,?,?,?)", (p["id"], 1, now, json.dumps(p)))
        return p

    def get_project(self, id):
        with self.connect() as c:
            row = c.execute("SELECT data FROM projects WHERE id=?", (id,)).fetchone()
        if not row:
            raise KeyError("Project not found")
        return json.loads(row["data"])

    def create_reference_revision(self, parent, payload):
        """Publish a copied visual workspace and its first job together, after copying artifacts."""
        now = time.time()
        new = {
            key: deepcopy(parent[key])
            for key in ("source", "brief", "analyses", "events", "bible", "bible_hash", "references")
        }
        for key in ("bible_sections_done", "estimated_episode_count"):
            if key in parent:
                new[key] = parent[key]
        new.update(
            id=uuid4().hex,
            title=parent["title"] + " · visual revision",
            parent_project=parent["id"],
            status="references_review",
            version=1,
            created=now,
            updated=now,
            episodes=[],
            plans={},
            productions={},
            reviews={},
            references_hash=None,
            audit=[
                {
                    "action": "reference_revision",
                    "parent_project": parent["id"],
                    "entity": payload["only"],
                    "at": now,
                }
            ],
        )
        source = self.artifact_dir(parent["id"])
        destination = self.artifact_dir(new["id"])
        try:
            for reference in new["references"].values():
                shutil.copy2(source / reference["file"], destination / reference["file"])
                reference["approved"] = False
            with self.connect() as c:
                c.execute("INSERT INTO projects VALUES(?,?,?,?)", (new["id"], 1, now, json.dumps(new)))
                self._insert_job(c, new["id"], "references", payload)
        except Exception:
            shutil.rmtree(destination)
            raise
        return new

    def list_projects(self):
        with self.connect() as c:
            rows = c.execute("SELECT data FROM projects ORDER BY updated DESC").fetchall()
        return [json.loads(r["data"]) for r in rows]

    def save_project(self, p):
        version = p["version"]
        updated = {**p, "version": version + 1, "updated": time.time()}
        with self.connect() as c:
            result = c.execute(
                "UPDATE projects SET version=?,updated=?,data=? WHERE id=? AND version=?",
                (version + 1, updated["updated"], json.dumps(updated), p["id"], version),
            )
            if result.rowcount != 1:
                raise ValueError("Project changed; reload before saving")
        p.update(updated)

    def enqueue(self, project_id, kind, payload):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            active = c.execute(
                "SELECT * FROM jobs WHERE project_id=? AND status IN ('queued','running')", (project_id,)
            ).fetchone()
            if active:
                if active["kind"] == kind and json.loads(active["payload"]) == payload:
                    return self._job(active)
                raise ValueError("This project already has an active job")
            id = self._insert_job(c, project_id, kind, payload)
        return self.get_job(id)

    def retry_language_job(self, id, settings):
        """Keep the original snapshot; atomically replace a stopped planning job."""
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            if row is None:
                raise KeyError("Job not found")
            job = self._job(row)
            if job["kind"] not in ("analyze", "episodes", "direct", "audio"):
                raise ValueError("Only language planning jobs can retry with a new language model")
            if job["status"] not in ("failed", "interrupted", "cancelled", "review_required"):
                raise ValueError("This job does not need retrying")
            if c.execute(
                "SELECT 1 FROM jobs WHERE project_id=? AND status IN ('queued','running')",
                (job["project_id"],),
            ).fetchone():
                raise ValueError("This project already has an active job")
            payload = deepcopy(job["payload"])
            payload["retry_of_job"] = id
            previous = payload.get("model_settings", settings)
            payload["model_settings"] = previous | {k: v for k, v in settings.items() if k.startswith("llm_")}
            new_id = self._insert_job(c, job["project_id"], job["kind"], payload)
            c.execute(
                "UPDATE jobs SET status='superseded',message=?,updated=? WHERE id=?",
                ("Retried with selected language settings", time.time(), id),
            )
        return self.get_job(new_id)

    @staticmethod
    def _insert_job(c, project_id, kind, payload):
        now = time.time()
        id = uuid4().hex
        c.execute(
            "INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (id, project_id, kind, json.dumps(payload), "queued", 0, "Queued", None, now, now, 0),
        )
        return id

    @staticmethod
    def _job(row):
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        return data

    def get_job(self, id):
        with self.connect() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
        if not row:
            raise KeyError("Job not found")
        return self._job(row)

    def jobs(self, project_id):
        with self.connect() as c:
            rows = c.execute(
                "SELECT * FROM jobs WHERE project_id=? ORDER BY created DESC", (project_id,)
            ).fetchall()
        return [self._job(r) for r in rows]

    def next_job(self):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            c.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), row["id"]))
        return self.get_job(row["id"])

    def update_job(self, id, **changes):
        allowed = {"status", "progress", "message", "error", "cancel"}
        if not set(changes) <= allowed:
            raise ValueError("Invalid job fields")
        changes["updated"] = time.time()
        with self.connect() as c:
            c.execute(
                "UPDATE jobs SET " + ",".join(k + "=?" for k in changes) + " WHERE id=?",
                (*changes.values(), id),
            )

    def recover_jobs(self):
        with self.connect() as c:
            c.execute(
                "UPDATE jobs SET status='interrupted',message='Application restarted; resume saved work',updated=? WHERE status IN ('running','queued')",
                (time.time(),),
            )

    def artifact_dir(self, project_id):
        if len(project_id) != 32 or any(c not in "0123456789abcdef" for c in project_id):
            raise ValueError("Invalid project identity")
        path = self.root / "artifacts" / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path
