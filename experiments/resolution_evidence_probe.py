"""Synthetic SDK ablations; never installed as a production ranking policy."""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from experiments.longmemeval_lexical_slot_probe import lexical_slot
from vibe_memory import VibeMemory
from vibe_memory.retrieval import fusion


ARMS = ('baseline', 'no_rerank', 'no_graph_vote', 'no_graph_no_rerank',
        'max_normalized', 'lexical_slot')
CASES = (
    ('resolution', '连接池耗尽导致接口超时，释放连接后恢复正常', {}, {}),
    ('negated', '连接池耗尽导致接口超时，释放连接未恢复正常', {}, {}),
    ('obsolete', '旧版连接池耗尽导致接口超时，释放连接后恢复', {}, {}),
    ('wrong_scope', '连接池耗尽导致接口超时，释放连接后恢复正常',
     {'service': 'billing'}, {'service': 'orders'}),
)


def scoped_lexical_slot(ids, lexical, atoms, query_scope):
    """Report-only scope gate; matching scope does not prove applicability."""
    if not lexical or not query_scope:
        return list(ids)
    winner = next((atom for atom in atoms if atom.id == lexical[0][0]), None)
    if winner is None or any(
            winner.scope.get(key, '').strip().casefold() != value.strip().casefold()
            for key, value in query_scope.items()):
        return list(ids)
    return lexical_slot(ids, lexical)


def diagnose(case, size, mode, arm):
    case_id, content, stored_scope, query_scope = case
    memory = VibeMemory(agent_id='resolution-probe', embedding_backend='tfidf')
    original_fusion = fusion.rrf_fusion
    original_rerank = fusion.rerank_by_similarity
    observed = {}
    try:
        # Fix randomness/time boundaries so displacement compares identical IDs/order.
        with patch('vibe_memory.sdk.uuid.uuid4', side_effect=[UUID(int=i + 1) for i in range(size)]), \
                patch('vibe_memory.sdk.datetime') as clock:
            clock.now.side_effect = [datetime(2026, 10, 3, 12) + timedelta(microseconds=i)
                                     for i in range(size)]
            atoms = [memory.store(content, scope=stored_scope, session_id='fixture',
                                  auto_build_edges=False, auto_episode=False)]
            for index in range(size - 1):
                atoms.append(memory.store(
                    f'接口超时连接池维护记录编号{index}，连接资源配置记录',
                    scope={'service': 'orders'}, session_id='fixture',
                    auto_build_edges=False, auto_episode=False))
        anonymous = {atom.id: f'atom-{index}' for index, atom in enumerate(atoms)}

        def capture_fusion(lists, *args, **kwargs):
            if len(lists) != 4:
                raise RuntimeError('Diagnostic requires four successful strategy lists')
            observed.update(zip(('semantic', 'bm25', 'graph', 'temporal'), lists))
            if arm in ('no_graph_vote', 'no_graph_no_rerank'):
                lists = [row for index, row in enumerate(lists) if index != 2]
            result = original_fusion(lists, *args, **kwargs)
            observed['fused'] = result
            return result

        def rerank(query, candidates, vectors, indices, top_k=20):
            if arm in ('no_rerank', 'no_graph_no_rerank'):
                return candidates[:top_k]
            if arm == 'max_normalized':
                scale = max((score for _, score in candidates), default=0)
                if scale > 0:
                    candidates = [(key, score / scale) for key, score in candidates]
            return original_rerank(query, candidates, vectors, indices, top_k)

        # Diagnostic instrumentation only; not internal mocks in correctness tests.
        with patch.object(fusion, 'rrf_fusion', capture_fusion), patch.object(
                fusion, 'rerank_by_similarity', rerank):
            result = memory.recall('接口超时如何修复连接池', mode=mode, top_k=5,
                                   scope=query_scope)
        ids = [atom.id for atom in result['atoms']]
        if arm == 'lexical_slot':
            # Report-side intervention after SDK scope boost, not an SDK policy.
            ids = lexical_slot(ids, observed['bm25'])
        elif arm == 'scoped_lexical_slot':
            ids = scoped_lexical_slot(ids, observed['bm25'], atoms, query_scope)
        target = atoms[0].id
        ranks = {}
        for name, ranked in observed.items():
            ranked_ids = [key for key, _ in ranked]
            ranks[name] = ranked_ids.index(target) + 1 if target in ranked_ids else None
        return {'case': case_id, 'size': size, 'mode': mode, 'arm': arm,
                'target_ranks': ranks,
                'ids': [anonymous[key] for key in ids],
                'target_hit': target in ids,
                'negative_hit': case_id not in ('resolution', 'resolution_scoped') and target in ids,
                'failures': result['failures']}
    finally:
        memory.storage.conn.close()


