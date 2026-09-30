import json

import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom


@pytest.fixture
def memory():
    mem = VibeMemory(agent_id='owner', db_path=':memory:')
    for atom_id, agent, tenant in [
        ('abcdefgh-1111', 'owner', mem.tenant_id),
        ('abcdefgh-2222', 'owner', mem.tenant_id),
        ('uniqueid-3333', 'owner', mem.tenant_id),
        ('foreign1-4444', 'other', mem.tenant_id),
        ('foreign2-5555', 'owner', 'other-tenant'),
    ]:
        mem.storage.insert_atom(MemoryAtom(
            id=atom_id, agent_id=agent, tenant_id=tenant,
            session_id='s', content='synthetic memory', summary='synthetic'))
    yield mem
    mem.storage.conn.close()


@pytest.mark.parametrize('atom_id', ['', ' ', 'uniquei', 'abcdefgh', None, 123,
                                   'foreign1-4444', 'foreign1',
                                   'foreign2-5555', 'foreign2'])
def test_forget_rejects_unsafe_or_unowned_ids(memory, atom_id):
    before = memory.storage.conn.execute('SELECT id FROM atoms ORDER BY id').fetchall()
    assert memory.forget(atom_id) is False
    assert memory.storage.conn.execute('SELECT id FROM atoms ORDER BY id').fetchall() == before


@pytest.mark.parametrize('atom_id', ['uniqueid', 'uniqueid-3333', 'abcdefgh-1111'])
def test_forget_accepts_exact_or_unique_safe_prefix(memory, atom_id):
    full_id = 'uniqueid-3333' if atom_id.startswith('uniqueid') else atom_id
    assert memory.forget(atom_id) is True
    assert memory.storage.get_atom(full_id) is None


def test_openai_adapter_rejects_empty_and_short_id():
    from vibe_memory.openai_agents import create_vibe_tools
    tools = {tool.__name__: tool for tool in create_vibe_tools(db_path=':memory:')}
    atom_id = json.loads(tools['vibe_store']('synthetic important memory'))['id']
    for unsafe in ['', atom_id[:7]]:
        assert json.loads(tools['vibe_forget'](unsafe))['deleted'] is False
    assert json.loads(tools['vibe_stats']())['total_atoms'] == 1
    assert json.loads(tools['vibe_forget'](atom_id))['deleted'] is True
