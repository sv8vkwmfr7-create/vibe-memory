"""
Embedding Module

向量化与相似度计算。支持：
- TF-IDF: 纯 numpy 零额外依赖（L1 baseline）
- SentenceTransformer: 语义 embedding（需要 pip install sentence-transformers）
- 统一接口：EmbeddingProvider
"""

from vibe_memory.embedding.tfidf import (
    TfidfVectorizer,
    cosine_similarity,
    index_flat,
)
from vibe_memory.embedding.provider import (
    EmbeddingProvider,
    TfidfProvider,
    SentenceTransformerProvider,
    create_provider,
)

__all__ = [
    "TfidfVectorizer",
    "cosine_similarity",
    "index_flat",
    "EmbeddingProvider",
    "TfidfProvider",
    "SentenceTransformerProvider",
    "create_provider",
]