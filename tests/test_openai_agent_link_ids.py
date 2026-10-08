"""Adapter link identity through public functions and temporary synthetic stores."""
import json
from datetime import datetime
import pytest
from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.openai_agents import create_vibe_tools


@pytest.fixture
def library(tmp_path, monkeypatch):
    ids = ('11111111-0000-0000-0000-000000000001',
           '11111111-0000-0000-0000-000000000002',
           '22222222-0000-0000-0000-000000000003')
    path = str(tmp_path / 'memory.db')
    with VibeMemory(agent_id='adapter-test', db_path=path, embedding_backend='tfidf') as memory:
        with monkeypatch.context() as patch:
            fixed = iter(ids)
            patch.setattr('uuid.uuid4', lambda: next(fixed))
            for index in range(3):
                memory.store(f'合成证据{index}', session_id=f'synthetic-{index}',
                             auto_build_edges=False, auto_episode=False)
        with VibeMemory(agent_id='adapter-test', db_path=path, embedding_backend='tfidf') as tool_memory:
            tools = {tool.__name__: tool for tool in create_vibe_tools(memory=tool_memory)}
            yield memory, tools, ids


@pytest.mark.parametrize('endpoint', ['from_id', 'to_id'])
def test_ambiguous_prefix_rejected_without_creating_edge(library, endpoint):
    memory, tools, ids = library
    arguments = dict(from_id=ids[2], to_id=ids[0], label='causal')
    arguments[endpoint] = '11111111'
    result = json.loads(tools['vibe_link'](**arguments))
    assert 'ambiguous' in result.get('error', '').lower()
    assert json.loads(tools['vibe_stats']())['total_edges'] == 0


@pytest.mark.parametrize('source,target,short_endpoint', [
    (0, 1, None), (2, 0, 'from_id'), (1, 2, 'to_id')])
def test_full_and_unique_prefix_link_use_requested_endpoints(library, source, target, short_endpoint):
    memory, tools, ids = library
    arguments = dict(from_id=ids[source], to_id=ids[target], label='causal')
    if short_endpoint:
        arguments[short_endpoint] = arguments[short_endpoint][:8]
    result = json.loads(tools['vibe_link'](**arguments))
    assert result['status'] == 'created'
    edges = memory.storage.get_edges_between(ids[source], ids[target])
    assert [(edge.from_atom_id, edge.to_atom_id) for edge in edges] == [(ids[source], ids[target])]


@pytest.mark.parametrize('created_at', [datetime(2000, 1, 1), datetime(2099, 1, 1)])
def test_exact_eight_character_id_is_not_shadowed(library, created_at):
    memory, tools, ids = library
    memory.storage.insert_atom(MemoryAtom(
        id='11111111', agent_id=memory.agent_id, tenant_id=memory.tenant_id,
        session_id='synthetic-exact', content='精确短ID证据', summary='精确短ID证据',
        created_at=created_at))
    result = json.loads(tools['vibe_link'](from_id='11111111', to_id=ids[2], label='causal'))
    assert result['status'] == 'created'
    edges = memory.storage.get_edges_between('11111111', ids[2])
    assert [(edge.from_atom_id, edge.to_atom_id) for edge in edges] == [('11111111', ids[2])]


def test_store_delivers_full_id_without_removing_display_id(library):
    memory, tools, ids = library
    result = json.loads(tools['vibe_store'](content='蓝鲸观测合成记录', session_id='synthetic-new'))
    assert result['id'] == result['full_id'][:8]
    assert memory.storage.get_atom(result['full_id']).content == '蓝鲸观测合成记录'


def test_recall_delivers_distinct_full_ids_for_colliding_display_ids(library):
    memory, tools, ids = library
    result = json.loads(tools['vibe_recall'](query='合成证据', top_k=10))
    assert {row['full_id'] for row in result['memories']} == set(ids)
    assert all(row['id'] == row['full_id'][:8] for row in result['memories'])
