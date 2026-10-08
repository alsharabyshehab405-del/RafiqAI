import asyncio
import os
import copy
import httpx
import pytest
import sys
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "unit-test-secret")
os.environ.setdefault("AI_BASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("AI_API_KEY", "unit-test-key")

from backend.app import config as _config
sys.modules.setdefault("backend.config", _config)
from backend.app import ai
from backend.app.services.ai_platform import ModelProfile
from backend.app.services.rag import reindex_file


def _profile(name, provider, *, tool_calling=True, structured_output=True, vision=True, quality=5, is_fallback=False):
    return ModelProfile(name, provider, 'http://provider.invalid', 'key', 8192, vision, True, tool_calling, structured_output, 4, True, 1.0, 1.0, quality, 4, 4, is_fallback)


def _run(coro):
    return asyncio.run(coro)


def test_chat_runtime_failover_primary_failure_fallback_success(monkeypatch):
    p1, p2 = _profile('m1', 'p1'), _profile('m2', 'p2')
    calls = []
    health = []

    class Adapter:
        def __init__(self, provider): self.provider = provider
        async def complete(self, *args, **kwargs):
            calls.append(self.provider)
            if self.provider == 'p1': raise httpx.ConnectError('primary down')
            return {'choices': [{'message': {'content': 'fallback ok'}}], 'usage': {}}

    monkeypatch.setattr(ai.router, 'candidates', lambda **kwargs: [p1, p2])
    monkeypatch.setattr(ModelProfile, 'adapter', lambda self: Adapter(self.provider))
    monkeypatch.setattr(ai, 'allowed', lambda provider: True)
    monkeypatch.setattr(ai, 'failure', lambda provider: health.append(('failure', provider)))
    monkeypatch.setattr(ai, 'success', lambda provider: health.append(('success', provider)))

    result = _run(ai.chat([{'role': 'user', 'content': 'hello'}]))
    assert result[0] == 'fallback ok'
    assert calls == ['p1', 'p2']
    assert health == [('failure', 'p1'), ('success', 'p2')]


def test_chat_runtime_failover_all_eligible_providers_fail(monkeypatch):
    p1, p2 = _profile('m1', 'p1'), _profile('m2', 'p2')
    calls = []

    class Adapter:
        def __init__(self, provider): self.provider = provider
        async def complete(self, *args, **kwargs):
            calls.append(self.provider)
            raise httpx.ConnectError(self.provider)

    monkeypatch.setattr(ai.router, 'candidates', lambda **kwargs: [p1, p2])
    monkeypatch.setattr(ModelProfile, 'adapter', lambda self: Adapter(self.provider))
    monkeypatch.setattr(ai, 'allowed', lambda provider: True)
    monkeypatch.setattr(ai, 'failure', lambda provider: None)

    with pytest.raises(httpx.ConnectError):
        _run(ai.chat([{'role': 'user', 'content': 'hello'}]))
    assert calls == ['p1', 'p2']


def test_chat_non_retryable_error_does_not_failover(monkeypatch):
    p1, p2 = _profile('m1', 'p1'), _profile('m2', 'p2')
    calls = []

    class Adapter:
        def __init__(self, provider): self.provider = provider
        async def complete(self, *args, **kwargs):
            calls.append(self.provider)
            raise ValueError('invalid request')

    monkeypatch.setattr(ai.router, 'candidates', lambda **kwargs: [p1, p2])
    monkeypatch.setattr(ModelProfile, 'adapter', lambda self: Adapter(self.provider))
    monkeypatch.setattr(ai, 'allowed', lambda provider: True)
    monkeypatch.setattr(ai, 'failure', lambda provider: None)

    with pytest.raises(ValueError, match='invalid request'):
        _run(ai.chat([{'role': 'user', 'content': 'hello'}]))
    assert calls == ['p1']


def test_chat_capability_filter_excludes_incapable_fallback():
    capable = _profile('capable', 'p1', tool_calling=True, quality=5)
    incapable = _profile('incapable', 'p2', tool_calling=False, quality=5)
    eligible = ai.router.candidates(plan='free', task='chat', preference='balanced', capabilities={'tool_calling'})
    # The runtime router must never return a profile lacking the requested capability.
    assert all(p.tool_calling for p in eligible)
    # A direct candidate set with the same policy also excludes the incapable fallback.
    original = ai.router.profiles
    try:
        ai.router.profiles = [capable, incapable]
        eligible = ai.router.candidates(plan='premium', capabilities={'tool_calling'})
        assert [p.provider for p in eligible] == ['p1']
    finally:
        ai.router.profiles = original


def test_chat_explicit_fallback_provider_is_eligible_for_free_plan(monkeypatch):
    primary = _profile('free-model', 'p1')
    fallback = _profile('fallback-model', 'p2', is_fallback=True)
    original = ai.router.profiles
    try:
        ai.router.profiles = [primary, fallback]
        eligible = ai.router.candidates(plan='free', capabilities=set())
        assert [p.provider for p in eligible] == ['p1', 'p2']
    finally:
        ai.router.profiles = original


def test_chat_does_not_attempt_same_provider_twice(monkeypatch):
    p1a, p1b, p2 = _profile('m1', 'p1'), _profile('m1-pro', 'p1'), _profile('m2', 'p2')
    calls = []

    class Adapter:
        def __init__(self, provider): self.provider = provider
        async def complete(self, *args, **kwargs):
            calls.append(self.provider)
            if self.provider == 'p1': raise httpx.ConnectError('down')
            return {'choices': [{'message': {'content': 'ok'}}], 'usage': {}}

    monkeypatch.setattr(ai.router, 'candidates', lambda **kwargs: [p1a, p1b, p2])
    monkeypatch.setattr(ModelProfile, 'adapter', lambda self: Adapter(self.provider))
    monkeypatch.setattr(ai, 'allowed', lambda provider: True)
    monkeypatch.setattr(ai, 'failure', lambda provider: None)
    monkeypatch.setattr(ai, 'success', lambda provider: None)

    assert _run(ai.chat([{'role': 'user', 'content': 'hello'}]))[0] == 'ok'
    assert calls == ['p1', 'p2']


def test_reindex_embedding_failure_preserves_old_index():
    old = [{'id': 'old:0', 'payload': {'file_id': 7, 'project_id': 9, 'index_version': 'old'}}]

    class Store:
        async def ensure_collection(self, *args): raise AssertionError('must not touch qdrant when embeddings are invalid')

    with pytest.raises(ValueError):
        _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='x', chunks=['a'], vectors=[]))
    assert old == [{'id': 'old:0', 'payload': {'file_id': 7, 'project_id': 9, 'index_version': 'old'}}]


