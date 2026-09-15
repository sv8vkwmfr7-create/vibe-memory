"""Compare the downloaded local embedding model without changing production defaults."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.precision_guard_probe import evaluate
from vibe_memory.embedding.provider import SentenceTransformerProvider


def run(model_dir, corpora):
    provider = SentenceTransformerProvider(model_name=str(model_dir), device='cpu')
    if not provider.available:
        raise RuntimeError('sentence-transformers is unavailable')
    datasets = []
    for corpus in corpora:
        raw = corpus.read_bytes()
        data = json.loads(raw.decode('utf-8-sig'))
        if 'cases' in data:
            case_results = [{'case_id': case['case_id'],
                'aggregates': evaluate(case, embedding_provider=provider)['aggregates']}
                for case in data['cases']]
            datasets.append({'name': corpus.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                'cases': case_results})
        else:
            result = evaluate(data, embedding_provider=provider)
            datasets.append({'name': corpus.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                'aggregates': result['aggregates']})
    return {'model': 'BAAI/bge-small-zh-v1.5', 'model_dir': str(model_dir),
        'provider': provider.name, 'device': 'cpu',
        'conditions': 'Local model only; no SDK/MCP, no production configuration or defaults changed. Assistant-authored labels/manual edges; not independent evaluation. Setup/model loading excluded from per-query result because this probe reports retrieval behavior only.',
        'datasets': datasets}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=Path('models/bge-small-zh-v1.5'))
    parser.add_argument('corpus', type=Path, nargs='+')
    args = parser.parse_args()
    print(json.dumps(run(args.model_dir, args.corpus), indent=2, ensure_ascii=False))
