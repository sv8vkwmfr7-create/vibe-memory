"""Boundaries of the offline prototype, not production relevance guarantees."""
import pytest

from experiments.precision_guard_probe import causal_neighborhood, evaluate
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.storage.sqlite_store import VibeStorage


@pytest.mark.parametrize('label,confidence,expected', [
    (EdgeLabel.CAUSAL, 1.0, {'a', 'b', 'c'}),
    (EdgeLabel.SIMILAR, 1.0, {'a'}),
    (EdgeLabel.CAUSAL, 0.01, {'a'}),
])
def test_neighborhood_respects_labels_strength_and_hop_limit(label, confidence, expected):
    store = VibeStorage(':memory:')
    try:
        for aid in ('a', 'b', 'c', 'd'):
            store.insert_atom(MemoryAtom(id=aid, agent_id='probe', session_id='test', content=aid, summary=aid))
        for source, target in (('a', 'b'), ('b', 'c'), ('c', 'd')):
            store.insert_edge(Edge(id=source + target, from_atom_id=source, to_atom_id=target,
                label=label, confidence=confidence))
        assert causal_neighborhood(store, 'probe', store.tenant_id, 'a', 2) == expected
    finally:
        store.conn.close()


def test_neighborhood_excludes_other_tenant():
    store = VibeStorage(':memory:')
    try:
        store.insert_atom(MemoryAtom(id='a', agent_id='probe', session_id='test', content='a', summary='a'))
        store.insert_atom(MemoryAtom(id='b', agent_id='probe', tenant_id='other', session_id='test', content='b', summary='b'))
        store.insert_edge(Edge(id='ab', from_atom_id='a', to_atom_id='b', label=EdgeLabel.CAUSAL))
        assert causal_neighborhood(store, 'probe', store.tenant_id, 'a', 2) == {'a'}
    finally:
        store.conn.close()


def test_graph_free_relevant_result_is_lost_by_strict_guard():
    data = {'atoms': [
        {'id': 'a', 'session_id': 'one', 'content': 'cache timeout incident'},
        {'id': 'b', 'session_id': 'two', 'content': 'cache timeout retry solution'},
    ], 'edges': [], 'queries': [
        {'text': 'cache timeout incident', 'relevant_ids': ['a', 'b'], 'negative_ids': []},
    ]}
    result = evaluate(data)['aggregates']
    assert result['baseline']['macro_recall'] == 1.0
    # This intentionally locks a counterexample: do not ship as a general filter.
    assert result['primary_causal_2hop']['macro_recall'] == 0.5
