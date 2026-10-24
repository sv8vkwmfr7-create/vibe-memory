from datetime import datetime, timedelta

import pytest

from vibe_memory.models.memory_atom import Lifecycle, MemoryAtom
from vibe_memory.sdk import VibeMemory


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        current = datetime(2026, 1, 1)

        @classmethod
        def now(cls):
            return cls.current

    for module in ('vibe_memory.models.memory_atom', 'vibe_memory.gc',
                   'vibe_memory.storage.sqlite_store'):
        monkeypatch.setattr(f'{module}.datetime', Clock)
    return Clock


@pytest.mark.parametrize('accessed', [False, True])
def test_inactivity_safe_gc_preserves_records_and_edges_after_idle_reopen(tmp_path, clock, accessed):
    path = str(tmp_path / 'idle.db')
    with VibeMemory('idle', path, embedding_backend='tfidf',
                    retention_policy='inactivity_safe') as memory:
        atom = MemoryAtom('checkpoint', 'idle', 'session', 'copper project resume checkpoint',
                          'copper project resume checkpoint', created_at=clock.current)
        other = MemoryAtom('notes', 'idle', 'session', 'copper project deployment notes',
                           'copper project deployment notes', created_at=clock.current)
        memory.storage.insert_atom(atom)
        memory.storage.insert_atom(other)
        edge = memory.link(atom.id, other.id)
        for item in (atom, other, edge):
            item.weight = 0.5
            item.created_at = clock.current
            item.last_accessed = clock.current if accessed else None
        memory.storage.update_atom(atom)
        memory.storage.update_atom(other)
        memory.storage.update_edge(edge)
    clock.current += timedelta(days=180)
    with VibeMemory('idle', path, embedding_backend='tfidf',
                    retention_policy='inactivity_safe') as memory:
        for dry_run in (True, False, False):
            result = memory.collect_garbage(dry_run=dry_run)
            assert result['errors'] == []
            assert result['total_cleaned'] == 0
            assert result['migrated_to_archived'] == 0
            records = memory.history()
            assert {a.id for a in records} == {atom.id, other.id}
            for record in records:
                assert record.created_at == datetime(2026, 1, 1)
                assert record.weight == 0.5
                assert record.lifecycle == Lifecycle.ACTIVE
                assert record.last_accessed == atom.last_accessed
                assert record.last_decayed_at is None
            stored_edge = memory.storage.get_edge(edge.id)
            assert stored_edge.weight == 0.5
            assert stored_edge.last_accessed == edge.last_accessed
            assert stored_edge.last_decayed_at is None
        assert atom.id in {a.id for a in memory.recall('copper project resume checkpoint')['atoms']}


def test_legacy_default_still_archives_an_unaccessed_old_record(tmp_path, clock):
    with VibeMemory('legacy', str(tmp_path / 'legacy.db'), embedding_backend='tfidf') as memory:
        atom = MemoryAtom('old', 'legacy', 's', 'old copper checkpoint', 'old copper checkpoint',
                          created_at=clock.current)
        memory.storage.insert_atom(atom)
        clock.current += timedelta(days=180)
        assert memory.collect_garbage()['migrated_to_archived'] == 1
        assert memory.history()[0].lifecycle == Lifecycle.ARCHIVED


def test_inactivity_safe_gc_still_enforces_capacity(tmp_path, clock):
    with VibeMemory('pool', str(tmp_path / 'pool.db'), embedding_backend='tfidf',
                    retention_policy='inactivity_safe') as memory:
        for index in range(1001):
            memory.storage.insert_atom(MemoryAtom(str(index), 'pool', 's', 'synthetic copper',
                                                   'synthetic copper', created_at=clock.current))
        clock.current += timedelta(days=180)
        assert memory.collect_garbage(dry_run=True)['pool_evicted_atoms'] == 1
        assert len(memory.storage.get_atoms_by_agent('pool')) == 1001
        result = memory.collect_garbage()
        assert result['errors'] == []
        assert result['pool_evicted_atoms'] == 1
        assert len(memory.storage.get_atoms_by_agent('pool')) == 1000
        assert memory.collect_garbage()['pool_evicted_atoms'] == 0


@pytest.mark.parametrize('policy', ['', 'logical', None, True])
def test_unknown_retention_policy_is_rejected(tmp_path, policy):
    with pytest.raises(ValueError, match='retention_policy'):
        VibeMemory('invalid', str(tmp_path / 'invalid.db'), embedding_backend='tfidf',
                   retention_policy=policy)
