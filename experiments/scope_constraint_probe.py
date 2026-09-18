"""Experiment-only reranking by rare query scope tokens."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.precision_guard_probe import evaluate
from vibe_memory.retrieval.text_tokens import cjk_bigrams


_STRUCTURED_WORDS = {
    'production', 'staging', 'development', 'dev', 'test', 'testing', 'uat',
    'prod', 'export', 'import', 'deploy', 'deployment', 'login', 'logout',
    'payment', 'checkout', 'upload', 'download', 'sync', 'preview', 'file',
}
_STRUCTURED_CJK = {'财务', '库存', '订单', '支付'}


def _tokens(text):
    return ([token for token in re.findall(r'[a-z0-9]+', text.lower())
             if len(token) >= 2] + cjk_bigrams(text))


def scope_rerank(query, documents, ranked_indices):
    document_tokens = [set(_tokens(document)) for document in documents]
    document_frequency = Counter(
        token for tokens in document_tokens for token in tokens)
    rare_limit = max(1, len(documents) // 4)
    scope_tokens = []
    for token in _tokens(query):
        if (0 < document_frequency[token] <= rare_limit
                and token not in scope_tokens):
            scope_tokens.append(token)
    if not scope_tokens:
        return {'indices': list(ranked_indices), 'scope_tokens': []}
    original_position = {index: position
                         for position, index in enumerate(ranked_indices)}
    ranked = sorted(ranked_indices, key=lambda index: (
        -sum(token in document_tokens[index] for token in scope_tokens),
        original_position[index],
    ))
    return {'indices': ranked, 'scope_tokens': scope_tokens}


def _structured_tokens(text):
    tokens = []
    for raw in re.findall(r'[A-Za-z][A-Za-z0-9_.:/-]*', text):
        normalized = raw.lower()
        if (normalized in _STRUCTURED_WORDS
                or raw != normalized
                or re.search(r'[-_.:/]', raw)):
            tokens.append(normalized)
    tokens.extend(token for token in _STRUCTURED_CJK if token in text)
    return tokens


def structured_scope_rerank(query, documents, ranked_indices):
    document_tokens = [set(_structured_tokens(document))
                       for document in documents]
    document_frequency = Counter(
        token for tokens in document_tokens for token in tokens)
    rare_limit = max(1, len(documents) // 4)
    scope_tokens = []
    for token in _structured_tokens(query):
        if (0 < document_frequency[token] <= rare_limit
                and token not in scope_tokens):
            scope_tokens.append(token)
    if not scope_tokens:
        return {'indices': list(ranked_indices), 'scope_tokens': []}
    original_position = {index: position
                         for position, index in enumerate(ranked_indices)}
    ranked = sorted(ranked_indices, key=lambda index: (
        -sum(token in document_tokens[index] for token in scope_tokens),
        original_position[index],
    ))
    return {'indices': ranked, 'scope_tokens': scope_tokens}


def run(corpus, top_k=5):
    documents = [atom['content'] for atom in corpus['atoms']]
    atom_ids = [atom['id'] for atom in corpus['atoms']]
    index_by_anonymous = {f'atom-{index}': index
                          for index in range(len(atom_ids))}
    baseline_rows = [row for row in evaluate(corpus)['rows']
                     if row['variant'] == 'baseline']
    rows = []
    for query_index, (query, baseline) in enumerate(
            zip(corpus['queries'], baseline_rows)):
        baseline_indices = [index_by_anonymous[item]
                            for item in baseline['returned_ids']]
        scoped = scope_rerank(query['text'], documents, baseline_indices)
        structured = structured_scope_rerank(
            query['text'], documents, baseline_indices)
        returned = [atom_ids[index] for index in scoped['indices'][:top_k]]
        structured_returned = [atom_ids[index]
                               for index in structured['indices'][:top_k]]
        baseline_returned = [atom_ids[index]
                             for index in baseline_indices[:top_k]]
        relevant = set(query['relevant_ids'])
        negatives = set(query.get('negative_ids', []))
        rows.append({
            'query_id': f'query-{query_index}',
            'scope_token_count': len(scoped['scope_tokens']),
            'structured_scope_token_count': len(structured['scope_tokens']),
            'baseline_top1_hit': bool(baseline_returned
                                      and baseline_returned[0] in relevant),
            'scope_top1_hit': bool(returned and returned[0] in relevant),
            'structured_scope_top1_hit': bool(
                structured_returned and structured_returned[0] in relevant),
            'baseline_top1_negative': bool(baseline_returned
                                           and baseline_returned[0] in negatives),
            'scope_top1_negative': bool(returned and returned[0] in negatives),
            'structured_scope_top1_negative': bool(
                structured_returned and structured_returned[0] in negatives),
            'scope_top_k_recall': len(set(returned) & relevant) / len(relevant),
            'structured_scope_top_k_recall': (
                len(set(structured_returned) & relevant) / len(relevant)),
            'ranking_changed': returned != baseline_returned,
            'structured_ranking_changed': structured_returned != baseline_returned,
            'returned_ids': [f'atom-{atom_ids.index(item)}' for item in returned],
        })
    return {
        'conditions': {
            'candidate_set': 'Unchanged production core baseline Top-5.',
            'rule': 'Stable boost by rare query tokens present in at most 25% of corpus documents.',
            'top_k': top_k,
            'labels': 'Assistant-authored development labels; not independent evaluation.',
            'production_default_changed': False,
        },
        'aggregates': {
            'baseline_top1_recall': sum(row['baseline_top1_hit'] for row in rows) / len(rows),
            'scope_top1_recall': sum(row['scope_top1_hit'] for row in rows) / len(rows),
            'structured_scope_top1_recall': (
                sum(row['structured_scope_top1_hit'] for row in rows) / len(rows)),
            'baseline_top1_negative_queries': sum(row['baseline_top1_negative'] for row in rows),
            'scope_top1_negative_queries': sum(row['scope_top1_negative'] for row in rows),
            'structured_scope_top1_negative_queries': sum(
                row['structured_scope_top1_negative'] for row in rows),
            'scope_macro_top_k_recall': sum(row['scope_top_k_recall'] for row in rows) / len(rows),
            'queries_with_scope_signal': sum(row['scope_token_count'] > 0 for row in rows),
            'queries_with_ranking_change': sum(row['ranking_changed'] for row in rows),
            'structured_scope_macro_top_k_recall': sum(
                row['structured_scope_top_k_recall'] for row in rows) / len(rows),
            'queries_with_structured_scope_signal': sum(
                row['structured_scope_token_count'] > 0 for row in rows),
            'queries_with_structured_ranking_change': sum(
                row['structured_ranking_changed'] for row in rows),
        },
        'rows': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--output', type=Path)
    parser.add_argument('corpus', type=Path, nargs='+')
    args = parser.parse_args()
    datasets = []
    for path in args.corpus:
        raw = path.read_bytes()
        data = json.loads(raw.decode('utf-8-sig'))
        if 'cases' in data:
            cases = [{'case_id': case['case_id'], **run(case, args.top_k)}
                     for case in data['cases']]
            datasets.append({'name': path.name,
                'sha256': hashlib.sha256(raw).hexdigest(), 'cases': cases})
        else:
            datasets.append({'name': path.name,
                'sha256': hashlib.sha256(raw).hexdigest(),
                **run(data, args.top_k)})
    report = json.dumps({'datasets': datasets}, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(report + '\n', encoding='utf-8')
    else:
        print(report)


if __name__ == '__main__':
    main()
