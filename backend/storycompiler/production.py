"""Approval-bound production, checkpointed at every expensive artifact boundary."""

import hashlib
import time
import uuid
from pathlib import Path

from .compiler import compile_frame, compile_shot
from .contracts import ShotPlan
from .domain import STYLE_BY_ID, fingerprint
from .generation import LocalGenerator, OpenAIGenerator
from .media import (
    animatic_clip,
    assemble,
    extract_frame,
    normalize_clip,
    probe,
    system_voice,
    write_subtitles,
)
from .planning import Planner
from .validation import assert_references_frozen, reference_manifest


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def assert_production_approved(p, numbers):
    Planner.assert_frozen(p)
    assert_references_frozen(p)
    for number in numbers:
        plan = p["plans"].get(str(number), {})
        current = fingerprint(
            {"scenes": plan.get("scenes"), "shots": plan.get("shots"), "bible_hash": p["bible_hash"]}
        )
        if not plan.get("approved_hash") or plan["approved_hash"] != current:
            raise ValueError(f"Approve the current Episode {number} plan before production")
        if plan.get("hard_gate_errors"):
            raise ValueError(f"Episode {number} has unresolved deterministic errors")


class Producer:
    def __init__(self, repo, settings, progress, cancelled):
        self.repo, self.store, self.progress = repo, settings, progress
        self.settings = settings.get()
        self.local = LocalGenerator(repo.root, cancelled)
        self.cancelled = cancelled
        self.remote = None

    def hosted(self):
        if self.remote is None:
            self.remote = OpenAIGenerator(self.store, self.cancelled)
        return self.remote

    def image(self, prompt, output, seed, references=None):
        if self.settings.image_provider == "openai":
            return self.hosted().image(prompt, output, self.settings.image_model, references)
        return self.local.image(prompt, output, seed, references, self.settings.image_model)

    def references(self, p, only=None):
        Planner.assert_frozen(p)
        if p["references_hash"]:
            raise ValueError("References are frozen; create a revision to redesign them")
        entities = [(kind, e) for kind in ("characters", "locations") for e in p["bible"][kind]]
        directory = self.repo.artifact_dir(p["id"])
        for i, (kind, entity) in enumerate(entities):
            if only and entity["id"] != only:
                continue
            existing = p["references"].get(entity["id"])
            if existing and not only and (directory / existing["file"]).exists():
                continue
            self.progress(i / len(entities), f"Painting reference: {entity['name']}…")
            attempt = (existing or {}).get("attempt", 0) + 1
            file = f"reference-{fingerprint(entity['id'])[:12]}-{attempt}.png"
            style = STYLE_BY_ID[p["brief"]["style"]].name
            purpose = (
                "Single character full body, clear face, neutral pose"
                if kind == "characters"
                else "Wide environment, no people, clear landmarks"
            )
            prompt = f"{style} painting. {purpose}. {entity['name']}: {entity['appearance']}. {entity.get('costume', entity.get('lighting', ''))}. No text."
            self.image(prompt, directory / file, self.settings.seed + i + attempt)
            p["references"][entity["id"]] = {
                "file": file,
                "name": entity["name"],
                "kind": kind,
                "sha256": file_hash(directory / file),
                "bible_hash": p["bible_hash"],
                "approved": False,
                "prompt": prompt,
                "provider": self.settings.image_provider,
                "model": self.settings.image_model,
                "attempt": attempt,
            }
            self.repo.save_project(p)
        p["status"] = "references_review"
        self.repo.save_project(p)
        self.progress(1, "Review the character and location references")

    def approve_references(self, p):
        expected = {e["id"] for key in ("characters", "locations") for e in p["bible"][key]}
        if set(p["references"]) != expected:
            raise ValueError("Generate all character and location references first")
        directory = self.repo.artifact_dir(p["id"])
        for reference in p["references"].values():
            if file_hash(directory / reference["file"]) != reference["sha256"]:
                raise ValueError("Reference image changed; regenerate it before approval")
            reference["approved"] = True
        p["references_hash"] = fingerprint(reference_manifest(p))
        p["audit"].append({"action": "references_approved", "hash": p["references_hash"], "at": time.time()})
        self.repo.save_project(p)

    def approve_plans(self, p, numbers, accept_findings=False):
        for number in numbers:
            plan = p["plans"].get(str(number))
            if (
                not plan
                or plan.get("status") not in ("ready", "review_required")
                or plan.get("hard_gate_errors")
            ):
                raise ValueError(f"Episode {number} needs a valid complete plan")
            errors = [f for f in plan.get("critique", {}).get("findings", []) if f["severity"] == "error"]
            if errors and not accept_findings:
                raise ValueError("Review critic findings and explicitly accept them before production")
            plan["approved_hash"] = plan["hash"]
            plan["approved_at"] = time.time()
            plan["accepted_findings"] = accept_findings
        self.repo.save_project(p)

    def render(self, p, numbers):
        assert_production_approved(p, numbers)
        directory = self.repo.artifact_dir(p["id"])
        for ref in p["references"].values():
            if file_hash(directory / ref["file"]) != ref["sha256"]:
                raise ValueError("Approved reference file changed on disk")
        total = sum(len(p["plans"][str(n)]["shots"]) for n in numbers)
        missing = sum(
            1
            for n in numbers
            for s in p["plans"][str(n)]["shots"]
            if not p["productions"].get(str(n), {}).get("clips", {}).get(s["id"], {}).get("file")
        )
        # Each clip may need a frame, a video and a voice call. Explicit ceiling avoids unbounded spend.
        required_calls = missing * (2 + (self.settings.voice_provider == "openai"))
        if required_calls > self.settings.max_generation_calls:
            raise ValueError(
                f"Up to {required_calls} generation calls required; raise the call budget in Model settings or select fewer episodes"
            )
        completed = 0
        for number in numbers:
            key = str(number)
            plan = p["plans"][key]
            production = p["productions"].setdefault(
                key,
                {
                    "prefix": f"take-{uuid.uuid4().hex[:8]}-",
                    "clips": {},
                    "status": "rendering",
                    "settings": self.settings.model_dump(),
                    "plan_hash": plan["hash"],
                    "references_hash": p["references_hash"],
                },
            )
            if (
                production["plan_hash"] != plan["hash"]
                or production["references_hash"] != p["references_hash"]
            ):
                raise ValueError("Production lineage changed; create a revision")
            if production["settings"] != self.settings.model_dump():
                raise ValueError(
                    "Models changed during this production. Restore the saved model settings to resume it."
                )
            files = []
            prefix = production.get("prefix", "")
            for i, payload in enumerate(plan["shots"]):
                shot = ShotPlan.model_validate(payload)
                receipt = production["clips"].setdefault(shot.id, {})
                file = f"{prefix}ep{number}-{i + 1:03}.mp4"
                if receipt.get("file") and (directory / receipt["file"]).exists():
                    files.append(directory / receipt["file"])
                    completed += 1
                    continue
                self.progress(
                    completed / total, f"Rendering Episode {number}, shot {i + 1} of {len(plan['shots'])}…"
                )
                scene = next(s for s in plan["scenes"] if s["id"] == shot.scene_id)
                prompt = compile_shot(shot, p["bible"], scene=scene)
                receipt.update(
                    prompt=prompt,
                    seed=self.settings.seed + number * 1000 + i,
                    bible_hash=p["bible_hash"],
                    references_hash=p["references_hash"],
                )
                self.repo.save_project(p)
                frame = directory / f"{prefix}ep{number}-{i + 1:03}-frame.png"
                refs = [
                    directory / p["references"][entity]["file"]
                    for entity in [*shot.characters, shot.location_id]
                ]
                if not frame.exists():
                    still_prompt = compile_frame(shot, p["bible"], scene)
                    self.image(still_prompt, frame, receipt["seed"], refs)
                raw = directory / f"{prefix}ep{number}-{i + 1:03}-raw.mp4"
                if not raw.exists():
                    if self.settings.video_provider == "animatic":
                        animatic_clip(frame, raw, shot.duration)
                    elif self.settings.video_provider == "local":
                        self.local.video(
                            prompt,
                            frame,
                            raw,
                            receipt["seed"],
                            self.settings.local_steps,
                            p["brief"]["aspect"] == "9:16",
                        )
                    else:
                        self.hosted().video(
                            prompt,
                            frame,
                            raw,
                            self.settings.video_model,
                            receipt,
                            lambda: self.repo.save_project(p),
                            p["brief"]["aspect"] == "9:16",
                        )
                narration = None
                if shot.narration and self.settings.voice_provider != "none":
                    narration = directory / f"{prefix}ep{number}-{i + 1:03}-voice.wav"
                    if not narration.exists():
                        if self.settings.voice_provider == "system":
                            system_voice(shot.narration, narration, self.settings.voice)
                        else:
                            self.hosted().speech(shot.narration, narration, self.settings.voice)
                size = (432, 768) if p["brief"]["aspect"] == "9:16" else (768, 432)
                normalize_clip(raw, directory / file, shot.duration, size, narration)
                receipt.update(
                    file=file,
                    sha256=file_hash(directory / file),
                    technical=probe(directory / file)["format"],
                    status="complete",
                )
                files.append(directory / file)
                completed += 1
                self.repo.save_project(p)
            self.progress(completed / total, f"Assembling Episode {number}…")
            output = directory / f"{prefix}episode-{number}.mp4"
            duration = assemble(files, output, p["brief"]["target_seconds"])
            subtitles = directory / f"{prefix}episode-{number}.vtt"
            write_subtitles(plan["shots"], subtitles)
            samples = []
            for j, seconds in enumerate((0.25, duration / 2, max(0.25, duration - 0.5))):
                sample = directory / f"{prefix}episode-{number}-sample-{j}.png"
                extract_frame(output, sample, seconds)
                samples.append(sample.name)
            production.update(
                file=output.name,
                subtitles=subtitles.name,
                duration=duration,
                samples=samples,
                status="review_required",
                kind="illustrated_animatic"
                if self.settings.video_provider == "animatic"
                else "generated_video",
                technical_status="passed",
                visual_status="human_review_required",
                audio_notes="Narration is synthesized when selected. Foley and music are directing intent; local generation does not synthesize them.",
                sha256=file_hash(output),
            )
            p["status"] = "watch_ready"
            self.repo.save_project(p)
        self.progress(1, "Episodes are ready to watch and review")

    def close(self):
        if self.remote:
            self.remote.close()
