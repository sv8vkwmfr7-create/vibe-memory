import json
from datetime import datetime, timedelta

import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import (
    Edge, EdgeLabel, EdgeStatus, GraphPartition, Lifecycle, MemoryAtom,
)


@pytest.fixture
def memory(tmp_path):
    mem = VibeMemory(agent_id='agent-a', tenant_id='tenant-a',
                     db_path=str(tmp_path / 'shared.db'))
    for prefix, tenant, agent in [
        ('local', 'tenant-a', 'agent-a'),
        ('tenant', 'tenant-b', 'agent-a'),
        ('agent', 'tenant-a', 'agent-b'),
    ]:
        for number in range(3):
            mem.storage.insert_atom(MemoryAtom(
                id=f'{prefix}-{number}', tenant_id=tenant, agent_id=agent,
                session_id='shared-session', content=f'{prefix} content',
                summary=f'{prefix} summary', tags=['shared-topic']))
        for number, status in enumerate(EdgeStatus):
            mem.storage.insert_edge(Edge(
                id=f'{prefix}-{status.value}', from_atom_id=f'{prefix}-{number}',
                to_atom_id=f'{prefix}-{(number + 1) % 3}', tenant_id=tenant,
                label=EdgeLabel.CAUSAL, status=status,
                weight=0.01 if status == EdgeStatus.ACTIVE else 0.8))
    # Malformed legacy edges must not count or be modified as owned edges.
    for edge_id, source, destination, tenant in [
        ('cross-agent', 'local-0', 'agent-0', 'tenant-a'),
        ('cross-tenant', 'local-0', 'tenant-0', 'tenant-a'),
        ('wrong-edge-tenant', 'local-0', 'local-2', 'tenant-b'),
        ('orphan', 'local-0', 'missing', 'tenant-a'),
    ]:
        mem.storage.insert_edge(Edge(
            id=edge_id, from_atom_id=source, to_atom_id=destination,
            tenant_id=tenant, label=EdgeLabel.SIMILAR, weight=0.01))
    yield mem
    mem.storage.conn.close()


def test_history_with_same_session_id_is_tenant_and_agent_scoped(memory):
    assert {a.id for a in memory.history('shared-session')} == {
        'local-0', 'local-1', 'local-2'}
    assert all(a.tenant_id == 'tenant-a' and a.agent_id == 'agent-a'
               for a in memory.history())


def test_storage_session_query_defaults_to_its_tenant(memory):
    atoms = memory.storage.get_atoms_by_session('shared-session')
    assert len(atoms) == 6
    assert all(a.tenant_id == 'tenant-a' for a in atoms)


def test_explicit_storage_session_scope_and_sdk_shared_database(memory):
    atoms = memory.storage.get_atoms_by_session(
        'shared-session', tenant_id='tenant-b', agent_id='agent-a')
    assert {a.id for a in atoms} == {'tenant-0', 'tenant-1', 'tenant-2'}
    db = memory.storage.conn.execute('PRAGMA database_list').fetchone()[2]
    other = VibeMemory(agent_id='agent-b', tenant_id='tenant-a', db_path=db)
    try:
        assert {a.id for a in other.history('shared-session')} == {
            'agent-0', 'agent-1', 'agent-2'}
        assert other.stats()['total_edges'] == 1
        assert other.stats()['pending_edges'] == 1
    finally:
        other.storage.conn.close()


def test_empty_session_id_is_a_specific_session(memory):
    memory.storage.insert_atom(MemoryAtom(
        id='empty-session', tenant_id='tenant-a', agent_id='agent-a',
        session_id='', content='empty', summary='empty'))
    assert [a.id for a in memory.history('')] == ['empty-session']


def test_equal_timestamp_session_atoms_keep_batch_position(memory):
    timestamp = datetime(2026, 9, 30, 12, 0)
    for atom_id, position in [('m-first', 1), ('a-second', 3), ('z-last', 5)]:
        memory.storage.insert_atom(MemoryAtom(
            id=atom_id, tenant_id='tenant-a', agent_id='agent-a',
            session_id='tied-session', content=f'position {position}',
            summary=f'position {position}', tags=['config'],
            created_at=timestamp, episode_position=position))
    atoms = memory.storage.get_atoms_by_session(
        'tied-session', agent_id='agent-a', tenant_id='tenant-a')
    assert [a.id for a in atoms] == ['m-first', 'a-second', 'z-last']
    memory._auto_episode_aggregation('tied-session')
    episode = memory.storage.get_episodes_by_session('tied-session')[0]
    assert episode.atom_ids == ['m-first', 'a-second', 'z-last']
    assert 'position 1' in episode.summary