def run():
    rows = [diagnose(case, size, mode, arm) for case in CASES
            for size in (6, 100) for mode in ('precision', 'recall') for arm in ARMS]
    baseline = {(row['case'], row['size'], row['mode']): row for row in rows
                if row['arm'] == 'baseline'}
    for row in rows:
        control = baseline[(row['case'], row['size'], row['mode'])]
        row['new_negative'] = row['negative_hit'] and not control['negative_hit']
    return {'rows': rows, 'sdk_calls': len(rows), 'paid_api_calls': 0,
            'production_defaults_changed': False, 'evaluation_is_independent': False,
            'eligible_for_default': False,
            'limits': 'Assistant-authored synthetic expectations; fixed store UUIDs/microsecond '
                      'timestamps, fresh in-memory TF-IDF SDK per arm, '
                      'no graph edges, reinforcement not replayed across arms. Fixed Top-5 and no '
                      'parameter sweep. No latency/RSS, answer generation or real-host evidence. '
                      'Graph ablation removes its fusion vote only, retaining upstream computation. '
                      'Lexical slot reuses existing Top-5 helper after SDK scope boost; it is not '
                      'a production implementation. Non-triggered negative cases prove no safety. '
                      'Private blind labels remain paused.'}


def run_applicability():
    scope = {'service': 'orders', 'environment': 'production', 'operation': 'timeout'}
    cases = (
        CASES[0],  # Missing query scope: fail closed, not an inferred scope.
        ('resolution_scoped', CASES[0][1], scope, scope),
        ('negated', CASES[1][1], scope, scope),
        ('obsolete', CASES[2][1], scope, scope),
        ('wrong_scope', CASES[3][1], dict(scope, service='billing'), scope),
        ('missing_scope', CASES[0][1], {}, scope),
    )
    arms = ('baseline', 'lexical_slot', 'scoped_lexical_slot')
    rows = [diagnose(case, size, mode, arm) for case in cases
            for size in (6, 100) for mode in ('precision', 'recall') for arm in arms]
    baseline = {(row['case'], row['size'], row['mode']): row for row in rows
                if row['arm'] == 'baseline'}
    for row in rows:
        control = baseline[(row['case'], row['size'], row['mode'])]
        row['new_negative'] = row['negative_hit'] and not control['negative_hit']
        row['displaced_ids'] = [key for key in control['ids'] if key not in row['ids']]
    return {'rows': rows, 'sdk_calls': len(rows), 'paid_api_calls': 0,
            'production_defaults_changed': False, 'evaluation_is_independent': False,
            'eligible_for_default': False,
            'limits': 'Report-side scope gate, not production SDK logic. All queried scope keys '
                      'must match; no inferred service, outcome or validity labels. Missing scope '
                      'is unknown, not proven harmful: missing_scope negative_hit is an unsupported '
                      'promotion risk, not an independently judged wrong answer. Negated and obsolete '
                      'statements intentionally share the positive scope. Fixed assistant-authored '
                      'development fixtures, fixed store UUIDs/microsecond timestamps, fresh SDK '
                      'per arm, no graph/answers/latency/model calls. '
                      'Displaced IDs are mechanical changes, not proof of relevant evidence loss. '
                      'Original unscoped omission remains a required unresolved case.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, required=True)
    parser.add_argument('--applicability', action='store_true')
    args = parser.parse_args()
    report = run_applicability() if args.applicability else run()
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    arms = tuple(dict.fromkeys(row['arm'] for row in report['rows']))
    print(json.dumps({'sdk_calls': report['sdk_calls'], 'arms': {
        arm: {'resolution_hits': sum(row['target_hit'] for row in report['rows']
                                    if row['arm'] == arm and row['case'] in ('resolution', 'resolution_scoped')),
              'new_negative_rows': sum(row['new_negative'] for row in report['rows']
                                       if row['arm'] == arm)} for arm in arms}}))
