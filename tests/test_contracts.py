import importlib.util
import pytest


def api():
    assert importlib.util.find_spec('storycompiler.contracts'), 'Production contracts are missing'
    assert importlib.util.find_spec('storycompiler.validation'), 'Plan gates are missing'
    from storycompiler import contracts as c, validation as v
    return c, v


def shot_payload():
    return dict(id='sh1',scene_id='sc1',bible_hash='abc',source_event_ids=['ev1'],
                purpose='ACTION',narrative_focus='The mouse is released',visual_focus='lifting paw',
                characters=['c1'],location_id='l1',action='The lion lifts his paw.',
                duration=4,camera=dict(size='CU',angle='eye level',movement='static',motivation='show release'),
                performance=[dict(character_id='c1',intent='release',behavior='opens paw slowly')],
                blocking='paw at screen left',start_state={'paw':'closed'},end_state={'paw':'open'},
                state_reason='The lion lifts its paw',locked=['golden mane'],allowed_changes=['paw position'],
                sound=dict(ambience='leaves rustle',foley='paw brushing grass'),
                narration='The lion let the mouse go.',edit='Cut on the paw lifting')


def test_continuity_gate_catches_unmotivated_state_reset():
    c,v = api()
    a=c.ShotPlan(**shot_payload())
    b=a.model_copy(update={'id':'sh2','start_state':{'paw':'closed'}})
    errors=v.validate_shots([a,b], 'abc', {'ev1'}, {'c1'}, {'l1'})
    assert any('continuity' in e.lower() for e in errors)


def test_plan_gate_rejects_stale_bible_unknown_character_and_uncovered_source():
    c,v=api()
    shot=c.ShotPlan(**shot_payload())
    errors=v.validate_shots([shot], 'new-hash', {'ev1','ev2'}, {'other'}, {'l1'})
    assert any('bible' in e.lower() for e in errors)
    assert any('character' in e.lower() for e in errors)
    assert any('ev2' in e for e in errors)


def test_compiler_keeps_action_and_identity_and_never_silently_truncates():
    c,v=api()
    from storycompiler.compiler import compile_shot
    shot=c.ShotPlan(**shot_payload())
    bible={'characters':[{'id':'c1','name':'Lion','appearance':'golden mane'}],
           'locations':[{'id':'l1','name':'Forest','appearance':'acacia clearing'}],
           'style_instruction':'Watercolor on paper'}
    prompt=compile_shot(shot,bible,limit=4000)
    assert 'The lion lifts his paw' in prompt and 'golden mane' in prompt
    assert 'acacia clearing' in prompt and 'paw' in prompt
    with pytest.raises(ValueError,match='budget'):
        compile_shot(shot,bible,limit=15)


def test_episode_duration_and_provider_capabilities_are_hard_gates():
    c,v=api()
    shot=c.ShotPlan(**shot_payload()).model_copy(update={'duration':21})
    assert v.validate_timeline([shot],60,max_clip_seconds=8)
    good=[c.ShotPlan(**shot_payload()).model_copy(update={'id':f's{i}'}) for i in range(15)]
    assert v.validate_timeline(good,60,max_clip_seconds=8) == []

