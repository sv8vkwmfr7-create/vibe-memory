"""Read-only new-source corpus comparison; report no private text."""
import argparse
import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path
from time import perf_counter
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall


def evaluate(data):
    anonymous = {a['id']: f'atom-{i}' for i,a in enumerate(data['atoms'])}
    rows = []
    for i, q in enumerate(data['queries']):
        positive, negative = set(q['relevant_ids']), set(q['negative_ids'])
        if not positive or positive & negative or not positive | negative <= anonymous.keys():
            raise ValueError('Invalid labels')
        for flag in (False, True):
            times = []
            ranks = []
            for _ in range(5):
                store = VibeStorage(':memory:')
                try:
                    for a in data['atoms']:
                        store.insert_atom(MemoryAtom(id=a['id'], agent_id='holdout',
                            session_id=a['session_id'], content=a['content'], summary=a['content'],
                            created_at=datetime(2026, 9, 14)))
                    for j, (source, target) in enumerate(data['edges']):
                        store.insert_edge(Edge(id=f'edge-{j}', from_atom_id=source,
                            to_atom_id=target, label=EdgeLabel.CAUSAL))
                    start = perf_counter()
                    ids = [a.id for a in recall(q['text'], 'holdout', store,
                        top_k=5, causal_bridge=flag)['atoms']]
                    times.append((perf_counter() - start) * 1000)
                    ranks.append(ids)
                finally:
                    store.conn.close()
            rows.append({'query_id': f'query-{i}', 'causal_bridge': flag,
                'recall': len(set(ids) & positive) / len(positive),
                'precision_at_5': len(set(ids) & positive) / 5,
                'negative_hits': [anonymous[x] for x in ids if x in negative],
                'returned_ids': [anonymous[x] for x in ids],
                'repeat_ranking_stable': all(rank == ranks[0] for rank in ranks),
                'core_cold_p50_ms': statistics.median(times)})
    aggregates = {}
    for flag in (False, True):
        selected = [r for r in rows if r['causal_bridge'] == flag]
        aggregates[str(flag)] = {
            'macro_recall': statistics.mean(r['recall'] for r in selected),
            'macro_precision_at_5': statistics.mean(r['precision_at_5'] for r in selected),
            'queries_with_negative_hits': sum(bool(r['negative_hits']) for r in selected)}
    return {'conditions': 'New Wiki-source assistant paraphrases/labels/manual edges, not independent human labels. Fresh core precision Top-5, equal current creation timestamps, five cold calls per condition; setup excluded. No SDK cache, reinforcement, automatic edges, MCP, temporal cutoff or production latency proof. Private text omitted.',
            'aggregates': aggregates, 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path)
    args = parser.parse_args()
    raw = args.corpus.read_bytes()
    result = evaluate(json.loads(raw.decode('utf-8-sig')))
    result['corpus_sha256'] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result, indent=2))
