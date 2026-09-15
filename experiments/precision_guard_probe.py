"""Offline precision ablations; never installed in SDK/MCP or default recall."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from vibe_memory.embedding import TfidfProvider, index_flat
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.retrieval.ppr import recall
from vibe_memory.storage.sqlite_store import VibeStorage


def causal_neighborhood(storage, agent_id, tenant_id, primary, hops):
    """Experimental undirected, bounded causal neighborhood with live scope."""
    reached = {primary}
    frontier = {primary}
    for _ in range(hops):
        next_frontier = set()
        for edge in storage.get_retrieval_edges(agent_id, tenant_id, atom_ids=list(frontier)):
            if edge.label != EdgeLabel.CAUSAL or edge.weight * edge.confidence < 0.05:
                continue
            if edge.from_atom_id in frontier:
                next_frontier.add(edge.to_atom_id)
            if edge.to_atom_id in frontier:
                next_frontier.add(edge.from_atom_id)
        frontier = next_frontier - reached
        reached.update(frontier)
        if not frontier:
            break
    return reached


def guarded_causal_ids(storage, agent_id, tenant_id, baseline, semantic_ids, scores):
    """Experimental fallback gate; consensus does not prove correct anchors."""
    if len(semantic_ids) < 2 or any(scores.get(aid, 0) <= 0 for aid in semantic_ids[:2]):
        return list(baseline), 'insufficient_anchors'
    allowed = causal_neighborhood(storage, agent_id, tenant_id, semantic_ids[0], 2)
    if len(allowed) < 2:
        return list(baseline), 'no_causal_support'
    if semantic_ids[1] not in allowed:
        return list(baseline), 'anchor_disagreement'
    return [aid for aid in baseline if aid in allowed], 'filtered'


def evaluate(data, embedding_provider=None):
    store = VibeStorage(':memory:')
    anonymous = {a['id']: f'atom-{i}' for i, a in enumerate(data['atoms'])}
    try:
        for a in data['atoms']:
            store.insert_atom(MemoryAtom(id=a['id'], agent_id='probe',
                session_id=a['session_id'], content=a['content'], summary=a['content'],
                created_at=datetime(2026, 9, 14)))
        for i, e in enumerate(data['edges']):
            source, target = (e['from_atom_id'], e['to_atom_id']) if isinstance(e, dict) else e
            label = EdgeLabel(e['label']) if isinstance(e, dict) else EdgeLabel.CAUSAL
            store.insert_edge(Edge(id=f'edge-{i}', from_atom_id=source,
                to_atom_id=target, label=label))
        atoms = store.get_atoms_by_agent('probe')
        provider = embedding_provider or TfidfProvider()
        documents = [a.content for a in atoms]
        if isinstance(provider, TfidfProvider):
            provider.fit(documents)
            def rank(query):
                return provider.search(query, top_k=len(atoms))
        else:
            vectors = provider.encode(documents)
            def rank(query):
                return index_flat(vectors, provider.encode_query(query), top_k=len(atoms))
        rows = []
        for i, q in enumerate(data['queries']):
            indices, similarities = rank(q['text'])
            scores = {atoms[index].id: float(score) for index, score in zip(indices, similarities)}
            primary = atoms[indices[0]].id
            baseline = [a.id for a in recall(q['text'], 'probe', store, top_k=5,
                embedding_provider=provider)['atoms']]
            variants = {'baseline': baseline, 'truncate_3': baseline[:3],
                'positive_similarity': [aid for aid in baseline if scores.get(aid, 0) > 0]}
            for hops in (1, 2):
                allowed = causal_neighborhood(store, 'probe', store.tenant_id, primary, hops)
                variants[f'primary_causal_{hops}hop'] = [aid for aid in baseline if aid in allowed]
            guarded, decision = guarded_causal_ids(store, 'probe', store.tenant_id, baseline,
                [atoms[index].id for index in indices], scores)
            variants['guarded_causal_2hop'] = guarded
            variants['evidence_preserving_causal_2hop'] = [aid for aid in baseline
                if aid in guarded or scores.get(aid, 0) > 0]
            positive, negative = set(q['relevant_ids']), set(q.get('negative_ids', []))
            for name, ids in variants.items():
                rows.append({'query_id': f'query-{i}', 'variant': name,
                    'recall': len(set(ids) & positive) / len(positive),
                    'labeled_positive_precision': len(set(ids) & positive) / len(ids) if ids else 0,
                    'returned_count': len(ids), 'returned_ids': [anonymous[x] for x in ids],
                    'negative_hits': [anonymous[x] for x in ids if x in negative],
                    'semantic_scores': {anonymous[x]: scores.get(x, 0) for x in baseline},
                    'primary_id': anonymous[primary]})
                if name == 'guarded_causal_2hop':
                    rows[-1]['guard_decision'] = decision
        aggregates = {}
        for name in variants:
            selected = [r for r in rows if r['variant'] == name]
            aggregates[name] = {
                'macro_recall': sum(r['recall'] for r in selected) / len(selected),
                'macro_labeled_positive_precision': sum(r['labeled_positive_precision'] for r in selected) / len(selected),
                'mean_returned_count': sum(r['returned_count'] for r in selected) / len(selected),
                'queries_with_negative_hits': sum(bool(r['negative_hits']) for r in selected)}
        provider_kind = 'TF-IDF' if isinstance(provider, TfidfProvider) else provider.name
        return {'conditions': f'Offline post-filter of production core precision Top-5. Assistant labels/manual edges. Primary {provider_kind} anchor, causal neighborhood ignores direction; no backfill or candidate expansion. Guard requires two positive {provider_kind} anchors in the primary two-hop causal neighborhood, otherwise preserves baseline. Evidence-preserving variant additionally retains every original candidate with positive {provider_kind} similarity; this is lexical/vector support, not semantic correctness. Zero-overlap relevant candidates can still be lost if outside the causal neighborhood. Anchor agreement is not correctness proof; jointly wrong anchors remain unsafe. Truncate-3 is post-truncation, not recall(top_k=3). Unlabeled items not assumed irrelevant. Consumed holdout is now diagnostic/development data, not fresh generalization evidence. Not SDK/MCP implementation or production latency proof.',
            'aggregates': aggregates, 'rows': rows}
    finally:
        store.conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path)
    args = parser.parse_args()
    raw = args.corpus.read_bytes()
    result = evaluate(json.loads(raw.decode('utf-8-sig')))
    result['corpus_sha256'] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result, indent=2))
