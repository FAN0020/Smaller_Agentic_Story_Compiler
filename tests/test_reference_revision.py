"""Reference redesign keeps the original canon and all dependent work intact."""

import pytest
from PIL import Image
from storycompiler.domain import CreativeBrief
from storycompiler.jobs import JobWorker
from storycompiler.planning import Planner
from storycompiler.production import Producer, file_hash
from test_api import client
from test_planning import AnalysisModel


def planned_project(c, monkeypatch):
    repo = c.app.state.repo
    p = repo.create_project("Reference revision", "The mouse frees the lion.", CreativeBrief().model_dump())
    planner = Planner(repo, AnalysisModel(), lambda *_: None)
    planner.analyze(p)
    planner.freeze(p)

    def image(self, prompt, output, seed):
        Image.new("RGB", (16, 16), "green").save(output)

    monkeypatch.setattr(Producer, "image", image)
    producer = Producer(repo, c.app.state.settings, lambda *_: None, lambda: False)
    producer.references(p)
    producer.approve_references(p)
    p["episodes"] = [{"number": 1, "references_hash": p["references_hash"]}]
    p["plans"] = {"1": {"approved_hash": "approved-plan"}}
    p["productions"] = {"1": {"file": "episode-1.mp4"}}
    p["reviews"] = {"1": {"status": "approved"}}
    p["status"] = "watch_ready"
    repo.save_project(p)
    return p


@pytest.mark.parametrize("entity_id", ["c1", "l1"])
def test_reference_revision_regenerates_edited_prompt_without_changing_original(
    tmp_path, monkeypatch, entity_id
):
    with client(tmp_path) as c:
        parent = planned_project(c, monkeypatch)
        repo = c.app.state.repo
        body = {"only": entity_id, "prompt": "Watercolor design with golden highlights."}
        response = c.post(f"/api/projects/{parent['id']}/reference-revision", json=body)
        assert response.status_code == 201, response.text
        new = response.json()
        assert new["id"] != parent["id"] and new["parent_project"] == parent["id"]
        for key in (
            "source",
            "brief",
            "analyses",
            "events",
            "bible",
            "bible_hash",
            "bible_sections_done",
            "estimated_episode_count",
        ):
            assert new[key] == parent[key]
        assert new["episodes"] == [] and new["plans"] == {} and new["productions"] == {}
        assert new["reviews"] == {} and new["references_hash"] is None
        assert not any(r["approved"] for r in new["references"].values())
        for ref in new["references"].values():
            assert file_hash(repo.artifact_dir(new["id"]) / ref["file"]) == ref["sha256"]
        job = repo.jobs(new["id"])[0]
        assert job["kind"] == "references" and job["payload"]["prompt"] == body["prompt"]
        assert job["payload"]["only"] == entity_id
        assert job["payload"]["model_settings"] == c.app.state.settings.get().model_dump()
        # The revision cannot plan episodes using inherited approval.
        assert c.post(f"/api/projects/{new['id']}/jobs", json={"kind": "episodes"}).status_code == 409

        def regenerated(self, prompt, output, seed):
            assert prompt == body["prompt"]
            Image.new("RGB", (16, 16), "gold").save(output)

        monkeypatch.setattr(Producer, "image", regenerated)
        JobWorker(repo, c.app.state.settings).execute(repo.next_job())
        assert repo.get_job(job["id"])["status"] == "complete"
        updated = repo.get_project(new["id"])
        assert updated["references"][entity_id]["prompt"] == body["prompt"]
        assert updated["references"][entity_id]["attempt"] == 2
        assert updated["references"][entity_id]["sha256"] != parent["references"][entity_id]["sha256"]
        other = "l1" if entity_id == "c1" else "c1"
        assert updated["references"][other]["sha256"] == parent["references"][other]["sha256"]
        assert repo.get_project(parent["id"]) == parent
        for ref in parent["references"].values():
            assert file_hash(repo.artifact_dir(parent["id"]) / ref["file"]) == ref["sha256"]
        assert c.post(f"/api/projects/{new['id']}/approve", json={"kind": "references"}).status_code == 200
        assert c.post(f"/api/projects/{new['id']}/jobs", json={"kind": "episodes"}).status_code == 202


