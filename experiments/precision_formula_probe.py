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


def compare(store, agent, queries, anonymous):
    original = fusion.rerank_by_similarity
    rows = []
    for ordinal, query in enumerate(queries):
        expected = set(query['relevant_ids'])
        variants = {}
        for variant in ('raw', 'max_normalized'):
            def rerank(query_vec, candidates, doc_vectors, candidate_indices, top_k=20):
                scale = max((score for _, score in candidates), default=0)
                if variant == 'max_normalized' and scale > 0:
                    candidates = [(key, score / scale) for key, score in candidates]
                return original(query_vec, candidates, doc_vectors, candidate_indices, top_k)
            with patch.object(fusion, 'rerank_by_similarity', rerank):
                ids = [a.id for a in recall(query['text'], agent, store,
                                           mode='precision', top_k=5)['atoms']]
            hits = len(set(ids) & expected)
            variants[variant] = {'recall': hits / len(expected),
                                 'precision_at_5': hits / 5,
                                 'returned_ids': [anonymous[x] for x in ids]}
        rows.append({'query_id': f'query-{ordinal}', **variants})
    return {'queries': len(rows), 'macro': {
        variant: {metric: sum(row[variant][metric] for row in rows) / len(rows)
                  for metric in ('recall', 'precision_at_5')}
        for variant in ('raw', 'max_normalized')}, 'rows': rows}


def run(corpus=None):
    store, atoms, _, queries = build_dataset()
    # Existing benchmark is separately authored synthetic data, not independent human labels.
    public_queries = [{'text': q['query'], 'relevant_ids': q['relevant_ids']} for q in queries]
    try:
        result = {'synthetic_v3': compare(store, AGENT_ID, public_queries,
                                         {a.id: f'atom-{i}' for i, a in enumerate(atoms)})}
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
                {a['id']: f'atom-{i}' for i, a in enumerate(data['atoms'])})
        finally:
            store.conn.close()
    result['conditions'] = ('Fresh core precision Top-5; no reinforcement or automatic edges. '
        'Max normalization divides each fused score by the maximum before the existing reranker. '
        'Default production formula unchanged. Synthetic labels and local debug labels '
        'are not independent human quality evidence. Private text is never reported.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.corpus), indent=2))
