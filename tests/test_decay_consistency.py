from datetime import datetime, timedelta

import pytest

from vibe_memory.learner.learner import DecayManager
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom
from vibe_memory.sdk import VibeMemory


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        current = datetime(2026, 5, 3, 12)

        @classmethod
        def now(cls):
            return cls.current

    monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
    monkeypatch.setattr('vibe_memory.learner.learner.datetime', Clock)
    monkeypatch.setattr('vibe_memory.gc.datetime', Clock)
    monkeypatch.setattr('vibe_memory.storage.sqlite_store.datetime', Clock)
    return Clock


def test_atom_decay_consumes_each_complete_day_once_without_changing_access(clock):
    accessed = datetime(2026, 5, 1)
    atom = MemoryAtom(id='atom', agent_id='agent', session_id='session',
                      content='synthetic', summary='synthetic',
                      last_accessed=accessed, decay_rate=0.5)
    atom.decay()
    assert atom.weight == 0.25
    atom.decay()
    assert atom.weight == 0.25
    clock.current += timedelta(hours=12)
    atom.decay()
    assert atom.weight == 0.125
    assert atom.last_accessed == accessed


@pytest.mark.parametrize('through_manager', [False, True])
def test_edge_decay_consumes_each_complete_day_once(clock, through_manager):
    accessed = datetime(2026, 5, 1)
    edge = Edge(id='edge', from_atom_id='a', to_atom_id='b',
                label=EdgeLabel.SIMILAR, last_accessed=accessed, decay_rate=0.5)
    decay = (lambda: DecayManager().decay_edge(edge)) if through_manager else edge.decay
    decay()
    assert edge.weight == 0.25
    decay()
    assert edge.weight == 0.25
    clock.current += timedelta(hours=12)
    decay()
    assert edge.weight == 0.125
    assert edge.last_accessed == accessed


def test_decay_progress_survives_public_storage_update_and_reopen(tmp_path, clock):
    path = str(tmp_path / 'decay.db')
    accessed = datetime(2026, 5, 1)
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        atom = memory.store('synthetic copper guide', auto_build_edges=False, auto_episode=False)
        other = memory.store('synthetic appendix', auto_build_edges=False, auto_episode=False)
        edge = memory.link(atom.id, other.id)
        for item in (atom, edge):
            item.last_accessed = accessed
            item.decay_rate = 0.5
            item.decay()
        memory.storage.update_atom(atom)
        memory.storage.update_edge(edge)
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        for item in (memory.storage.get_atom(atom.id), memory.storage.get_edge(edge.id)):
            item.decay()
            assert item.weight == 0.25
            assert item.last_accessed == accessed


@pytest.mark.parametrize('kind', ['atom', 'edge'])
def test_reinforcement_starts_decay_at_real_access_not_old_processing_time(clock, kind):
    if kind == 'atom':
        item = MemoryAtom(id='a', agent_id='agent', session_id='s', content='synthetic', summary='synthetic')
    else:
        item = Edge(id='e', from_atom_id='a', to_atom_id='b', label=EdgeLabel.SIMILAR)
    item.last_accessed = datetime(2026, 5, 1)
    item.decay_rate = 0.5
    item.decay()
    item.reinforce()
    accessed = clock.current
    assert item.weight == pytest.approx(0.35)
    clock.current += timedelta(days=1)
    item.decay()
    item.decay()
    assert item.weight == pytest.approx(0.175)
    assert item.last_accessed == accessed


def test_atomic_storage_reinforcement_preserves_decay_progress_on_reopen(tmp_path, clock):
    path = str(tmp_path / 'reinforced.db')
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        atom = memory.store('synthetic copper guide', auto_build_edges=False, auto_episode=False)
        atom.last_accessed = datetime(2026, 5, 1)
        atom.decay_rate = 0.5
        atom.decay()
        memory.storage.update_atom(atom)
        memory.storage.reinforce_atoms([atom.id], 'agent')
    accessed = clock.current
    clock.current += timedelta(days=1)
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        item = memory.storage.get_atom(atom.id)
        item.decay()
        item.decay()
        assert item.weight == pytest.approx(0.175)
        assert item.last_accessed == accessed


def test_public_storage_insert_preserves_already_applied_decay(tmp_path, clock):
    path = str(tmp_path / 'inserted.db')
    atom = MemoryAtom(id='a', agent_id='agent', session_id='s', content='synthetic', summary='synthetic',
                      last_accessed=datetime(2026, 5, 1), decay_rate=0.5)
    edge = Edge(id='e', from_atom_id='a', to_atom_id='b', label=EdgeLabel.SIMILAR,
                last_accessed=datetime(2026, 5, 1), decay_rate=0.5)
    atom.decay()
    edge.decay()
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        memory.storage.insert_atom(atom)
        memory.storage.insert_atom(MemoryAtom(id='b', agent_id='agent', session_id='s',
                                             content='synthetic appendix', summary='synthetic appendix'))
        memory.storage.insert_edge(edge)
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        for item in (memory.storage.get_atom(atom.id), memory.storage.get_edge(edge.id)):
            item.decay()
            assert item.weight == 0.25
            clock.current += timedelta(hours=12)
            item.decay()
            assert item.weight == 0.125
            clock.current -= timedelta(hours=12)


def test_sdk_gc_persists_survivor_decay_once_and_dry_run_is_non_mutating(tmp_path, clock):
    path = str(tmp_path / 'gc.db')
    accessed = datetime(2026, 5, 1)
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        atom = memory.store('synthetic copper guide', auto_build_edges=False, auto_episode=False)
        other = memory.store('synthetic appendix', auto_build_edges=False, auto_episode=False)
        edge = memory.link(atom.id, other.id)
        for item in (atom, edge):
            item.last_accessed = accessed
            item.decay_rate = 0.5
        memory.storage.update_atom(atom)
        memory.storage.update_edge(edge)
        assert memory.collect_garbage(dry_run=True)['errors'] == []
        for item in (next(a for a in memory.history() if a.id == atom.id),
                     memory.storage.get_edge(edge.id)):
            assert item.weight == 1.0
        for _ in range(2):
            assert memory.collect_garbage()['errors'] == []
            assert memory.storage.get_atom(atom.id).weight == 0.25
            assert memory.storage.get_edge(edge.id).weight == 0.25
    with VibeMemory(agent_id='agent', db_path=path, embedding_backend='tfidf') as memory:
        clock.current += timedelta(hours=12)
        assert memory.collect_garbage(dry_run=True)['errors'] == []
        assert memory.storage.get_atom(atom.id).weight == 0.25
        assert memory.storage.get_edge(edge.id).weight == 0.25
        assert memory.collect_garbage()['errors'] == []
        for item in (memory.storage.get_atom(atom.id), memory.storage.get_edge(edge.id)):
            assert item.weight == 0.125
            assert item.last_accessed == accessed
