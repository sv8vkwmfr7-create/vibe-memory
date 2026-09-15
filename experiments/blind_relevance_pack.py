"""Build a deterministic, label-free relevance review pack."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--review-csv', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--seed', required=True)
    args = parser.parse_args()

    source_bytes = args.corpus.read_bytes()
    corpus = json.loads(source_bytes.decode('utf-8'))
    atoms = corpus['atoms']
    queries = list(enumerate(corpus['queries']))
    queries.sort(key=lambda item: digest(
        f'{args.seed}|query|{item[0]}|{item[1]["text"]}'))

    fieldnames = [
        'query_id', 'query_text', 'candidate_id', 'candidate_text',
        'relevance', 'harmful', 'notes',
    ]
    rows = []
    query_map = []
    candidate_map = []
    for query_number, (query_index, query) in enumerate(queries, start=1):
        query_id = f'query-{query_number:03d}'
        query_map.append({'query_id': query_id, 'query_index': query_index})
        candidates = sorted(
            atoms,
            key=lambda atom: digest(
                f'{args.seed}|candidate|{query_index}|{atom["id"]}'),
        )
        for candidate_number, atom in enumerate(candidates, start=1):
            candidate_id = f'{query_id}-candidate-{candidate_number:03d}'
            rows.append({
                'query_id': query_id,
                'query_text': query['text'],
                'candidate_id': candidate_id,
                'candidate_text': atom['content'],
                'relevance': '',
                'harmful': '',
                'notes': '',
            })
            candidate_map.append({
                'query_id': query_id,
                'candidate_id': candidate_id,
                'atom_id': atom['id'],
            })

    args.review_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.review_csv.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        'version': 1,
        'source': args.corpus.name,
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'seed': args.seed,
        'query_map': query_map,
        'candidate_map': candidate_map,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(json.dumps({
        'queries': len(queries),
        'candidates_per_query': len(atoms),
        'review_csv': str(args.review_csv),
        'manifest': str(args.manifest),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
