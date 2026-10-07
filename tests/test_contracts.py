import importlib.util

import pytest


def api():
    assert importlib.util.find_spec("storycompiler.contracts"), "Production contracts are missing"
    assert importlib.util.find_spec("storycompiler.validation"), "Plan gates are missing"
    from storycompiler import contracts as c
    from storycompiler import validation as v

    return c, v


def shot_payload():
    return {
        "id": "sh1",
        "scene_id": "sc1",
        "bible_hash": "abc",
        "source_event_ids": ["ev1"],
        "purpose": "ACTION",
        "narrative_focus": "The mouse is released",
        "visual_focus": "lifting paw",
        "characters": ["c1"],
        "location_id": "l1",
        "action": "The lion lifts his paw.",
        "duration": 4,
        "camera": {"size": "CU", "angle": "eye level", "movement": "static", "motivation": "show release"},
        "performance": [{"character_id": "c1", "intent": "release", "behavior": "opens paw slowly"}],
        "blocking": "paw at screen left",
        "start_state": {"paw": "closed"},
        "end_state": {"paw": "open"},
        "state_reason": "The lion lifts its paw",
        "locked": ["golden mane"],
        "allowed_changes": ["paw position"],
        "sound": {"ambience": "leaves rustle", "foley": "paw brushing grass"},
        "narration": "The lion let the mouse go.",
        "edit": "Cut on the paw lifting",
    }


def test_bible_rejects_colliding_character_and_location_identifiers():
    c, _ = api()
    character = {key: "shared" for key in c.Character.model_fields}
    location = {key: "shared" for key in c.Location.model_fields}
    with pytest.raises(ValueError, match="unique"):
        c.BibleDraft(
            title="Test",
            logline="A forest story",
            genre="Fable",
            themes=[],
            characters=[character],
            locations=[location],
            directing_principles=[],
            adaptation_notes=[],
            content_warnings=[],
            visual_motifs=[],
        )


def test_bible_carries_evidence_labeled_world_setting():
    c, _ = api()
    setting = c.StorySetting.model_validate(
        {
            "period": {
                "value": "late 14th century",
                "basis": "inferred",
                "evidence": "Bronze cannon are named",
                "confidence": "medium",
            },
            "country_or_region": {
                "value": "Anatolia",
                "basis": "explicit",
                "evidence": "The story names Anatolia",
                "confidence": "high",
            },
            "polity_or_dynasty": {
                "value": "Unspecified",
                "basis": "unspecified",
                "evidence": "",
                "confidence": "low",
            },
        }
    )
    assert setting.period.basis == "inferred"
    assert setting.country_or_region.evidence == "The story names Anatolia"
    assert setting.polity_or_dynasty.value == "Unspecified"


def test_video_and_frame_prompts_include_setting_and_avoid_confident_invention():
    c, _ = api()
    from storycompiler.compiler import compile_frame, compile_shot

    setting = {
        "period": {
            "value": "late 14th century",
            "basis": "inferred",
            "evidence": "Bronze cannon are named",
            "confidence": "medium",
        },
        "country_or_region": {
            "value": "Anatolia",
            "basis": "explicit",
            "evidence": "The story names Anatolia",
            "confidence": "high",
        },
        "polity_or_dynasty": {
            "value": "Unspecified",
            "basis": "unspecified",
            "evidence": "",
            "confidence": "low",
        },
        "cultural_context": {
            "value": "Anatolian frontier society",
            "basis": "inferred",
            "evidence": "The story mentions steppe raids and stone forts",
            "confidence": "medium",
        },
        "visual_guidance": ["late medieval stone fortifications"],
        "guardrails": ["Do not depict a named dynasty"],
    }
    bible = {
        "characters": [{"id": "c1", "name": "Lion", "appearance": "golden mane"}],
        "locations": [{"id": "l1", "name": "Forest", "appearance": "acacia clearing"}],
        "style_instruction": "Watercolor on paper",
        "story_setting": setting,
    }
    shot = c.ShotPlan(**shot_payload())
    frame = compile_frame(shot, bible, {})
    motion = compile_shot(shot, bible, limit=4000)
    for prompt in (frame, motion):
        assert "late 14th century" in prompt
        assert "Unspecified" in prompt
        assert "Do not depict a named dynasty" in prompt


def test_continuity_gate_catches_unmotivated_state_reset():
    c, v = api()
    a = c.ShotPlan(**shot_payload())
    b = a.model_copy(update={"id": "sh2", "start_state": {"paw": "closed"}})
    errors = v.validate_shots([a, b], "abc", {"ev1"}, {"c1"}, {"l1"})
    assert any("continuity" in e.lower() for e in errors)


