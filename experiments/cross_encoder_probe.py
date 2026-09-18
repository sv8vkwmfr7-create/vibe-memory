"""Experiment-only wider-pool CrossEncoder reranking probe."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibe_memory.embedding import TfidfProvider


def run(model, corpus, candidate_pool_size=20, top_k=5):
    atoms = corpus['atoms']
    anonymous = {atom['id']: f'atom-{index}' for index, atom in enumerate(atoms)}
    provider = TfidfProvider()
    provider.fit([atom['content'] for atom in atoms])
    rows = []
    for query_index, query in enumerate(corpus['queries']):
        indices, _ = provider.search(
            query['text'], top_k=min(candidate_pool_size, len(atoms)))
        pairs = [(query['text'], atoms[index]['content']) for index in indices]
        started = time.perf_counter()
        scores = [float(score) for score in model.predict(pairs)]
        reranked = sorted(zip(indices, scores), key=lambda item: item[1], reverse=True)
        returned = [atoms[index]['id'] for index, _ in reranked[:top_k]]
        relevant = set(query['relevant_ids'])
        negatives = set(query.get('negative_ids', []))
        rows.append({
            'query_id': f'query-{query_index}',
            'recall': len(set(returned) & relevant) / len(relevant),
            'labeled_positive_precision': (
                len(set(returned) & relevant) / len(returned) if returned else 0),
            'negative_hits': sum(item in negatives for item in returned),
            'returned_ids': [anonymous[item] for item in returned],
            'rerank_ms': (time.perf_counter() - started) * 1000,
        })
    return {
        'conditions': {
            'candidate_source': 'TF-IDF',
            'candidate_pool_size': candidate_pool_size,
            'top_k': top_k,
            'labels': 'Assistant-authored development labels; not independent evaluation.',
            'production_default_changed': False,
        },
        'aggregates': {
            'macro_recall': sum(row['recall'] for row in rows) / len(rows),
            'macro_labeled_positive_precision': (
                sum(row['labeled_positive_precision'] for row in rows) / len(rows)),
            'queries_with_negative_hits': sum(bool(row['negative_hits']) for row in rows),
            'p95_rerank_ms': sorted(row['rerank_ms'] for row in rows)[
                max(0, (95 * len(rows) + 99) // 100 - 1)],
        },
        'rows': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--candidate-pool-size', type=int, default=20)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--output', type=Path)
    parser.add_argument('corpus', type=Path, nargs='+')
    args = parser.parse_args()

    from sentence_transformers import CrossEncoder

    load_started = time.perf_counter()
    model = CrossEncoder(str(args.model_dir), device='cpu')
    load_seconds = time.perf_counter() - load_started
    datasets = []
    for path in args.corpus:
        raw = path.read_bytes()
        data = json.loads(raw.decode('utf-8-sig'))
        if 'cases' in data:
            cases = []
            for case in data['cases']:
                result = run(model, case, args.candidate_pool_size, args.top_k)
                cases.append({'case_id': case['case_id'], **result})
            datasets.append({'name': path.name,
                'sha256': hashlib.sha256(raw).hexdigest(), 'cases': cases})
        else:
            datasets.append({'name': path.name,
                'sha256': hashlib.sha256(raw).hexdigest(),
                **run(model, data, args.candidate_pool_size, args.top_k)})
    report = json.dumps({
        'model': 'BAAI/bge-reranker-base',
        'model_dir': str(args.model_dir),
        'device': 'cpu',
        'model_load_seconds': load_seconds,
        'datasets': datasets,
    }, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(report + '\n', encoding='utf-8')
    else:
        print(report)


if __name__ == '__main__':
    main()
