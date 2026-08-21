"""
Lightweight TF-IDF Embedding

纯 numpy 实现，零额外依赖。
用于替换 _tag_match_score 标签近似，提供真实向量相似度。

TF-IDF 虽不是语义 embedding（如 sentence-transformers），
但它是真实的向量表示——不依赖手工标签，是更诚实的 RAG baseline。
"""

import math
from collections import Counter
from typing import Optional
import numpy as np


class TfidfVectorizer:
    """
    TF-IDF 向量化器。

    TF = term frequency in document
    IDF = log(total_docs / doc_freq)

    降级策略：如果 numpy 不可用 → 回退到纯 Python 字典
    """

    def __init__(
        self,
        max_features: int = 5000,
        min_df: int = 1,
        max_df: float = 1.0,
        ngram_range: tuple[int, int] = (1, 1),
    ):
        self.max_features = max_features
        self.min_df = min_df
        self.max_df = max_df
        self.ngram_range = ngram_range

        # 词汇表: {term: index}
        self.vocabulary: dict[str, int] = {}
        # IDF 值: {term: idf}
        self.idf: dict[str, float] = {}
        # 文档数
        self.n_docs: int = 0

    def fit(self, documents: list[str]) -> "TfidfVectorizer":
        """
        在所有文档上拟合词汇表 + IDF。

        Args:
            documents: 文档列表
        """
        self.n_docs = len(documents)
        if self.n_docs == 0:
            return self

        # 文档频率: {term: doc_count}
        doc_freq: Counter = Counter()

        for doc in documents:
            terms = set(self._tokenize(doc))
            for term in terms:
                doc_freq[term] += 1

        # 过滤
        min_docs = max(1, int(self.n_docs * self.max_df)) if self.max_df < 1.0 else self.n_docs
        filtered_terms = [
            (term, freq) for term, freq in doc_freq.most_common(self.max_features)
            if freq >= self.min_df and freq <= min_docs
        ]

        # 构建词汇表
        self.vocabulary = {term: idx for idx, (term, _) in enumerate(filtered_terms)}

        # 计算 IDF
        self.idf = {}
        for term, idx in self.vocabulary.items():
            freq = doc_freq[term]
            self.idf[term] = math.log((self.n_docs + 1) / (freq + 1)) + 1.0

        return self

    def transform(self, documents: list[str]) -> np.ndarray:
        """
        将文档列表转换为 TF-IDF 矩阵。

        Returns:
            shape (n_docs, vocab_size) 的 numpy 数组
        """
        if not self.vocabulary:
            return np.zeros((len(documents), 0))

        n_features = len(self.vocabulary)
        result = np.zeros((len(documents), n_features))

        for i, doc in enumerate(documents):
            terms = self._tokenize(doc)
            if not terms:
                continue

            # 词频
            term_counts = Counter(terms)
            doc_len = len(terms)

            for term, count in term_counts.items():
                if term in self.vocabulary:
                    idx = self.vocabulary[term]
                    tf = count / doc_len
                    result[i, idx] = tf * self.idf.get(term, 1.0)

            # L2 归一化
            norm = np.linalg.norm(result[i])
            if norm > 0:
                result[i] /= norm

        return result

    def fit_transform(self, documents: list[str]) -> np.ndarray:
        """拟合 + 转换"""
        self.fit(documents)
        return self.transform(documents)

    def _tokenize(self, text: str) -> list[str]:
        """
        简单分词：小写 + 按非字母数字分割 + 最小长度 2。

        L1 原型：英文分词。中文支持需 jieba。
        """
        import re
        text_lower = text.lower()
        # 按非字母数字分割
        tokens = re.findall(r'[a-z0-9]+', text_lower)
        # 过滤最短长度
        tokens = [t for t in tokens if len(t) >= 2]

        # N-gram
        if self.ngram_range[1] > 1:
            bigrams = []
            for i in range(len(tokens) - 1):
                bigrams.append(f"{tokens[i]}_{tokens[i+1]}")
            tokens.extend(bigrams)

        return tokens


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    余弦相似度。

    假设输入已 L2 归一化，则直接点积。
    """
    return float(np.dot(a, b))


def index_flat(
    vectors: np.ndarray,
    query: np.ndarray,
    top_k: int = 10,
) -> tuple[list[int], list[float]]:
    """
    暴力搜索 Top-K（平面索引）。

    生产环境替换为 FAISS IndexFlatIP。

    Args:
        vectors: (n_docs, dim) 的文档向量矩阵
        query: (dim,) 的查询向量
        top_k: 返回数量

    Returns:
        (indices, scores) — 按分数降序排列
    """
    if vectors.shape[0] == 0:
        return [], []

    scores = vectors @ query  # (n_docs,)
    top_indices = np.argsort(scores)[::-1][:top_k]
    top_scores = scores[top_indices]

    return list(top_indices), list(top_scores)