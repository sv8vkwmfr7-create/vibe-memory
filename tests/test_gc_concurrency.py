from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier, Event, local

import pytest

from vibe_memory.models.memory_atom import Edge, EdgeLabel, EdgeStatus, Lifecycle, MemoryAtom
from vibe_memory.sdk import VibeMemory


def test_gc_survivor_decay_preserves_another_instances_update_and_reinforcement(tmp_path, monkeypatch):
    reached_clock, writer_done = Event(), Event()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            reached_clock.set()
            if not writer_done.wait(10):
                raise TimeoutError('concurrent writer did not finish')
            return now

    path = str(tmp_path / 'gc.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as collector, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as writer:
        atom = collector.store('synthetic old guide', auto_build_edges=False, auto_episode=False)
        atom.last_accessed = now - timedelta(days=2)
        atom.weight = 0.5
        collector.storage.update_atom(atom)
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(collector.collect_garbage)
            try:
                assert reached_clock.wait(10), 'GC did not reach the clock boundary'
                current = writer.storage.get_atom(atom.id)
                current.content = current.summary = 'synthetic corrected guide'
                writer.storage.update_atom(current)
                writer.storage.reinforce_atoms([atom.id], 'agent')
            finally:
                writer_done.set()
            assert future.result(timeout=10)['errors'] == []
        current = next(item for item in writer.history() if item.id == atom.id)
        assert current.content == current.summary == 'synthetic corrected guide'
        assert current.access_count == 1
        assert abs(current.weight - 0.6) < 1e-9


@pytest.mark.parametrize('initial_weight', [1.0, 0.051])
def test_gc_edge_cleanup_preserves_another_connections_metadata(tmp_path, monkeypatch, initial_weight):
    reached_clock, writer_done = Event(), Event()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            reached_clock.set()
            if not writer_done.wait(10):
                raise TimeoutError('concurrent edge writer did not finish')
            return now

    path = str(tmp_path / 'edge.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as collector, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as writer:
        first = collector.store('synthetic guide', auto_build_edges=False, auto_episode=False)
        second = collector.store('synthetic appendix', auto_build_edges=False, auto_episode=False)
        edge = Edge(id='edge', from_atom_id=first.id, to_atom_id=second.id,
                    label=EdgeLabel.SIMILAR, last_accessed=now - timedelta(days=2),
                    weight=initial_weight)
        collector.storage.insert_edge(edge)
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(collector.collect_garbage)
            try:
                assert reached_clock.wait(10), 'GC did not reach the clock boundary'
                current = writer.storage.get_edge(edge.id)
                current.confidence, current.weight = 0.4, 0.6
                current.last_accessed = now
                writer.storage.update_edge(current)
            finally:
                writer_done.set()
            outcome = future.result(timeout=10)
            assert outcome['errors'] == []
            assert outcome['sparsified_edges'] == 0
        current = writer.storage.get_edge(edge.id)
        assert current.confidence == 0.4
        assert current.weight == 0.6
        assert current.last_accessed == now
        assert current.status == EdgeStatus.ACTIVE


def test_gc_capacity_evicts_unchanged_candidate_not_newly_reinforced_memory(tmp_path, monkeypatch):
    reached_clock, writer_done = Event(), Event()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            reached_clock.set()
            if not writer_done.wait(10):
                raise TimeoutError('concurrent capacity writer did not finish')
            return now

    path = str(tmp_path / 'capacity.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as collector, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as writer:
        anchor = MemoryAtom(id='anchor', agent_id='agent', session_id='synthetic',
                            content='old guide', summary='old guide', weight=0.051,
                            created_at=now - timedelta(days=2),
                            last_accessed=now - timedelta(days=2))
        collector.storage.insert_atom(anchor)
        for index in range(1000):
            collector.storage.insert_atom(MemoryAtom(
                id=f'filler-{index}', agent_id='agent', session_id='synthetic',
                content='synthetic filler', summary='synthetic filler', weight=0.3,
                created_at=now))
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(collector.collect_garbage)
            try:
                assert reached_clock.wait(10), 'GC did not reach the clock boundary'
                current = writer.storage.get_atom(anchor.id)
                current.content = current.summary = 'corrected guide'
                current.weight = 0.6
                writer.storage.update_atom(current)
                writer.storage.reinforce_atoms([anchor.id], 'agent')
            finally:
                writer_done.set()
            outcome = future.result(timeout=10)
            assert outcome['errors'] == []
        current = writer.storage.get_atom(anchor.id)
        assert current is not None
        assert current.content == current.summary == 'corrected guide'
        assert current.access_count == 1
        assert abs(current.weight - 0.7) < 1e-9
        assert len(writer.history(limit=1002)) == 1000
        assert outcome['pool_evicted_atoms'] == 1


def test_gc_low_weight_eviction_preserves_a_concurrent_reinforcement(tmp_path, monkeypatch):
    reached_clock, writer_done = Event(), Event()
    now = datetime.now()
    clock_calls = 0

    class Clock(datetime):
        @classmethod
        def now(cls):
            nonlocal clock_calls
            clock_calls += 1
            if clock_calls == 2:
                reached_clock.set()
                if not writer_done.wait(10):
                    raise TimeoutError('concurrent eviction writer did not finish')
            return now

    path = str(tmp_path / 'eviction.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as collector, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as writer:
        anchor = MemoryAtom(id='anchor', agent_id='agent', session_id='synthetic',
                            content='old guide', summary='old guide', weight=0.051,
                            created_at=now - timedelta(days=2),
                            last_accessed=now - timedelta(days=2))
        collector.storage.insert_atom(anchor)
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(collector.collect_garbage)
            try:
                assert reached_clock.wait(10), 'GC did not reach the clock boundary'
                current = writer.storage.get_atom(anchor.id)
                current.content = current.summary = 'corrected guide'
                current.weight = 0.6
                writer.storage.update_atom(current)
                writer.storage.reinforce_atoms([anchor.id], 'agent')
            finally:
                writer_done.set()
            outcome = future.result(timeout=10)
            assert outcome['errors'] == []
        current = writer.storage.get_atom(anchor.id)
        assert current is not None
        assert current.content == current.summary == 'corrected guide'
        assert current.access_count == 1
        assert abs(current.weight - 0.7) < 1e-9
        assert outcome['evicted_atoms'] == 0


@pytest.mark.parametrize('age_days', [10, 40, 90])
def test_gc_lifecycle_preserves_a_concurrently_updated_and_accessed_memory(tmp_path, monkeypatch, age_days):
    reached_clock, writer_done = Event(), Event()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            return cls.fromisoformat(now.isoformat())

        def __lt__(self, other):
            reached_clock.set()
            if not writer_done.wait(10):
                raise TimeoutError('concurrent lifecycle writer did not finish')
            return super().__lt__(other)

    path = str(tmp_path / 'lifecycle.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as collector, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as writer:
        anchor = MemoryAtom(id='anchor', agent_id='agent', session_id='synthetic',
                            content='old guide', summary='old guide', weight=0.5,
                            decay_rate=1.0, created_at=now - timedelta(days=age_days),
                            last_accessed=now - timedelta(days=age_days))
        collector.storage.insert_atom(anchor)
        monkeypatch.setattr('vibe_memory.gc.datetime', Clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(collector.collect_garbage)
            try:
                assert reached_clock.wait(10), 'GC did not reach the clock boundary'
                current = writer.storage.get_atom(anchor.id)
                current.content = current.summary = 'corrected guide'
                writer.storage.update_atom(current)
                writer.storage.reinforce_atoms([anchor.id], 'agent')
            finally:
                writer_done.set()
            outcome = future.result(timeout=10)
            assert outcome['errors'] == []
        current = writer.storage.get_atom(anchor.id)
        assert current.content == current.summary == 'corrected guide'
        assert current.lifecycle == Lifecycle.ACTIVE
        assert current.access_count == 1
        assert abs(current.weight - 0.6) < 1e-9
        assert outcome['migrated_to_warm'] == 0
        assert outcome['migrated_to_cold'] == 0
        assert outcome['migrated_to_archived'] == 0


def test_two_concurrent_gcs_consume_each_decay_period_only_once(tmp_path, monkeypatch):
    first_access = Barrier(2)
    clock_state = local()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            if not getattr(clock_state, 'started', False):
                clock_state.started = True
                first_access.wait(timeout=10)
            return now

    path = str(tmp_path / 'dual-gc.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as first, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as second:
        for atom_id in ('first', 'second'):
            first.storage.insert_atom(MemoryAtom(
                id=atom_id, agent_id='agent', session_id='synthetic',
                content='synthetic guide', summary='synthetic guide', weight=0.5,
                last_accessed=now - timedelta(days=2)))
        first.storage.insert_edge(Edge(
            id='edge', from_atom_id='first', to_atom_id='second',
            label=EdgeLabel.SIMILAR, last_accessed=now - timedelta(days=2)))
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(memory.collect_garbage) for memory in (first, second)]
            for future in futures:
                assert future.result(timeout=10)['errors'] == []
        for atom in second.history():
            assert abs(atom.weight - 0.45125) < 1e-9
            assert atom.last_decayed_at == now
            assert atom.last_accessed == now - timedelta(days=2)
            assert atom.access_count == 0
        edge = second.storage.get_edge('edge')
        assert abs(edge.weight - 0.9025) < 1e-9
        assert edge.last_decayed_at == now
        assert edge.last_accessed == now - timedelta(days=2)


def test_two_gcs_do_not_evict_below_partition_capacity(tmp_path, monkeypatch):
    snapshots_ready = Barrier(2)
    first_done = Event()
    clock_state = local()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            if not getattr(clock_state, 'started', False):
                clock_state.started = True
                snapshots_ready.wait(timeout=10)
                if clock_state.role == 'second' and not first_done.wait(10):
                    raise TimeoutError('first capacity GC did not finish')
            return now

    def collect(memory, role):
        clock_state.role = role
        try:
            return memory.collect_garbage()
        finally:
            if role == 'first':
                first_done.set()

    path = str(tmp_path / 'dual-pool.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as first, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as second:
        first.storage.insert_atom(MemoryAtom(
            id='anchor', agent_id='agent', session_id='synthetic',
            content='synthetic anchor', summary='synthetic anchor', weight=0.2,
            created_at=now - timedelta(days=2), last_accessed=now - timedelta(days=2)))
        for index in range(1000):
            first.storage.insert_atom(MemoryAtom(
                id=f'filler-{index}', agent_id='agent', session_id='synthetic',
                content='synthetic filler', summary='synthetic filler', weight=0.3,
                created_at=now))
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(collect, memory, role)
                       for memory, role in ((first, 'first'), (second, 'second'))]
            results = [future.result(timeout=10) for future in futures]
        assert all(result['errors'] == [] for result in results)
        assert len(second.history(limit=1002)) == 1000
        assert sum(result['pool_evicted_atoms'] for result in results) == 1
        assert second.storage.get_atom('anchor') is None


def test_gc_does_not_evict_after_another_connection_frees_pool_space(tmp_path, monkeypatch):
    reached_clock, writer_done = Event(), Event()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            reached_clock.set()
            if not writer_done.wait(10):
                raise TimeoutError('concurrent pool writer did not finish')
            return now

    path = str(tmp_path / 'freed-pool.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as collector, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as writer:
        collector.storage.insert_atom(MemoryAtom(
            id='anchor', agent_id='agent', session_id='synthetic',
            content='synthetic anchor', summary='synthetic anchor', weight=0.2,
            created_at=now - timedelta(days=2), last_accessed=now - timedelta(days=2)))
        for index in range(1000):
            collector.storage.insert_atom(MemoryAtom(
                id=f'filler-{index}', agent_id='agent', session_id='synthetic',
                content='synthetic filler', summary='synthetic filler', weight=0.3,
                created_at=now))
        for index in range(3):
            collector.storage.insert_atom(MemoryAtom(
                id=f'other-agent-{index}', agent_id='other-agent', session_id='synthetic',
                content='protected other agent', summary='protected other agent',
                created_at=now))
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(collector.collect_garbage)
            try:
                assert reached_clock.wait(10), 'GC did not reach the clock boundary'
                writer.storage.delete_atom('filler-0')
            finally:
                writer_done.set()
            outcome = future.result(timeout=10)
        assert outcome['errors'] == []
        assert outcome['pool_evicted_atoms'] == 0
        assert len(writer.history(limit=1002)) == 1000
        assert writer.storage.get_atom('anchor') is not None
        assert len(writer.storage.get_atoms_by_agent('other-agent')) == 3


@pytest.mark.parametrize('initial_count', [1000, 1001])
def test_gc_capacity_accounts_for_a_concurrent_new_memory(tmp_path, monkeypatch, initial_count):
    reached_clock, writer_done = Event(), Event()
    now = datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls):
            reached_clock.set()
            if not writer_done.wait(10):
                raise TimeoutError('concurrent insertion did not finish')
            return now

    path = str(tmp_path / 'insert-pool.db')
    with VibeMemory('agent', db_path=path, embedding_backend='tfidf', journal_mode='wal') as collector, \
            VibeMemory('agent', db_path=path, embedding_backend='tfidf') as writer:
        collector.storage.insert_atom(MemoryAtom(
            id='anchor', agent_id='agent', session_id='synthetic',
            content='synthetic anchor', summary='synthetic anchor', weight=0.2,
            created_at=now - timedelta(days=2), last_accessed=now - timedelta(days=2)))
        for index in range(initial_count - 1):
            collector.storage.insert_atom(MemoryAtom(
                id=f'filler-{index}', agent_id='agent', session_id='synthetic',
                content='synthetic filler', summary='synthetic filler', weight=0.3,
                created_at=now))
        monkeypatch.setattr('vibe_memory.models.memory_atom.datetime', Clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(collector.collect_garbage)
            try:
                assert reached_clock.wait(10), 'GC did not reach the clock boundary'
                fresh = MemoryAtom(id='fresh', agent_id='agent', session_id='synthetic',
                                   content='new confirmed policy', summary='new confirmed policy',
                                   weight=1.0, created_at=now)
                writer.storage.insert_atom(fresh)
            finally:
                writer_done.set()
            outcome = future.result(timeout=10)
        assert outcome['errors'] == []
        assert len(writer.history(limit=1003)) == 1000
        assert outcome['pool_evicted_atoms'] == (1 if initial_count == 1000 else 2)
        assert writer.storage.get_atom(fresh.id).content == 'new confirmed policy'
        assert writer.storage.get_atom('anchor') is None