def test_stats_and_indexer_only_count_owned_edges(memory):
    stats = memory.stats()
    assert stats['total_atoms'] == 3
    assert stats['total_edges'] == 1
    assert stats['pending_edges'] == 1
    assert stats['edge_labels'] == {EdgeLabel.CAUSAL.value: 1}
    assert stats['indexer']['total_edges_in_graph'] == 1
    assert memory.indexer.stats()['total_edges_in_graph'] == 1
    assert stats['metrics']['graph_size']['current']['edges'] == 1


def test_stats_count_owned_cold_archived_endpoints_not_only_recall_edges(memory):
    for atom_id, lifecycle in [('local-0', Lifecycle.COLD), ('local-1', Lifecycle.ARCHIVED)]:
        atom = memory.storage.get_atom(atom_id)
        atom.lifecycle = lifecycle
        memory.storage.update_atom(atom)
    stats = memory.stats()
    assert stats['total_edges'] == 1
    assert stats['pending_edges'] == 1


@pytest.mark.parametrize('tenant, agent, prefix', [
    ('tenant-a', 'agent-a', 'local'),
    ('tenant-b', 'agent-a', 'tenant'),
    ('tenant-a', 'agent-b', 'agent'),
])
def test_scoped_edge_query_checks_both_endpoints(memory, tenant, agent, prefix):
    edges = memory.storage.get_edges_by_agent(agent, tenant_id=tenant)
    assert {e.id for e in edges} == {
        f'{prefix}-{status.value}' for status in EdgeStatus}
    active = memory.storage.get_edges_by_agent(
        agent, tenant_id=tenant, status=EdgeStatus.ACTIVE)
    assert [e.id for e in active] == [f'{prefix}-active']


@pytest.mark.parametrize('dry_run', [False, True])
def test_gc_sparsify_cannot_modify_foreign_or_malformed_edges(memory, dry_run):
    before = {row['id']: tuple(row) for row in memory.storage.conn.execute('SELECT * FROM edges')}
    assert memory.gc.sparsify(dry_run=dry_run) == 2
    after = {row['id']: tuple(row) for row in memory.storage.conn.execute('SELECT * FROM edges')}
    for edge_id in before:
        if dry_run or not edge_id.startswith('local-'):
            assert after[edge_id] == before[edge_id]
    expected = EdgeStatus.ACTIVE if dry_run else EdgeStatus.STALE
    assert memory.storage.get_edge('local-active').status == expected


def test_full_gc_and_metrics_snapshot_are_scoped(memory):
    foreign_before = {
        row['id']: tuple(row) for row in memory.storage.conn.execute(
            "SELECT * FROM atoms WHERE id NOT LIKE 'local-%'")}
    result = memory.collect_garbage()
    assert result['errors'] == []
    assert result['sparsified_edges'] == 2
    foreign_after = {
        row['id']: tuple(row) for row in memory.storage.conn.execute(
            "SELECT * FROM atoms WHERE id NOT LIKE 'local-%'")}
    assert foreign_after == foreign_before
    assert memory.metrics.stats()['graph_size']['current']['edges'] == 0
    assert memory.storage.get_edge('tenant-active').status == EdgeStatus.ACTIVE
    assert memory.storage.get_edge('agent-active').status == EdgeStatus.ACTIVE


def test_full_gc_pool_migration_and_eviction_preserve_foreign_rows(memory):
    old = (datetime.now() - timedelta(days=70)).isoformat()
    memory.storage.conn.execute('UPDATE atoms SET weight = 0.01, created_at = ?', (old,))
    memory.storage.conn.commit()
    before = {row['id']: tuple(row) for row in memory.storage.conn.execute(
        "SELECT * FROM atoms WHERE id NOT LIKE 'local-%'")}
    memory.gc.partition_capacity = {GraphPartition.SESSION: 1}
    result = memory.collect_garbage()
    assert result['errors'] == []
    assert result['pool_evicted_atoms'] == 2
    assert result['evicted_atoms'] == 1
    assert memory.history() == []
    after = {row['id']: tuple(row) for row in memory.storage.conn.execute(
        "SELECT * FROM atoms WHERE id NOT LIKE 'local-%'")}
    assert after == before


def test_episode_aggregation_cannot_import_foreign_session_atoms(memory):
    memory._auto_episode_aggregation('shared-session')
    rows = memory.storage.conn.execute('SELECT * FROM episodes').fetchall()
    assert rows
    for row in rows:
        assert row['tenant_id'] == 'tenant-a'
        assert row['agent_id'] == 'agent-a'
        assert set(json.loads(row['atom_ids'])) <= {'local-0', 'local-1', 'local-2'}