def test_plan_gate_rejects_stale_bible_unknown_character_and_uncovered_source():
    c, v = api()
    shot = c.ShotPlan(**shot_payload())
    errors = v.validate_shots([shot], "new-hash", {"ev1", "ev2"}, {"other"}, {"l1"})
    assert any("bible" in e.lower() for e in errors)
    assert any("character" in e.lower() for e in errors)
    assert any("ev2" in e for e in errors)


def test_compiler_keeps_action_and_identity_and_never_silently_truncates():
    c, _v = api()
    from storycompiler.compiler import compile_shot

    shot = c.ShotPlan(**shot_payload())
    bible = {
        "characters": [{"id": "c1", "name": "Lion", "appearance": "golden mane"}],
        "locations": [{"id": "l1", "name": "Forest", "appearance": "acacia clearing"}],
        "style_instruction": "Watercolor on paper",
    }
    prompt = compile_shot(shot, bible, limit=4000)
    assert "The lion lifts his paw" in prompt and "golden mane" in prompt
    assert "acacia clearing" in prompt and "paw" in prompt
    with pytest.raises(ValueError, match="budget"):
        compile_shot(shot, bible, limit=15)


def test_episode_duration_and_provider_capabilities_are_hard_gates():
    c, v = api()
    shot = c.ShotPlan(**shot_payload()).model_copy(update={"duration": 21})
    assert v.validate_timeline([shot], 60, max_clip_seconds=8)
    good = [c.ShotPlan(**shot_payload()).model_copy(update={"id": f"s{i}"}) for i in range(15)]
    assert v.validate_timeline(good, 60, max_clip_seconds=8) == []


def test_scene_boundaries_reject_state_reset_before_expensive_shot_planning():
    _c, v = api()
    assert hasattr(v, "validate_scenes"), "Scene gate is missing"
    scenes = [
        {
            "id": "a",
            "duration": 28,
            "source_event_ids": ["ev1"],
            "characters": ["c1"],
            "location_id": "l1",
            "start_state": {"paw": "closed"},
            "end_state": {"paw": "open"},
            "transition_reason": "",
        },
        {
            "id": "b",
            "duration": 32,
            "source_event_ids": ["ev2"],
            "characters": ["c1"],
            "location_id": "l1",
            "start_state": {"paw": "closed"},
            "end_state": {"paw": "open"},
            "transition_reason": "",
        },
    ]
    errors = v.validate_scenes(scenes, 60, {"ev1", "ev2"}, {"c1"}, {"l1"})
    assert any("continuity" in e for e in errors)


def test_shot_context_does_not_expose_other_scenes_events():
    from storycompiler import planning

    assert hasattr(planning, "shot_context"), "Scene-scoped context is missing"
    result = planning.shot_context(
        {
            "episode": {"summary": "Secret reveal"},
            "source_events": [
                {"id": "ev1", "summary": "Before reveal"},
                {"id": "ev2", "summary": "Secret revealed"},
            ],
            "bible": {},
        },
        {"source_event_ids": ["ev1"]},
    )
    assert [e["id"] for e in result["source_events"]] == ["ev1"]
    assert "episode" not in result


def test_episode_boundaries_compile_to_complete_ordered_coverage():
    from storycompiler import planning

    assert hasattr(planning, "partition_events"), "Deterministic boundary compiler is missing"
    events = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]
    assert planning.partition_events([2, 4], events) == [["a", "b"], ["c", "d"]]
    with pytest.raises(ValueError):
        planning.partition_events([2, 3], events)
    with pytest.raises(ValueError):
        planning.partition_events([3, 2, 4], events)


def test_scene_boundaries_compile_ids_coverage_and_exact_timeline():
    from storycompiler import planning

    assert hasattr(planning, "compile_scenes"), "Scene boundary compiler is missing"
    candidates = [
        {"end_event_number": 2, "end_clip_number": 6, "title": "Mercy"},
        {"end_event_number": 4, "end_clip_number": 15, "title": "Repayment"},
    ]
    events = [{"id": value} for value in ("a", "b", "c", "d")]
    scenes = planning.compile_scenes(candidates, events, 60, 3, "canon")
    assert [s["source_event_ids"] for s in scenes] == [["a", "b"], ["c", "d"]]
    assert [s["duration"] for s in scenes] == [24, 36]
    assert scenes[0]["id"] == "ep3-sc1" and scenes[1]["bible_hash"] == "canon"
    with pytest.raises(ValueError):
        planning.compile_scenes(candidates, events, 64, 3, "canon")


