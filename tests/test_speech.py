import pytest
from storycompiler.speech import compile_cues, schedule_cues


def shots():
    return [{"id": f"s{i}", "scene_id": "scene1", "duration": 4, "speech": []} for i in range(3)]


def test_sentence_can_span_cuts_and_narration_is_distinct_from_dialogue():
    plan = shots()
    plan[0]["speech"] = [
        {
            "kind": "narration",
            "speaker": "narrator",
            "text": "A mouse discovered that even a mighty lion might need help.",
            "end_shot_id": "s1",
            "delivery": "warm",
            "pace": 1,
        }
    ]
    plan[2]["speech"] = [
        {
            "kind": "dialogue",
            "speaker": "mouse",
            "text": "I can help!",
            "end_shot_id": "s2",
            "delivery": "hopeful",
            "pace": 1,
        }
    ]
    cues = compile_cues(plan, {"mouse"})
    result = schedule_cues(cues, [6.2, 1.3])
    assert result[0]["start"] == 0 and result[0]["end"] == 6.2
    assert result[1]["start"] == 8 and result[1]["speaker"] == "mouse"


def test_long_audio_is_rejected_before_video_and_never_accelerated():
    plan = shots()
    plan[0]["speech"] = [
        {"kind": "narration", "speaker": "narrator", "text": "Long line", "end_shot_id": "s0", "pace": 1}
    ]
    with pytest.raises(ValueError, match="Shorten"):
        schedule_cues(compile_cues(plan, set()), [4.1])


def test_wrong_speaker_cross_scene_and_dialogue_only_are_rejected():
    plan = shots()
    plan[0]["speech"] = [
        {"kind": "dialogue", "speaker": "ghost", "text": "Hello", "end_shot_id": "s1", "pace": 1}
    ]
    with pytest.raises(ValueError, match="speaker"):
        compile_cues(plan, {"mouse"})
    plan[0]["speech"][0].update(kind="narration", speaker="narrator")
    plan[1]["scene_id"] = "scene2"
    with pytest.raises(ValueError, match="scene"):
        compile_cues(plan, {"mouse"})
    plan = shots()
    plan[0]["speech"] = [
        {"kind": "dialogue", "speaker": "mouse", "text": "Hello", "end_shot_id": "s1", "pace": 1}
    ]
    with pytest.raises(ValueError, match="narration"):
        compile_cues(plan, {"mouse"})


