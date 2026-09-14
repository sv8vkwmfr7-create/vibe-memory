"""Run frozen public relevance cases; no model download or production mutation."""
import hashlib
import json
from pathlib import Path

from experiments.precision_guard_probe import evaluate
from vibe_memory.embedding import create_provider


def run(path):
    raw = path.read_bytes()
    data = json.loads(raw.decode('utf-8-sig'))
    rows = []
    for case in data['cases']:
        result = evaluate(case)
        baseline = next(r for r in result['rows'] if r['variant'] == 'baseline')
        guard = next(r for r in result['rows'] if r['variant'] == 'guarded_causal_2hop')
        preserving = next(r for r in result['rows'] if r['variant'] == 'evidence_preserving_causal_2hop')
        rows.append({'case_id': case['case_id'], 'candidate_count': len(case['atoms']),
            'baseline': baseline, 'guard': guard, 'evidence_preserving': preserving,
            'failure_stage': 'candidate_omission' if baseline['recall'] < 1
                else 'filter_deletion' if guard['recall'] < baseline['recall'] else 'none',
            'preserving_failure_stage': 'candidate_omission' if baseline['recall'] < 1
                else 'filter_deletion' if preserving['recall'] < baseline['recall'] else 'none'})
    provider = create_provider('auto')
    return {'conditions': data['provenance'], 'corpus_sha256': hashlib.sha256(raw).hexdigest(),
        'actual_auto_backend': provider.name,
        'semantic_model_evaluated': False,
        'rows': rows,
        'summary': {stage: sum(r['failure_stage'] == stage for r in rows)
                    for stage in ('candidate_omission', 'filter_deletion', 'none')},
        'evidence_preserving_summary': {stage: sum(r['preserving_failure_stage'] == stage for r in rows)
                    for stage in ('candidate_omission', 'filter_deletion', 'none')}}


if __name__ == '__main__':
    print(json.dumps(run(Path(__file__).with_name('relevance_diagnostic_cases.json')), indent=2))
