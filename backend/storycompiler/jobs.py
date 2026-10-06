"""One serial durable worker; checkpoints survive process restarts."""

import threading

from .generation import Cancelled
from .planning import Planner, ReviewRequired
from .production import Producer
from .providers import JsonLLM
from .settings import JobSettings


class JobWorker:
    def __init__(self, repo, settings):
        self.repo, self.settings = repo, settings
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name="story-production", daemon=True)

    def start(self):
        self.repo.recover_jobs()
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=10)

    def run(self):
        while not self.stop.is_set():
            job = self.repo.next_job()
            if job is None:
                self.stop.wait(0.5)
                continue
            self.execute(job)

    def execute(self, job):
        llm = None
        producer = None
        try:
            p = self.repo.get_project(job["project_id"])

            def cancelled():
                return self.stop.is_set() or bool(self.repo.get_job(job["id"])["cancel"])

            def progress(amount, message):
                if cancelled():
                    raise Cancelled("Work stopped; completed artifacts are saved")
                self.repo.update_job(job["id"], progress=amount, message=message)

            def record(entry):
                p["audit"].append(entry)

            frozen_settings = JobSettings(
                self.settings, job["payload"].get("model_settings", self.settings.get().model_dump())
            )
            llm = JsonLLM(frozen_settings, record=record)
            planner = Planner(
                self.repo, llm, progress, narration=frozen_settings.get().voice_provider != "none"
            )
            producer = Producer(self.repo, frozen_settings, progress, cancelled)
            options = job["payload"]
            kind = job["kind"]
            if kind == "analyze":
                planner.analyze(p)
            elif kind == "episodes":
                planner.episodes(p)
            elif kind == "references":
                producer.references(p, options.get("only"))
            elif kind == "direct":
                planner.direct(p, options["numbers"])
            elif kind == "render":
                producer.render(p, options["numbers"])
            else:
                raise ValueError("Unknown job type")
            self.repo.update_job(job["id"], status="complete", progress=1, message="Completed")
        except Cancelled as e:
            self.repo.update_job(job["id"], status="cancelled", message=str(e))
        except ReviewRequired as e:
            self.repo.update_job(job["id"], status="review_required", error=str(e), message="Review needed")
        except Exception as e:  # noqa: BLE001 - worker boundary must preserve failed-job state
            self.repo.update_job(
                job["id"],
                status="failed",
                error=str(e)[:1800],
                message="Could not finish; saved work is retained",
            )
        finally:
            if llm:
                llm.close()
            if producer:
                producer.close()
