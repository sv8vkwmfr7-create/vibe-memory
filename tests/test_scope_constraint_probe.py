"""Behavior of experiment-only scope-aware reranking."""

from experiments.scope_constraint_probe import scope_rerank


def test_unique_query_scope_moves_matching_candidate_without_deleting_anything():
    documents = [
        'request hangs in Catalog service',
        'restart Catalog service when request hangs',
        'Orders connection slots exhausted; enlarge pool capacity',
    ]

    result = scope_rerank('Orders request hangs', documents, [0, 1, 2])

    assert result['indices'] == [2, 0, 1]
    assert result['scope_tokens'] == ['orders']


def test_no_rare_scope_signal_preserves_existing_order():
    documents = ['payment slow one', 'payment slow two', 'unrelated answer']

    result = scope_rerank('payment slow', documents, [1, 0, 2])

    assert result == {'indices': [1, 0, 2], 'scope_tokens': []}