@pytest.mark.parametrize("invalid", ["unknown", "blank", "busy", "missing", "changed"])
def test_invalid_reference_revision_does_not_create_partial_project(tmp_path, monkeypatch, invalid):
    with client(tmp_path) as c:
        parent = planned_project(c, monkeypatch)
        repo = c.app.state.repo
        body = {"only": "c1", "prompt": "New design"}
        if invalid == "unknown":
            body["only"] = "unknown"
        elif invalid == "blank":
            body["prompt"] = "   "
        elif invalid == "busy":
            repo.enqueue(parent["id"], "direct", {"numbers": [1]})
        else:
            image = repo.artifact_dir(parent["id"]) / parent["references"]["c1"]["file"]
            if invalid == "missing":
                image.unlink()
            else:
                image.write_bytes(b"changed")
        response = c.post(f"/api/projects/{parent['id']}/reference-revision", json=body)
        assert response.status_code == (422 if invalid == "blank" else 409), response.text
        assert len(repo.list_projects()) == 1
        assert repo.get_project(parent["id"]) == parent


def test_failed_revision_generation_retains_prompt_for_resume(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        parent = planned_project(c, monkeypatch)
        repo = c.app.state.repo
        response = c.post(
            f"/api/projects/{parent['id']}/reference-revision",
            json={"only": "c1", "prompt": "A golden mouse"},
        )
        assert response.status_code == 201, response.text
        new = response.json()

        def failed(*args):
            raise RuntimeError("Image provider unavailable")

        monkeypatch.setattr(Producer, "image", failed)
        worker = JobWorker(repo, c.app.state.settings)
        worker.execute(repo.next_job())
        failed_job = repo.jobs(new["id"])[0]
        assert failed_job["status"] == "failed" and failed_job["payload"]["prompt"] == "A golden mouse"
        assert repo.get_project(parent["id"]) == parent
        assert repo.get_project(new["id"])["references"]["c1"]["file"] == parent["references"]["c1"]["file"]
        assert c.post(f"/api/jobs/{failed_job['id']}/resume").status_code == 200


@pytest.mark.parametrize("failure", ["copy", "queue"])
def test_revision_failure_rolls_back_project_job_and_copied_images(tmp_path, monkeypatch, failure):
    with client(tmp_path) as c:
        parent = planned_project(c, monkeypatch)
        repo = c.app.state.repo

        def fail(*args):
            raise OSError("Disk write failed")

        target = (
            "storycompiler.storage.shutil.copy2"
            if failure == "copy"
            else "storycompiler.storage.Repository._insert_job"
        )
        monkeypatch.setattr(target, fail)
        with pytest.raises(OSError, match="Disk write failed"):
            c.post(
                f"/api/projects/{parent['id']}/reference-revision",
                json={"only": "c1", "prompt": "A golden mouse"},
            )
        assert repo.list_projects() == [parent]
        assert repo.next_job() is None
        assert [p.name for p in (tmp_path / "artifacts").iterdir()] == [parent["id"]]


def test_planned_project_still_rejects_in_place_regeneration(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        parent = planned_project(c, monkeypatch)
        response = c.post(
            f"/api/projects/{parent['id']}/jobs",
            json={"kind": "references", "only": "c1", "prompt": "A golden mouse"},
        )
        assert response.status_code == 409
        # Resuming an older reference job must enforce the same lock, even for legacy data.
        parent["references_hash"] = None
        with pytest.raises(ValueError, match="episode plans"):
            Producer(c.app.state.repo, c.app.state.settings, lambda *_: None, lambda: False).references(
                parent, "c1", "A golden mouse"
            )


def test_before_episode_planning_prompt_regenerates_in_same_project(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        p = planned_project(c, monkeypatch)
        repo = c.app.state.repo
        p.update(episodes=[], plans={}, productions={}, reviews={})
        repo.save_project(p)
        response = c.post(
            f"/api/projects/{p['id']}/jobs",
            json={"kind": "references", "only": "c1", "prompt": "A mouse with golden highlights"},
        )
        assert response.status_code == 202, response.text
        JobWorker(repo, c.app.state.settings).execute(repo.next_job())
        updated = repo.get_project(p["id"])
        assert updated["references"]["c1"]["prompt"] == "A mouse with golden highlights"
        assert updated["references"]["c1"]["attempt"] == 2
        assert updated["references_hash"] is None
        assert len(repo.list_projects()) == 1