def test_compiler_carries_scene_geography_and_lighting_into_provider_prompt():
    c, _ = api()
    from storycompiler.compiler import compile_shot

    bible = {
        "characters": [{"id": "c1", "name": "Lion", "appearance": "golden"}],
        "locations": [{"id": "l1", "name": "Forest", "appearance": "oaks"}],
        "style_instruction": "watercolor",
    }
    scene = {
        "lighting": "Moonlight from screen left",
        "geography": "Trap between two oaks",
        "environment": "Misty dawn",
    }
    prompt = compile_shot(c.ShotPlan(**shot_payload()), bible, scene=scene)
    assert all(scene[field] in prompt for field in scene)


def test_shot_compiler_owns_inherited_ids_duration_and_source_reference_resolution():
    from storycompiler import planning

    assert hasattr(planning, "compile_shots")
    scene = {"id": "ep2-sc3", "location_id": "l1"}
    candidate = shot_payload() | {"source_event_numbers": [7], "bible_hash": "wrong", "duration": 99}
    shots = planning.compile_shots([candidate], scene, "canon", [{"id": "ev7", "event_number": 7}])
    assert shots[0].id == "ep2-sc3-sh1"
    assert shots[0].bible_hash == "canon" and shots[0].duration == 4
    assert shots[0].source_event_ids == ["ev7"]
    with pytest.raises(ValueError):
        planning.compile_shots(
            [candidate | {"source_event_numbers": [8]}], scene, "canon", [{"id": "ev7", "event_number": 7}]
        )


def test_opening_frame_prompt_cannot_jump_ahead_to_the_shot_end_state():
    c, _ = api()
    from storycompiler import compiler

    assert hasattr(compiler, "compile_frame")
    shot = c.ShotPlan(**shot_payload())
    bible = {
        "characters": [{"id": "c1", "name": "Lion", "appearance": "golden mane"}],
        "locations": [{"id": "l1", "name": "Forest", "appearance": "oaks"}],
        "style_instruction": "watercolor",
    }
    prompt = compiler.compile_frame(shot, bible, {"lighting": "morning", "geography": "tree left"})
    assert '"paw": "closed"' in prompt
    assert '"paw": "open"' not in prompt
    assert shot.action not in prompt
    assert "golden mane" in prompt and "morning" in prompt


def test_shot_agent_sees_only_assigned_source_passages_and_visual_canon():
    from storycompiler.planning import shot_context

    result = shot_context(
        {
            "source_events": [
                {"id": "ev1", "quote": "The lion was asleep.", "source_id": "src1"},
                {"id": "ev2", "quote": "The mouse pleaded.", "source_id": "src1"},
            ],
            "original_source_excerpts": [{"text": "The lion was asleep. The mouse pleaded."}],
            "bible": {
                "logline": "The mouse pleaded and later rescued the lion.",
                "characters": [
                    {
                        "id": "lion",
                        "appearance": "golden",
                        "source_facts": "Catches the mouse then releases it",
                    }
                ],
                "style_instruction": "watercolor",
            },
        },
        {"source_event_ids": ["ev1"]},
    )
    assert "pleaded" not in str(result)
    assert "Catches" not in str(result)
    assert "golden" in str(result) and "The lion was asleep." in str(result)


def test_audio_script_preserves_complete_sentences_across_generation_units():
    from storycompiler.planning import apply_audio_script

    shots = [shot_payload() | {"id": "a"}, shot_payload() | {"id": "b"}]
    apply_audio_script(
        shots,
        [
            {
                "shot_id": "a",
                "kind": "narration",
                "speaker": "narrator",
                "end_shot_id": "b",
                "text": "The lion slept peacefully while the mouse wandered through the forest.",
            }
        ],
        {"lion", "mouse"},
    )
    assert len(shots[0]["speech"][0]["text"].split()) > 8
    assert shots[1]["speech"] == []


def test_scene_audio_contract_constrains_model_to_real_shots_and_speakers():
    from storycompiler.contracts import scene_audio_schema

    schema = scene_audio_schema(["s1", "s2"], ["lion", "mouse"])
    with pytest.raises(ValueError):
        schema.model_validate(
            {
                "lines": [
                    {
                        "kind": "dialogue",
                        "speaker": "invented",
                        "shot_id": "s1",
                        "end_shot_id": "s2",
                        "text": "Hello",
                    }
                ]
            }
        )
    with pytest.raises(ValueError):
        schema.model_validate(
            {
                "lines": [
                    {
                        "kind": "narration",
                        "speaker": "narrator",
                        "shot_id": "s1",
                        "end_shot_id": "other-scene",
                        "text": "Hello",
                    }
                ]
            }
        )
