"""Public behavior of the experiment-only hybrid embedding provider."""

import os

import numpy as np
import pytest

from experiments.hybrid_embedding_probe import (
    HybridEmbeddingProvider,
    compare_corpus,
    working_set_bytes,
)
from vibe_memory.embedding import EmbeddingProvider, index_flat


class FixedProvider(EmbeddingProvider):
    def __init__(self, documents, query, name):
        self._documents = np.array(documents, dtype=float)
        self._query = np.array(query, dtype=float)
        self._name = name

    def encode(self, texts):
        return self._documents

    def encode_query(self, query):
        return self._query

    @property
    def dim(self):
        return self._documents.shape[1]

    @property
    def name(self):
        return self._name


def test_hybrid_provider_combines_lexical_and_semantic_scores():
    lexical = FixedProvider([[1, 0], [0, 1]], [1, 0], 'lexical')
    semantic = FixedProvider([[1, 0], [0, 1]], [0, 1], 'semantic')
    provider = HybridEmbeddingProvider(semantic, lexical_provider=lexical,
        lexical_weight=0.25)

    vectors = provider.encode(['lexical match', 'semantic match'])
    indices, scores = index_flat(vectors, provider.encode_query('query'), top_k=2)

    assert indices == [1, 0]
    assert scores == pytest.approx([0.75, 0.25])
    assert provider.name == 'hybrid-0.25-lexical+semantic'


def test_compare_corpus_reports_all_three_methods_and_recall_latency():
    data = {'atoms': [
        {'id': 'a', 'session_id': 'one', 'content': 'cache timeout'},
        {'id': 'b', 'session_id': 'two', 'content': 'connection pool'},
    ], 'edges': [], 'queries': [
        {'text': 'cache timeout', 'relevant_ids': ['a'], 'negative_ids': ['b']},
    ]}
    semantic = FixedProvider([[1, 0], [0, 1]], [1, 0], 'semantic')

    result = compare_corpus(data, semantic, lexical_weight=0.5)

    assert set(result) == {'tfidf', 'semantic', 'hybrid'}
    assert all(method['baseline']['p95_recall_ms'] >= 0 for method in result.values())


@pytest.mark.skipif(os.name != 'nt', reason='Windows working-set implementation')
def test_working_set_measurement_is_available_on_windows():
    assert working_set_bytes() > 0
