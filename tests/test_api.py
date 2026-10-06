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