def test_soundtrack_records_before_images_and_reuses_verified_audio(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from storycompiler.media import run
    from storycompiler.production import Producer
    from storycompiler.resources import Snapshot
    from storycompiler.settings import SettingsStore

    monkeypatch.setattr("storycompiler.soundtrack.snapshot", lambda _: Snapshot(24, 12, 40, 0))
    saved = []
    repo = SimpleNamespace(
        root=tmp_path, artifact_dir=lambda _: tmp_path, save_project=lambda p: saved.append(p["id"])
    )
    store = SettingsStore(tmp_path)
    producer = Producer(repo, store, lambda *_: None, lambda: False)
    monkeypatch.setattr("storycompiler.production.assert_production_approved", lambda *_: None)
    monkeypatch.setattr(producer, "image", lambda *_: pytest.fail("Images must wait for speech timing"))
    calls = []

    class Voice:
        def __init__(self, *_):
            pass

        def speak(self, text, output, voice, pace):
            calls.append(text)
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=5", str(output)])

    monkeypatch.setattr("storycompiler.soundtrack.KokoroVoice", Voice)
    p = {
        "id": "test",
        "bible": {"characters": []},
        "references": {},
        "references_hash": "refs",
        "productions": {},
        "brief": {"target_seconds": 60},
        "plans": {
            "1": {
                "hash": "plan",
                "shots": [
                    {
                        "id": "s0",
                        "scene_id": "scene",
                        "duration": 4,
                        "speech": [
                            {
                                "kind": "narration",
                                "speaker": "narrator",
                                "text": "A long spoken line",
                                "end_shot_id": "s0",
                                "pace": 1,
                            }
                        ],
                    }
                ],
            }
        },
    }
    with pytest.raises(ValueError, match="Shorten"):
        producer.render(p, [1])
    with pytest.raises(ValueError, match="Shorten"):
        producer.render(p, [1])
    assert calls == ["A long spoken line"], "Resume should reuse the checkpoint, without new speech charges"
    assert saved


def test_real_soundtrack_keeps_silence_and_captions_follow_measured_speech(tmp_path):
    from storycompiler.media import probe, run
    from storycompiler.speech import mix_soundtrack, write_audio_subtitles

    voice = tmp_path / "line.wav"
    run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5", str(voice)])
    cues = [
        {
            "start": 4,
            "end": 5.5,
            "text": "A complete sentence.",
            "kind": "narration",
            "speaker": "narrator",
            "file": "line.wav",
        }
    ]
    mix_soundtrack(cues, tmp_path, tmp_path / "track.wav", 12)
    assert abs(float(probe(tmp_path / "track.wav")["format"]["duration"]) - 12) < 0.01
    write_audio_subtitles(cues, tmp_path / "track.vtt")
    assert "00:00:04.000 --> 00:00:05.500" in (tmp_path / "track.vtt").read_text()


def test_audio_director_context_excludes_old_captions_and_other_scene_events():
    from storycompiler.planning import audio_context

    p = {
        "brief": {},
        "bible": {"characters": []},
        "events": [{"id": "e1"}, {"id": "e2"}],
        "episodes": [{"number": 1, "source_event_ids": ["e1", "e2"]}],
    }
    plan = {
        "scenes": [{"id": "scene", "title": "Opening", "duration": 4, "source_event_ids": ["e1"]}],
        "shots": [
            {
                "id": "s1",
                "scene_id": "scene",
                "duration": 4,
                "action": "Lion sleeps",
                "source_event_ids": ["e1"],
                "narration": "Obsolete mechanical caption",
                "speech": [],
                "sound": {"dialogue": ""},
            }
        ],
    }
    context = audio_context(p, 1, plan)
    assert context["source_events"] == [{"id": "e1"}]
    assert "narration" not in context["shots"][0]
    assert "speech" not in context["shots"][0]


def test_scene_audio_writer_passes_a_constrained_schema_to_the_provider():
    from types import SimpleNamespace

    from storycompiler.planning import Planner

    p = {
        "brief": {},
        "bible": {"characters": []},
        "events": [{"id": "e1"}],
        "episodes": [{"number": 1, "source_event_ids": ["e1"]}],
    }
    plan = {
        "scenes": [{"id": "scene", "title": "Opening", "duration": 4, "source_event_ids": ["e1"]}],
        "shots": [
            {
                "id": "s1",
                "scene_id": "scene",
                "duration": 4,
                "action": "Lion sleeps",
                "source_event_ids": ["e1"],
                "narration": "Old caption",
                "speech": [],
                "sound": {"dialogue": ""},
            }
        ],
    }
    calls = []

    def generate(stage, context, schema):
        calls.append(stage)
        assert isinstance(schema.model_json_schema(), dict)
        if stage == "audio-director":
            return schema.model_validate(
                {
                    "lines": [
                        {
                            "kind": "narration",
                            "speaker": "narrator",
                            "text": "A lion slept in the shade.",
                            "shot_id": "s1",
                            "end_shot_id": "s1",
                        }
                    ]
                }
            )
        return schema.model_validate({"findings": [], "strengths": [], "summary": "Fixture review"})

    planner = Planner(
        SimpleNamespace(save_project=lambda _: None), SimpleNamespace(generate=generate), lambda *_: None
    )
    result = planner.write_audio(p, 1, plan)
    assert calls == ["audio-director", "narrative-critic"]
    assert result[0]["speech"][0]["speaker"] == "narrator"


def test_clip_direction_receives_only_its_measured_voice_interval():
    from storycompiler.speech import cue_intervals

    cues = [
        {
            "start": 0,
            "end": 5.7,
            "speaker": "narrator",
            "kind": "narration",
            "delivery": "warm",
            "text": "Story text",
        },
        {
            "start": 8,
            "end": 10,
            "speaker": "mouse",
            "kind": "dialogue",
            "delivery": "hopeful",
            "text": "Later words",
        },
    ]
    intervals = cue_intervals(cues, 4, 4)
    assert len(intervals) == 1
    assert intervals[0]["from_seconds"] == 0 and intervals[0]["to_seconds"] == pytest.approx(1.7)
    assert "text" not in intervals[0], "Later plot facts should not leak into a shot through voice context"
