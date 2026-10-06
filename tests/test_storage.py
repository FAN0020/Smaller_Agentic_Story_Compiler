import importlib.util
import json
import pytest


def repository(tmp_path):
    assert importlib.util.find_spec('storycompiler.storage'), 'Durable storage is missing'
    from storycompiler.storage import Repository
    return Repository(tmp_path)


def test_projects_survive_new_process_instance_and_detect_stale_writes(tmp_path):
    repo=repository(tmp_path)
    p=repo.create_project('Story','A mouse freed a lion.',{'mode':'children'})
    restored=repository(tmp_path).get_project(p['id'])
    assert restored['source'] == 'A mouse freed a lion.'
    restored['status']='analyzed'
    repo.save_project(restored)
    with pytest.raises(ValueError,match='changed'):
        repo.save_project(p)


def test_duplicate_jobs_are_idempotent_and_restart_requires_explicit_resume(tmp_path):
    repo=repository(tmp_path)
    p=repo.create_project('Story','Long enough story text',{})
    a=repo.enqueue(p['id'],'analyze',{})
    b=repo.enqueue(p['id'],'analyze',{})
    assert a['id']==b['id']
    repo.update_job(a['id'],status='running',message='Working')
    repository(tmp_path).recover_jobs()
    job=repo.get_job(a['id'])
    assert job['status']=='interrupted'
    assert repo.next_job() is None


def test_one_active_mutation_per_project(tmp_path):
    repo=repository(tmp_path)
    p=repo.create_project('Story','Long enough story text',{})
    repo.enqueue(p['id'],'analyze',{})
    with pytest.raises(ValueError,match='active'):
        repo.enqueue(p['id'],'render',{})


def test_secret_store_encrypts_and_never_returns_secret_in_public_settings(tmp_path):
    assert importlib.util.find_spec('storycompiler.settings'), 'Secret boundary is missing'
    from storycompiler.settings import SettingsStore
    store=SettingsStore(tmp_path)
    store.update({'llm_provider':'openai','api_key':'sk-test-private-secret'})
    assert store.secret('openai')=='sk-test-private-secret'
    assert 'sk-test' not in json.dumps(store.public())
    assert b'sk-test-private-secret' not in (tmp_path/'secrets.enc').read_bytes()
    assert (tmp_path/'secret.key').stat().st_mode & 0o077 == 0

