"""Provider doubles isolate slow model calls; real planners must enforce all gates."""

import importlib.util

import pytest
from storycompiler.domain import CreativeBrief


def modules():
    assert importlib.util.find_spec("storycompiler.planning"), "Planner pipeline is missing"
    from storycompiler.planning import Planner
    from storycompiler.storage import Repository

    return Planner, Repository


class AnalysisModel:
    def generate(self, stage, context, schema):
        if stage == "source-analysis":
            return schema.model_validate(
                {
                    "summary": "Kindness is repaid",
                    "events": [
                        {
                            "summary": "Mouse frees lion",
                            "quote": "The mouse frees the lion.",
                            "characters": ["Mouse", "Lion"],
                            "location": "Forest",
                        }
                    ],
                    "content_notes": [],
                }
            )
        if stage == "series-bible":
            return schema.model_validate(
                {
                    "title": "Kindness",
                    "logline": "A mouse helps a lion.",
                    "genre": "Fable",
                    "themes": ["kindness"],
                    "characters": [
                        {
                            "id": "c1",
                            "name": "Mouse",
                            "source_facts": "Helps lion",
                            "appearance": "brown mouse",
                            "costume": "none",
                            "acting": "alert",
                            "voice": "warm",
                            "design_choices": "brown fur",
                        }
                    ],
                    "locations": [
                        {
                            "id": "l1",
                            "name": "Forest",
                            "source_facts": "setting",
                            "appearance": "green woods",
                            "geography": "tree left",
                            "lighting": "daylight",
                            "design_choices": "oak tree",
                        }
                    ],
                    "directing_principles": ["Read actions clearly"],
                    "adaptation_notes": [],
                    "content_warnings": [],
                    "visual_motifs": [],
                }
            )
        raise AssertionError(stage)


def test_source_analysis_checkpoints_and_freezes_before_episode_division(tmp_path):
    Planner, Repo = modules()
    repo = Repo(tmp_path)
    p = repo.create_project("Test", "The mouse frees the lion.", CreativeBrief().model_dump())
    planner = Planner(repo, AnalysisModel(), lambda *_: None)
    planner.analyze(p)
    p = repo.get_project(p["id"])
    assert p["events"][0]["quote"] == "The mouse frees the lion."
    assert p["bible"]["characters"][0]["appearance"] == "brown mouse"
    with pytest.raises(ValueError, match="freeze"):
        planner.episodes(p)
    planner.freeze(p)
    frozen = p["bible_hash"]
    p["bible"]["characters"][0]["appearance"] = "blue mouse"
    with pytest.raises(ValueError, match="changed"):
        planner.assert_frozen(p)
    assert frozen


def test_analysis_rejects_fabricated_source_evidence(tmp_path):
    Planner, Repo = modules()
    repo = Repo(tmp_path)
    p = repo.create_project("Test", "A completely different story.", CreativeBrief().model_dump())
    with pytest.raises(ValueError, match="evidence"):
        Planner(repo, AnalysisModel(), lambda *_: None).analyze(p)


def test_evidence_quotes_match_wrapped_source_without_inventing_words(tmp_path):
    Planner, Repo = modules()
    repo = Repo(tmp_path)
    p = repo.create_project("Test", "The mouse frees\nthe lion.", CreativeBrief().model_dump())
    Planner(repo, AnalysisModel(), lambda *_: None).analyze(p)
    event = p["events"][0]
    assert p["source"][event["source_start"] : event["source_end"]] == "The mouse frees\nthe lion."


def test_http_llm_uses_structured_contract_and_reports_provider_errors(tmp_path):
    assert importlib.util.find_spec("storycompiler.providers"), "Provider adapters are missing"
    import httpx
    from storycompiler.contracts import ChunkAnalysis
    from storycompiler.providers import JsonLLM, ProviderError
    from storycompiler.settings import SettingsStore

    def handler(request):
        return httpx.Response(401, json={"error": "invalid API key secret-should-not-leak"})

    settings = SettingsStore(tmp_path)
    llm = JsonLLM(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError) as e:
        llm.generate("source-analysis", {}, ChunkAnalysis)
    assert "secret-should-not-leak" not in str(e.value)
    assert "401" in str(e.value)
