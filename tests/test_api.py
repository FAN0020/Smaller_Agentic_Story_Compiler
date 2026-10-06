import importlib.util

from fastapi.testclient import TestClient


def client(tmp_path):
    assert importlib.util.find_spec("storycompiler.api"), "Application API is missing"
    from storycompiler.api import create_app

    return TestClient(create_app(tmp_path, start_worker=False))


def test_upload_utf8_sample_and_reload_project(tmp_path):
    with client(tmp_path) as c:
        response = c.post(
            "/api/projects",
            json={
                "title": "My film",
                "source": "A mouse befriends a lion.",
                "brief": {"mode": "children", "target_seconds": 60},
            },
        )
        assert response.status_code == 201
        p = response.json()
        assert c.get("/api/projects/" + p["id"]).json()["source"] == "A mouse befriends a lion."
        meta = c.get("/api/catalog").json()
        assert len(meta["styles"]) >= 5 and len(meta["samples"]) >= 6
    with client(tmp_path) as c:
        assert c.get("/api/projects/" + p["id"]).status_code == 200


def test_render_cannot_bypass_approval_and_duplicate_job_is_safe(tmp_path):
    with client(tmp_path) as c:
        p = c.post(
            "/api/projects",
            json={"title": "Test", "source": "A valid story about a mouse and a lion.", "brief": {}},
        ).json()
        assert (
            c.post("/api/projects/" + p["id"] + "/jobs", json={"kind": "render", "numbers": [1]}).status_code
            == 409
        )
        a = c.post("/api/projects/" + p["id"] + "/jobs", json={"kind": "analyze"}).json()
        b = c.post("/api/projects/" + p["id"] + "/jobs", json={"kind": "analyze"}).json()
        assert a["id"] == b["id"]


def test_cross_origin_mutations_and_path_traversal_are_rejected(tmp_path):
    with client(tmp_path) as c:
        r = c.post(
            "/api/projects",
            headers={"Origin": "https://untrusted.example"},
            json={"title": "Test", "source": "A valid story for upload.", "brief": {}},
        )
        assert r.status_code == 403
        assert c.get("/api/samples/../../secret.key").status_code == 404
        assert c.get("/api/artifacts/not-a-project/secret.key").status_code in (400, 404)


def test_settings_secrets_not_exported_and_empty_story_rejected(tmp_path):
    with client(tmp_path) as c:
        assert (
            c.post("/api/projects", json={"title": "Empty", "source": "   ", "brief": {}}).status_code == 422
        )
        r = c.put("/api/settings", json={"credential_provider": "openai", "api_key": "private-key"})
        assert r.status_code == 200 and "private-key" not in r.text
        assert "private-key" not in c.get("/api/settings").text


def test_queued_jobs_freeze_model_choices_without_storing_credentials(tmp_path):
    with client(tmp_path) as c:
        p = c.post(
            "/api/projects", json={"title": "Test", "source": "A lion befriends a mouse.", "brief": {}}
        ).json()
        job = c.post("/api/projects/" + p["id"] + "/jobs", json={"kind": "analyze"}).json()
        assert job["payload"].get("model_settings", {}).get("llm_provider") == "ollama"
        c.put(
            "/api/settings",
            json={
                "llm_model": "another-local-model",
                "credential_provider": "openai",
                "api_key": "secret-for-test",
            },
        )
        stored = c.get("/api/projects/" + p["id"]).json()["jobs"][0]
        assert stored["payload"]["model_settings"]["llm_model"] != "another-local-model"
        assert "secret-for-test" not in str(stored)


def test_plan_revision_invalidates_approval_and_rejects_invalid_timing(tmp_path):
    from storycompiler.domain import fingerprint
    from test_contracts import shot_payload

    with client(tmp_path) as c:
        repo = c.app.state.repo
        p = repo.create_project(
            "Editable plan fixture",
            "A lion rests.",
            {"mode": "general", "style": "watercolor", "target_seconds": 60},
        )
        p["bible"] = {"characters": [{"id": "c1"}], "locations": [{"id": "l1"}]}
        p["bible_hash"] = fingerprint(p["bible"])
        p["episodes"] = [{"number": 1, "source_event_ids": ["ev1"]}]
        scene = {
            "id": "sc1",
            "episode_number": 1,
            "bible_hash": p["bible_hash"],
            "title": "Rest",
            "purpose": "Calm",
            "objective": "Rest",
            "conflict": "None",
            "source_event_ids": ["ev1"],
            "characters": ["c1"],
            "location_id": "l1",
            "emotional_progression": "Calm",
            "information_plan": "Rest",
            "geography": "Tree",
            "lighting": "Sunlight",
            "environment": "Forest",
            "sound_intent": "Wind",
            "duration": 60,
            "start_state": {"paw": "closed"},
            "end_state": {"paw": "closed"},
        }
        shots = [
            shot_payload()
            | {
                "id": f"sh{i}",
                "bible_hash": p["bible_hash"],
                "end_state": {"paw": "closed"},
                "action": "The lion rests.",
            }
            for i in range(15)
        ]
        p["plans"]["1"] = {
            "scenes": [scene],
            "shots": shots,
            "hash": "prior",
            "approved_hash": "prior",
            "status": "ready",
        }
        repo.save_project(p)
        path = f"/api/projects/{p['id']}/plans/1"
        shots[0]["action"] = "The lion rests under a tree."
        changed = c.put(path, json={"scenes": [scene], "shots": shots})
        assert changed.status_code == 200, changed.text
        plan = changed.json()["plans"]["1"]
        assert "approved_hash" not in plan
        assert plan["hash"] != "prior" and plan["revisions"][0]["hash"] == "prior"
        shots[0]["duration"] = 8
        rejected = c.put(path, json={"scenes": [scene], "shots": shots})
        assert rejected.status_code == 409
        assert repo.get_project(p["id"])["plans"]["1"]["hash"] == plan["hash"]
        shots[0]["duration"] = 4
        # Global coverage alone must not permit a later event inside an earlier scene.
        p = repo.get_project(p["id"])
        p["episodes"][0]["source_event_ids"] = ["ev1", "ev2"]
        repo.save_project(p)
        scenes = [
            scene | {"duration": 28},
            scene | {"id": "sc2", "duration": 32, "source_event_ids": ["ev2"]},
        ]
        for shot in shots[7:]:
            shot.update(scene_id="sc2", source_event_ids=["ev2"])
        assert c.put(path, json={"scenes": scenes, "shots": shots}).status_code == 200
        shots[0]["source_event_ids"] = ["ev2"]
        assert c.put(path, json={"scenes": scenes, "shots": shots}).status_code == 409
