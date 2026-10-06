"""Exercise real startup, queued work, abrupt restart, and explicit recovery on isolated data."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx


def wait_until(check, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (httpx.HTTPError, KeyError, IndexError):
            pass
        time.sleep(0.1)
    raise AssertionError("Runtime condition was not reached")


def main():
    release = threading.Event()
    request_started = threading.Event()

    class SlowProvider(BaseHTTPRequestHandler):
        def reply(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply({"models": [{"name": "qwen3.5:4b", "size": 1}]})

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path == "/api/show":
                self.reply({"capabilities": ["completion", "thinking"]})
                return
            request_started.set()
            release.wait(30)
            self.send_response(503)
            self.end_headers()

        def log_message(self, *_):
            pass

    provider = ThreadingHTTPServer(("127.0.0.1", 0), SlowProvider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="story-runtime-") as temporary:
        env = {**os.environ, "STORY_STUDIO_HOME": temporary}
        process = None
        with (
            Path(temporary, "server.log").open("w") as log,
            httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client,
        ):

            def start():
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "storycompiler.api:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                    ],
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                wait_until(lambda: client.get("/api/health").json()["worker_alive"])
                return child

            try:
                process = start()
                assert client.get("/").status_code == 200
                client.put(
                    "/api/settings", json={"llm_endpoint": f"http://127.0.0.1:{provider.server_port}"}
                ).raise_for_status()
                p = client.post(
                    "/api/projects", json={"title": "Runtime recovery", "source": "A mouse helps a lion."}
                ).json()
                path = f"/api/projects/{p['id']}"
                job = client.post(path + "/jobs", json={"kind": "analyze"}).json()

                def running():
                    current = client.get(path).json()["jobs"][0]
                    if current["status"] not in ("queued", "running"):
                        raise AssertionError(f"Job stopped before restart verification: {current}")
                    return current["status"] == "running" and request_started.is_set()

                wait_until(running)
                process.kill()
                process.wait(timeout=5)
                request_started.clear()
                process = start()
                restored = client.get(path).json()
                assert restored["source"] == p["source"]
                assert restored["jobs"][0]["status"] == "interrupted"
                time.sleep(0.7)
                assert client.get(path).json()["jobs"][0]["status"] == "interrupted"
                assert client.post(path + "/jobs", json={"kind": "render", "numbers": [1]}).status_code == 409
                client.post(f"/api/jobs/{job['id']}/resume", json={}).raise_for_status()
                wait_until(running)
                print(
                    json.dumps(
                        {
                            "startup": "passed",
                            "worker": "passed",
                            "persistence": "passed",
                            "crash_recovery": "passed",
                            "explicit_resume": "passed",
                            "approval_gate": "passed",
                        }
                    )
                )
            finally:
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                release.set()
                provider.shutdown()


if __name__ == "__main__":
    main()
