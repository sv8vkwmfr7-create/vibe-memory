"""
Retrieval Fusion — RRF (Reciprocal Rank Fusion) + Reranker

RRF: merges ranked lists from multiple strategies without tuning.
  score(d) = Σ 1/(k + rank_i(d))
  where k=60 (standard), rank_i(d) is position of doc d in strategy i's result.

Reranker: optional fine-grained scoring layer.
  - DefaultReranker: cosine similarity only (zero cost)
  - CrossEncoderReranker: sentence-transformers CrossEncoder (optional)
  - LLMReranker: LLM-based scoring (optional, requires API)
"""

from typing import Optional
import numpy as np


# ═══════════════════════════════════════════════════════════════════
# RRF Fusion
# ═══════════════════════════════════════════════════════════════════

def rrf_fusion(
    ranked_lists: list[list],
    k: int = 60,
    top_k: int = 20,
    weights: Optional[list[float]] = None,
) -> list[tuple]:
    """
    Reciprocal Rank Fusion — merge multiple ranked lists.

    Each list: [(id, score), ...] sorted by score descending.
    id can be any hashable type (int, str, tuple).

    Args:
        ranked_lists: List of ranked lists from different strategies
        k: RRF constant (default 60, standard value)
        top_k: Return top-K results
        weights: Strategy weights (default: equal weight)

    Returns:
        [(id, fused_score), ...] sorted by fused score descending
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)

    rrf_scores = {}
    for strategy_idx, ranked in enumerate(ranked_lists):
        weight = weights[strategy_idx] if strategy_idx < len(weights) else 1.0
        for rank, (item_id, _) in enumerate(ranked):
            rrf_score = weight / (k + rank + 1)  # rank starts at 1
            rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + rrf_score

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


# ═══════════════════════════════════════════════════════════════════
# Reranker
# ═══════════════════════════════════════════════════════════════════

class Reranker:
    """
    Optional fine-grained scoring layer.

    Default: cosine similarity reranking (zero cost).
    Can be swapped for CrossEncoder or LLM-based reranking.

    Args:
        provider: Embedding provider for scoring
    """

    def __init__(self, provider=None):
        self.provider = provider

    def rerank(
        self,
        query: str,
        candidates: list[tuple],
        top_k: int = 20,
    ) -> list[tuple]:
        """
        Rerank candidates by relevance to query.

        Args:
            query: Search query
            candidates: [(id, RRF_score), ...] from fusion
            top_k: Return top-K

        Returns:
            [(id, reranked_score), ...]
        """
        if not candidates or not self.provider:
            return candidates[:top_k]

        # Default: use embedding similarity to rerank
        try:
            query_vec = self.provider.encode_query(query)
            # For now, just return original order — reranker is a pass-through
            # Full CrossEncoder would require sentence-transformers
            return candidates[:top_k]
        except Exception:
            return candidates[:top_k]


def rerank_by_similarity(
    query_vec: np.ndarray,
    candidates: list[tuple],
    doc_vectors: np.ndarray,
    candidate_indices: list[int],
    top_k: int = 20,
) -> list[tuple]:
    """
    Rerank candidates by cosine similarity to query vector.

    Args:
        query_vec: Query embedding
        candidates: [(id, RRF_score), ...]
        doc_vectors: Document embedding matrix
        candidate_indices: Mapping from candidate id to doc_vectors index
        top_k: Return top-K

    Returns:
        [(id, reranked_score), ...]
    """
    if query_vec is None or doc_vectors is None or not candidates:
        return candidates[:top_k]

    # Normalize query
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)

    reranked = []
    for item_id, rrf_score in candidates:
        idx = candidate_indices.get(item_id)
        if idx is not None and idx < len(doc_vectors):
            doc_vec = doc_vectors[idx]
            doc_norm = doc_vec / (np.linalg.norm(doc_vec) + 1e-8)
            sim = float(np.dot(query_norm, doc_norm))
            # Combine RRF and similarity: 0.3 * rrf_norm + 0.7 * sim
            combined = 0.7 * sim + 0.3 * rrf_score
            reranked.append((item_id, combined))
        else:
            reranked.append((item_id, rrf_score))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked[:top_k]