def test_reindex_dimension_mismatch_preserves_old_index():
    class Store:
        async def ensure_collection(self, collection, dimension):
            raise ValueError('qdrant collection embedding dimension mismatch')

    with pytest.raises(ValueError, match='dimension'):
        _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='x', chunks=['a', 'b'], vectors=[[1, 2], [1, 2, 3]]))


def test_reindex_upsert_failure_never_deletes_old_index():
    events = []

    class Store:
        async def ensure_collection(self, *args): events.append('ensure')
        async def upsert(self, *args): events.append('upsert'); raise httpx.ConnectError('qdrant down')
        async def verify_points(self, *args, **kwargs): events.append('verify')
        async def delete_points(self, *args, **kwargs): events.append(('delete', kwargs))

    with pytest.raises(httpx.ConnectError):
        _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='x', chunks=['a'], vectors=[[1, 2]]))
    assert events[0:2] == ['ensure', 'upsert']
    assert events[2][0] == 'delete' and events[2][1]['index_version']
    assert events[2][1].get('exclude_index_version') is None


def test_reindex_success_removes_stale_and_keeps_new_metadata():
    state = [{'id': 'old:0', 'payload': {'file_id': 7, 'project_id': 9, 'index_version': 'old'}}]

    class Store:
        async def ensure_collection(self, *args): pass
        async def upsert(self, collection, items): state.extend(copy.deepcopy(items))
        async def verify_points(self, collection, **kwargs):
            matches=[p for p in state if p['payload']['index_version']==kwargs['index_version'] and p['payload']['file_id']==kwargs['file_id'] and p['payload']['project_id']==kwargs['project_id']]
            assert len(matches)==kwargs['expected_count']
        async def delete_points(self, collection, **kwargs):
            if kwargs.get('exclude_index_version'):
                state[:] = [p for p in state if p['payload']['index_version']==kwargs['exclude_index_version']]

    version = _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='new.txt', chunks=['a', 'b'], vectors=[[1, 2], [3, 4]], embedding_model='e1'))
    assert len(state) == 2
    assert all(p['payload']['index_version'] == version for p in state)
    assert all(p['payload']['file_id'] == 7 and p['payload']['project_id'] == 9 for p in state)
    assert [p['payload']['chunk'] for p in state] == [0, 1]
    assert all(p['payload']['embedding_model'] == 'e1' for p in state)


