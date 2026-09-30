import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel, GraphPartition, MemoryAtom


@pytest.fixture
def memory(tmp_path):
    mem = VibeMemory(agent_id='owner', tenant_id='tenant-a',
                     db_path=str(tmp_path / 'shared.db'))
    for prefix, agent, tenant in [
        ('own', 'owner', 'tenant-a'),
        ('agent', 'other', 'tenant-a'),
        ('tenant', 'owner', 'tenant-b'),
    ]:
        for number in (1, 2):
            mem.storage.insert_atom(MemoryAtom(
                id=f'{prefix}-{number}', agent_id=agent, tenant_id=tenant,
                session_id='shared', content=f'{prefix} content', summary='synthetic'))
    yield mem
    mem.storage.conn.close()


def snapshot(memory):
    return {table: [tuple(row) for row in memory.storage.conn.execute(
        f'SELECT * FROM {table} ORDER BY id')] for table in ('atoms', 'edges')}


@pytest.mark.parametrize('atom_id', ['agent-1', 'tenant-1', 'missing'])
@pytest.mark.parametrize('operation', ['update', 'migrate'])
def test_unowned_mutations_leave_database_unchanged(memory, atom_id, operation):
    before = snapshot(memory)
    if operation == 'update':
        assert memory.update(atom_id, content='unauthorized replacement') is None
    else:
        assert memory.migrate(atom_id, GraphPartition.PARAMETRIC) is False
    assert snapshot(memory) == before


@pytest.mark.parametrize('source, target', [
    ('own-1', 'agent-1'), ('agent-1', 'own-1'),
    ('agent-1', 'agent-2'), ('own-1', 'tenant-1'),
    ('tenant-1', 'own-1'), ('tenant-1', 'tenant-2'),
    ('own-1', 'missing'),
])
def test_link_requires_ownership_of_both_endpoints(memory, source, target):
    before = snapshot(memory)
    count = memory._edge_count
    assert memory.link(source, target, label=EdgeLabel.CAUSAL) is None
    assert snapshot(memory) == before
    assert memory._edge_count == count


@pytest.mark.parametrize('field, value', [
    ('id', 'agent-1'), ('tenant_id', 'tenant-b'), ('agent_id', 'other'),
    ('session_id', 'stolen'), ('type', GraphPartition.PARAMETRIC),
    ('version', 1000), ('created_at', None), ('lifecycle', 'archived'),
    ('episode_id', 'foreign-episode'), ('unknown_field', 'ignored'),
])
def test_update_cannot_retarget_atom_or_change_managed_fields(memory, field, value):
    before = snapshot(memory)
    with pytest.raises(ValueError, match='update fields'):
        memory.update('own-1', content='must not partially apply', **{field: value})
    assert snapshot(memory) == before


def test_owned_update_migrate_and_link_still_work(memory):
    before = snapshot(memory)
    atom = memory.update('own-1', content='authorized replacement', summary='new summary',
                         tags=['decision'], scope={'service': 'orders'},
                         confidence=0.8, weight=0.6, decay_rate=0.98)
    assert atom is not None
    assert atom.agent_id == 'owner' and atom.tenant_id == 'tenant-a'
    assert atom.version == 2
    assert memory.storage.get_atom('own-1').content == 'authorized replacement'
    assert memory.migrate('own-1', GraphPartition.PARAMETRIC) is True
    assert memory.storage.get_atom('own-1').type == GraphPartition.PARAMETRIC
    edge = memory.link('own-1', 'own-2', label=EdgeLabel.CAUSAL)
    assert edge is not None and edge.tenant_id == 'tenant-a'
    after = snapshot(memory)
    assert [row for row in after['atoms'] if row[0].startswith(('agent-', 'tenant-'))] == [
        row for row in before['atoms'] if row[0].startswith(('agent-', 'tenant-'))]
