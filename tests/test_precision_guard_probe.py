"""Boundaries of the offline prototype, not production relevance guarantees."""
import pytest

from experiments.precision_guard_probe import causal_neighborhood, evaluate, guarded_causal_ids
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
    assert result['guarded_causal_2hop']['macro_recall'] == 1.0


@pytest.mark.parametrize('edges,semantic,reason', [
    ([], ['a', 'b'], 'no_causal_support'),
    ([('a', 'c')], ['a', 'b'], 'anchor_disagreement'),
])
def test_guard_falls_back_when_graph_missing_or_anchors_disagree(edges, semantic, reason):
    store = VibeStorage(':memory:')
    try:
        for aid in ('a', 'b', 'c'):
            store.insert_atom(MemoryAtom(id=aid, agent_id='probe', session_id='test', content=aid, summary=aid))
        for source, target in edges:
            store.insert_edge(Edge(id=source + target, from_atom_id=source,
                to_atom_id=target, label=EdgeLabel.CAUSAL))
        ids, decision = guarded_causal_ids(store, 'probe', store.tenant_id,
            ['a', 'b', 'c'], semantic, {aid: 1.0 for aid in semantic})
        assert ids == ['a', 'b', 'c']
        assert decision == reason
    finally:
        store.conn.close()


@pytest.mark.parametrize('semantic,scores', [([], {}), (['a'], {'a': 1}),
    (['a', 'b'], {'a': 1, 'b': 0})])
def test_guard_preserves_baseline_without_two_positive_anchors(semantic, scores):
    store = VibeStorage(':memory:')
    try:
        assert guarded_causal_ids(store, 'probe', store.tenant_id,
            ['a', 'b'], semantic, scores) == (['a', 'b'], 'insufficient_anchors')
    finally:
        store.conn.close()


def test_jointly_wrong_connected_anchors_remain_a_counterexample():
    store = VibeStorage(':memory:')
    try:
        for aid in ('wrong-a', 'wrong-b', 'answer'):
            store.insert_atom(MemoryAtom(id=aid, agent_id='probe', session_id='test', content=aid, summary=aid))
        store.insert_edge(Edge(id='edge', from_atom_id='wrong-a',
            to_atom_id='wrong-b', label=EdgeLabel.CAUSAL))
        ids, decision = guarded_causal_ids(store, 'probe', store.tenant_id,
            ['wrong-a', 'wrong-b', 'answer'], ['wrong-a', 'wrong-b', 'answer'],
            {'wrong-a': 0.9, 'wrong-b': 0.8, 'answer': 0.7})
        assert decision == 'filtered'
        assert 'answer' not in ids  # Agreement is not a safe general relevance test.
    finally:
        store.conn.close()


def test_real_tfidf_can_agree_on_wrong_issue_and_drop_answer():
    data = {'atoms': [
        {'id': 'billing-incident', 'session_id': 'billing',
            'content': 'cache timeout incident in unrelated billing app'},
        {'id': 'billing-fix', 'session_id': 'billing',
            'content': 'cache timeout incident restart billing app'},
        {'id': 'worker-answer', 'session_id': 'worker',
            'content': 'Worker connections exhausted; increase connection pool capacity'},
    ], 'edges': [('billing-incident', 'billing-fix')], 'queries': [
        {'text': 'cache timeout incident in worker', 'relevant_ids': ['worker-answer'],
            'negative_ids': ['billing-incident', 'billing-fix']},
    ]}
    result = evaluate(data)['aggregates']
    assert result['baseline']['macro_recall'] == 1.0
    # Real TF-IDF selects both billing atoms; the fallback gate still deletes the answer.
    assert result['guarded_causal_2hop']['macro_recall'] == 0.0