def test_reindex_retry_after_temporary_failure_finishes_without_stale_versions():
    state = [{'id': 'old:0', 'payload': {'file_id': 7, 'project_id': 9, 'index_version': 'old'}}]
    attempts = {'n': 0}

    class Store:
        async def ensure_collection(self, *args): pass
        async def upsert(self, collection, items):
            attempts['n'] += 1
            if attempts['n'] == 1: raise httpx.ConnectError('temporary')
            state.extend(copy.deepcopy(items))
        async def verify_points(self, collection, **kwargs):
            matches=[p for p in state if p['payload']['index_version']==kwargs['index_version']]
            assert len(matches)==kwargs['expected_count']
        async def delete_points(self, collection, **kwargs):
            if kwargs.get('index_version'):
                state[:] = [p for p in state if p['payload']['index_version'] != kwargs['index_version']]
            elif kwargs.get('exclude_index_version'):
                state[:] = [p for p in state if p['payload']['index_version']==kwargs['exclude_index_version']]

    with pytest.raises(httpx.ConnectError):
        _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='x', chunks=['a'], vectors=[[1, 2]]))
    version = _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='x', chunks=['a'], vectors=[[1, 2]]))
    assert attempts['n'] == 2
    assert len(state) == 1 and state[0]['payload']['index_version'] == version


def test_reindex_partial_upsert_failure_cleans_only_new_version_and_preserves_old():
    state = [{'id': 'old:0', 'payload': {'file_id': 7, 'project_id': 9, 'index_version': 'old'}}]

    class Store:
        async def ensure_collection(self, *args): pass
        async def upsert(self, collection, items):
            state.append(copy.deepcopy(items[0]))
            raise httpx.ConnectError('partial qdrant write')
        async def verify_points(self, *args, **kwargs): raise AssertionError('verification must not run after failed upsert')
        async def delete_points(self, collection, **kwargs):
            if kwargs.get('index_version'):
                state[:] = [p for p in state if p['payload']['index_version'] != kwargs['index_version']]

    with pytest.raises(httpx.ConnectError):
        _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='x', chunks=['a', 'b'], vectors=[[1, 2], [3, 4]]))
    assert len(state) == 1 and state[0]['payload']['index_version'] == 'old'


def test_reindex_verification_failure_preserves_old_index_and_removes_new_version():
    state = [{'id': 'old:0', 'payload': {'file_id': 7, 'project_id': 9, 'index_version': 'old'}}]

    class Store:
        async def ensure_collection(self, *args): pass
        async def upsert(self, collection, items): state.extend(copy.deepcopy(items))
        async def verify_points(self, *args, **kwargs): raise RuntimeError('verification failed')
        async def delete_points(self, collection, **kwargs):
            if kwargs.get('index_version'):
                state[:] = [p for p in state if p['payload']['index_version'] != kwargs['index_version']]

    with pytest.raises(RuntimeError, match='verification failed'):
        _run(reindex_file(Store(), 'c', file_id=7, project_id=9, filename='x', chunks=['a'], vectors=[[1, 2]]))
    assert len(state) == 1 and state[0]['payload']['index_version'] == 'old'
