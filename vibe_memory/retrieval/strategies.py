"""
Multi-strategy retrieval — parallel search strategies + RRF fusion

Strategies:
  - BM25: keyword-based exact matching (pure Python, zero deps)
  - Semantic: embedding cosine similarity (TF-IDF or sentence-transformers)
  - Graph: PPR graph walk along relationship edges
  - Temporal: time-range boosting (recent memories score higher)

Fusion:
  - RRF (Reciprocal Rank Fusion): merge ranked lists from multiple strategies
  - Reranker: optional cross-encoder or LLM scoring for final ranking

Usage:
    from vibe_memory.retrieval.strategies import BM25Strategy, SemanticStrategy
    from vibe_memory.retrieval.fusion import rrf_fusion, Reranker

    bm25 = BM25Strategy()
    bm25.fit(documents)
    results = bm25.search("API timeout", top_k=20)
"""

import math
import numpy as np
from typing import Optional, Callable
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════
# BM25 Strategy — pure Python, zero dependencies
# ═══════════════════════════════════════════════════════════════════

class BM25Strategy:
    """
    BM25 keyword search (Okapi BM25).

    Formula: score(q, d) = Σ IDF(qi) * (f(qi,d) * (k1+1)) / (f(qi,d) + k1 * (1 - b + b * |d|/avgdl))

    Args:
        k1: term frequency saturation (default 1.5)
        b: length normalization (default 0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: list[str] = []
        self._tokens: list[list[str]] = []
        self._doc_len: list[int] = []
        self._avgdl: float = 0.0
        self._idf: dict[str, float] = {}
        self._fitted = False

    def fit(self, documents: list[str]):
        """Build BM25 index from documents."""
        self._documents = documents
        self._tokens = [self._tokenize(d) for d in documents]
        self._doc_len = [len(t) for t in self._tokens]
        self._avgdl = sum(self._doc_len) / max(len(documents), 1)
        self._idf = self._compute_idf(self._tokens, len(documents))
        self._fitted = True

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """
        Search documents by BM25.

        Returns:
            [(doc_index, score), ...] sorted by score descending
        """
        if not self._fitted:
            return []

        query_tokens = self._tokenize(query)
        scores = []

        for i, doc_tokens in enumerate(self._tokens):
            score = self._score(query_tokens, doc_tokens, i)
            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase, split on non-alphanumeric."""
        import re
        return [t.lower() for t in re.findall(r'\w+', text) if len(t) > 1]

    def _compute_idf(self, tokens: list[list[str]], N: int) -> dict[str, float]:
        """Compute IDF for each term."""
        df = defaultdict(int)
        for doc_tokens in tokens:
            for token in set(doc_tokens):
                df[token] += 1

        idf = {}
        for token, count in df.items():
            idf[token] = math.log(1 + (N - count + 0.5) / (count + 0.5))
        return idf

    def _score(self, query_tokens: list[str], doc_tokens: list[str], doc_idx: int) -> float:
        """Score one document against query."""
        score = 0.0
        doc_len = self._doc_len[doc_idx]
        term_freq = defaultdict(int)
        for t in doc_tokens:
            term_freq[t] += 1

        for token in query_tokens:
            if token not in self._idf:
                continue
            f = term_freq.get(token, 0)
            if f == 0:
                continue
            idf = self._idf[token]
            numerator = f * (self.k1 + 1)
            denominator = f + self.k1 * (1 - self.b + self.b * doc_len / max(self._avgdl, 1))
            score += idf * numerator / denominator

        return score


# ═══════════════════════════════════════════════════════════════════
# Semantic Strategy
# ═══════════════════════════════════════════════════════════════════

class SemanticStrategy:
    """Embedding cosine similarity search."""

    def __init__(self, provider=None):
        from vibe_memory.embedding.provider import TfidfProvider
        self.provider = provider or TfidfProvider()

    def fit(self, documents: list[str]):
        if hasattr(self.provider, 'fit'):
            self.provider.fit(documents)

    def search(self, query: str, documents: list[str], top_k: int = 20) -> list[tuple[int, float]]:
        query_vec = self.provider.encode_query(query)
        doc_vecs = self.provider.encode(documents)

        from vibe_memory.embedding import index_flat
        indices, scores = index_flat(doc_vecs, query_vec, top_k=top_k)
        return [(i, float(s)) for i, s in zip(indices, scores) if i < len(documents) and s > 0]


# ═══════════════════════════════════════════════════════════════════
# Graph Strategy
# ═══════════════════════════════════════════════════════════════════

class GraphStrategy:
    """PPR graph walk retrieval."""

    def __init__(self, storage, mode: str = "precision"):
        self.storage = storage
        self.mode = mode

    def search(
        self,
        seed_atoms: list,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """
        PPR graph walk from seed atoms.

        Returns:
            [(atom_id, ppr_score), ...] sorted by score descending
        """
        from vibe_memory.retrieval.ppr import PPRConfig, personalized_pagerank

        if self.mode == "precision":
            config = PPRConfig.precision()
        elif self.mode == "recall":
            config = PPRConfig.recall()
        elif self.mode == "budget":
            config = PPRConfig.budget()
        else:
            config = PPRConfig()

        config.top_n = top_k
        scores = personalized_pagerank(seed_atoms, self.storage, config)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# ═══════════════════════════════════════════════════════════════════
# Temporal Strategy
# ═══════════════════════════════════════════════════════════════════

class TemporalStrategy:
    """
    Time-range boosting for recent memories.

    Args:
        decay_days: half-life in days (default 30)
        boost_window_days: memories within this window get full boost (default 7)
    """

    def __init__(self, decay_days: float = 30.0, boost_window_days: float = 7.0):
        self.decay_days = decay_days
        self.boost_window_days = boost_window_days

    def search(
        self,
        atoms: list,
        top_k: int = 20,
    ) -> list[tuple[int, float]]:
        """
        Score atoms by recency.

        Returns:
            [(atom_index, recency_score), ...]
        """
        from datetime import datetime
        now = datetime.now()
        scores = []

        for i, atom in enumerate(atoms):
            if hasattr(atom, 'created_at') and atom.created_at:
                age_days = (now - atom.created_at).total_seconds() / 86400
                if age_days <= self.boost_window_days:
                    score = 1.0
                else:
                    score = math.exp(-age_days * math.log(2) / self.decay_days)
            else:
                score = 0.5  # Unknown time → neutral
            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]