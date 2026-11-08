from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from vibe_memory.models.memory_atom import (
    Edge, EdgeLabel, EdgeStatus, Lifecycle, MemoryAtom,
)
from vibe_memory.sdk import VibeMemory
from vibe_memory.storage.sqlite_store import VibeStorage


def _records(storage):
    return (
        [storage.get_atom(key) for key in ('first', 'old', 'weak')],
        [storage.get_edge(key) for key in ('survivor', 'weak-edge')],
    )


@pytest.fixture
def shared_memory(tmp_path):
    path = str(tmp_path / 'gc-transaction.db')
    now = datetime.now()
    recent = now - timedelta(days=2, hours=1)
    old = now - timedelta(days=40)
    with VibeMemory('gc-transaction', path, embedding_backend='tfidf',
                    journal_mode='wal') as memory:
        for key, weight, timestamp, rate in (
            ('first', 0.5, recent, 0.95),
            ('old', 0.5, old, 1.0),
            ('weak', 0.01, now, 0.95),
        ):
            memory.storage.insert_atom(MemoryAtom(
                key, 'gc-transaction', 'synthetic', 'original', 'original',
                weight=weight, decay_rate=rate,
                created_at=timestamp, last_accessed=timestamp))
        for key, source, target, weight in (
            ('survivor', 'first', 'old', 0.5),
            ('weak-edge', 'old', 'weak', 0.01),
        ):
            memory.storage.insert_edge(Edge(
                id=key, from_atom_id=source, to_atom_id=target,
                label=EdgeLabel.SIMILAR, weight=weight, last_accessed=recent))
        observer = VibeStorage(path)
        try:
            yield memory, observer
        finally:
            memory.storage.conn.rollback()
            observer.conn.close()


def _pending_change(memory):
    # SQL only seeds a real uncommitted caller write; assertions use public reads.
    memory.storage.conn.execute(
        'UPDATE atoms SET content=?, summary=? WHERE id=?',
        ('caller draft', 'caller draft', 'first'))


def _finish_and_check(memory, observer, before, finish):
    assert memory.storage.get_atom('first').content == 'caller draft'
    assert _records(observer) == before
    getattr(memory.storage.conn, finish)()
    atoms, edges = before
    expected_atoms = [
        replace(atom, content='caller draft', summary='caller draft')
        if finish == 'commit' and atom.id == 'first' else atom
        for atom in atoms
    ]
    assert _records(observer) == (expected_atoms, edges)
    assert _records(memory.storage) == (expected_atoms, edges)


@pytest.mark.parametrize('finish', ['rollback', 'commit'])
def test_sdk_gc_preserves_callers_uncommitted_write_and_transaction_choice(
        shared_memory, finish):
    memory, observer = shared_memory
    before = _records(observer)
    _pending_change(memory)

    outcome = memory.collect_garbage()

    assert observer.get_atom('first').content == 'original'
    assert any('open transaction' in error for error in outcome['errors'])
    assert outcome['total_cleaned'] == 0
    _finish_and_check(memory, observer, before, finish)


@pytest.mark.parametrize('finish', ['rollback', 'commit'])
@pytest.mark.parametrize('stage,low_edges', [
    ('sparsify', False),
    ('sparsify', True),
    ('enforce_pool', False),
    ('migrate_cold', False),
    ('evict', False),
], ids=['edge-decay', 'stale-edge', 'pool-decay', 'lifecycle', 'eviction-decay'])
def test_gc_stage_preserves_callers_transaction(shared_memory, stage, low_edges, finish):
    memory, observer = shared_memory
    if low_edges:
        edge = memory.storage.get_edge('survivor')
        edge.weight = 0.01
        memory.storage.update_edge(edge)
    before = _records(observer)
    _pending_change(memory)

    with pytest.raises(ValueError, match='open transaction'):
        getattr(memory.gc, stage)()

    _finish_and_check(memory, observer, before, finish)


@pytest.mark.parametrize('finish', ['rollback', 'commit'])
def test_dry_run_reads_callers_view_without_committing_or_rolling_it_back(
        shared_memory, finish):
    memory, observer = shared_memory
    before = _records(observer)
    _pending_change(memory)

    outcome = memory.collect_garbage(dry_run=True)

    assert outcome['errors'] == []
    assert outcome['sparsified_edges'] == 1
    assert outcome['evicted_atoms'] == 1
    assert outcome['migrated_to_cold'] == 1
    _finish_and_check(memory, observer, before, finish)


def test_normal_gc_persists_cleanup_and_does_not_repeat_decay(shared_memory):
    memory, observer = shared_memory

    outcome = memory.collect_garbage()

    assert outcome['errors'] == []
    assert outcome['sparsified_edges'] == 1
    assert outcome['evicted_atoms'] == 1
    assert outcome['migrated_to_cold'] == 1
    assert observer.get_atom('weak') is None
    assert observer.get_edge('weak-edge') is None
    assert observer.get_atom('old').lifecycle == Lifecycle.COLD
    assert observer.get_atom('first').weight == pytest.approx(0.45125)
    assert observer.get_edge('survivor').weight == pytest.approx(0.45125)
    assert observer.get_edge('survivor').status == EdgeStatus.ACTIVE
    after = _records(observer)

    repeated = memory.collect_garbage()

    assert repeated['errors'] == []
    assert repeated['total_cleaned'] == 0
    assert _records(observer) == after
