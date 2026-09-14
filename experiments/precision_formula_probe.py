"""Compare raw/max-normalized RRF without changing production ranking.

Optional private corpus is read only; output contains ordinal IDs, not text.
Both datasets use fresh core precision recall, not SDK/MCP session replay.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from experiments.retrieval_benchmark import build_dataset, AGENT_ID
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall
from vibe_memory.retrieval import fusion


def compare(store, agent, queries, anonymous, variants=('raw', 'max_normalized')):
    original = fusion.rerank_by_similarity
    original_fusion = fusion.rrf_fusion
    rows = []
    for ordinal, query in enumerate(queries):
        expected = set(query['relevant_ids'])
        outcomes = {}
        for variant in variants:
            supported = set()
            def capture_fusion(ranked_lists, *args, **kwargs):
                if variant == 'causal_bridge' and len(ranked_lists) >= 2:
                    # Require agreement of both lexical routes and two distinct
                    # anchors; a single cause edge or SIMILAR edge is insufficient.
                    anchors = {key for key, _ in ranked_lists[0]} & {
                        key for key, score in ranked_lists[1] if score > 0}
                    neighbors = {}
                    for edge in store.get_retrieval_edges(agent, atom_ids=list(anchors)):
                        if edge.label != EdgeLabel.CAUSAL or edge.weight * edge.confidence < 0.05:
                            continue
                        for node, anchor in ((edge.from_atom_id, edge.to_atom_id),
                                             (edge.to_atom_id, edge.from_atom_id)):
                            if anchor in anchors and node not in anchors:
                                neighbors.setdefault(node, set()).add(anchor)
                    supported.update(node for node, links in neighbors.items() if len(links) >= 2)
                return original_fusion(ranked_lists, *args, **kwargs)
            def rerank(query_vec, candidates, doc_vectors, candidate_indices, top_k=20):
                scale = max((score for _, score in candidates), default=0)
                if variant == 'max_normalized' and scale > 0:
                    candidates = [(key, score / scale) for key, score in candidates]
                ranked = original(query_vec, candidates, doc_vectors, candidate_indices,
                                  len(candidates) if variant == 'causal_bridge' else top_k)
                if variant == 'causal_bridge':
                    ranked.sort(key=lambda item: item[0] not in supported)
                return ranked[:top_k]
            with patch.object(fusion, 'rerank_by_similarity', rerank), patch.object(
                    fusion, 'rrf_fusion', capture_fusion):
                ids = [a.id for a in recall(query['text'], agent, store,
                                           mode='precision', top_k=5)['atoms']]
            hits = len(set(ids) & expected)
            outcomes[variant] = {'recall': hits / len(expected),
                                 'precision_at_5': hits / 5,
                                 'returned_ids': [anonymous[x] for x in ids]}
        if 'causal_bridge' in outcomes:
            baseline = set(outcomes['raw']['returned_ids'])
            labeled = {anonymous[x] for x in expected}
            outcomes['causal_bridge']['new_unlabeled_ids'] = [
                key for key in outcomes['causal_bridge']['returned_ids']
                if key not in baseline and key not in labeled]
        rows.append({'query_id': f'query-{ordinal}', **outcomes})
    return {'queries': len(rows), 'macro': {
        variant: {metric: sum(row[variant][metric] for row in rows) / len(rows)
                  for metric in ('recall', 'precision_at_5')}
        for variant in variants}, 'rows': rows}


def run(corpus=None, variants=('raw', 'max_normalized')):
    store, atoms, _, queries = build_dataset()
    # Existing benchmark is separately authored synthetic data, not independent human labels.
    public_queries = [{'text': q['query'], 'relevant_ids': q['relevant_ids']} for q in queries]
    try:
        result = {'synthetic_v3': compare(store, AGENT_ID, public_queries,
                                         {a.id: f'atom-{i}' for i, a in enumerate(atoms)}, variants)}
    finally:
        store.conn.close()
    if corpus:
        data = json.loads(corpus.read_text(encoding='utf-8-sig'))
        store = VibeStorage(':memory:')
        try:
            for a in data['atoms']:
                store.insert_atom(MemoryAtom(id=a['id'], agent_id='probe',
                    session_id=a['session_id'], content=a['content'], summary=a['summary'],
                    created_at=datetime(2026, 9, 14)))
            for i, edge in enumerate(data['edges']):
                store.insert_edge(Edge(id=f'edge-{i}', from_atom_id=edge['from_atom_id'],
                    to_atom_id=edge['to_atom_id'], label=EdgeLabel(edge['label']),
                    created_at=datetime(2026, 9, 14)))
            result['local_debug'] = compare(store, 'probe', data['queries'],
                {a['id']: f'atom-{i}' for i, a in enumerate(data['atoms'])}, variants)
        finally:
            store.conn.close()
    result['conditions'] = ('Fresh core precision Top-5; no reinforcement or automatic edges. '
        'Max normalization divides each fused score by the maximum before the existing reranker. '
        'Default production formula unchanged. Synthetic labels and local debug labels '
        'are not independent human quality evidence. Private text is never reported.')
    if 'causal_bridge' in variants:
        result['conditions'] += (' Experimental causal bridge promotes fused non-anchor nodes '
            'connected by qualifying CAUSAL edges to two distinct semantic/BM25 agreed anchors. '
            'Direction is ignored; no claim of cause-only relevance. Newly promoted unlabeled '
            'nodes are reported as review risks, not proven irrelevant without complete labels.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--causal-bridge', action='store_true',
                        help='Experiment only: promote fused nodes joining two lexical anchors by causal edges')
    args = parser.parse_args()
    variants = ('raw', 'causal_bridge') if args.causal_bridge else ('raw', 'max_normalized')
    print(json.dumps(run(args.corpus, variants), indent=2))
