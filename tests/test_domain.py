"""Catch source loss, invalid selections, broken inheritance and unfilmable timelines."""
import importlib.util
import pytest


def domain():
    assert importlib.util.find_spec('storycompiler.domain') is not None, 'Validated domain is missing'
    from storycompiler import domain as d
    return d


def test_source_chunks_cover_unicode_input_without_truncation():
    d = domain()
    source = ('第一章\n\nThe mouse frees the lion.\n\n' * 1000).strip()
    chunks = d.chunk_source(source, limit=600)
    assert ''.join(c.text for c in chunks) == source
    assert len({c.id for c in chunks}) == len(chunks)
    assert max(len(c.text) for c in chunks) <= 600


@pytest.mark.parametrize('mode,count,custom,want', [
    ('one', 8, [], [1]), ('five', 8, [], [1,2,3,4,5]),
    ('five', 2, [], [1,2]), ('all', 3, [], [1,2,3]),
    ('custom', 8, [5,2,2], [2,5]),
])
def test_episode_selection_is_valid_and_deduplicated(mode,count,custom,want):
    assert domain().select_episodes(mode,count,custom) == want


@pytest.mark.parametrize('custom', [[],[0],[9],[-1]])
def test_selection_rejects_unavailable_episodes(custom):
    with pytest.raises(ValueError):
        domain().select_episodes('custom',8,custom)


def test_director_policy_does_not_confuse_style_with_story_mode():
    d = domain()
    assert len(d.STYLES) >= 5
    general = d.CreativeBrief(mode='general',style='watercolor',target_seconds=60)
    children = d.CreativeBrief(mode='children',style='graphic-novel',target_seconds=240)
    assert general.policy.hook_latency_max_seconds < children.policy.hook_latency_max_seconds
    assert children.policy.age_range == '6–9'
    with pytest.raises(ValueError):
        d.CreativeBrief(target_seconds=241)


def test_freeze_hash_detects_nested_canon_changes():
    d = domain()
    bible = {'characters':[{'id':'c1','appearance':'brown fur'}],'genre':'fable'}
    frozen = d.fingerprint(bible)
    bible['characters'][0]['appearance'] = 'blue fur'
    assert frozen != d.fingerprint(bible)

