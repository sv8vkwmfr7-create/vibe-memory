"""
Embedding Provider: 统一向量化接口

支持多后端：
- TfidfBackend: 纯 numpy TF-IDF，零额外依赖
- SentenceTransformerBackend: 语义 embedding（需要 sentence-transformers）

设计原则：
- 统一接口：encode() 返回 numpy 向量
- 自动降级：语义后端不可用 → 回退 TF-IDF
- 懒加载：语义模型首次使用时才加载
"""

from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class EmbeddingProvider(ABC):
    """向量化抽象接口"""

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """
        将文本列表编码为向量。

        Returns:
            shape (n_texts, dim) 的 numpy 数组，L2 归一化
        """
        ...

    @abstractmethod
    def encode_query(self, query: str) -> np.ndarray:
        """
        编码单条查询。

        Returns:
            shape (dim,) 的 numpy 数组，L2 归一化
        """
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """后端名称"""
        ...


class TfidfProvider(EmbeddingProvider):
    """
    TF-IDF 向量化后端。

    零额外依赖。适合 L1 原型和 baseline 对比。
    """

    def __init__(self, max_features: int = 5000):
        from vibe_memory.embedding.tfidf import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(max_features=max_features)
        self._fitted = False

    def fit(self, documents: list[str]) -> "TfidfProvider":
        """在文档集上拟合词汇表"""
        self.vectorizer.fit(documents)
        self._fitted = True
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            self.fit(texts)
        return self.vectorizer.transform(texts)

    def encode_query(self, query: str) -> np.ndarray:
        vec = self.vectorizer.transform([query])
        return vec[0] if vec.shape[0] > 0 else np.zeros(self.dim)

    @property
    def dim(self) -> int:
        return len(self.vectorizer.vocabulary) if self._fitted else 0

    @property
    def name(self) -> str:
        return "tfidf"


class SentenceTransformerProvider(EmbeddingProvider):
    """
    语义 embedding 后端。

    使用 sentence-transformers。首次使用时懒加载模型。

    降级策略：sentence-transformers 不可用 → 回退 TF-IDF
    网络问题：设置 HF_ENDPOINT 环境变量可使用镜像
      e.g. HF_ENDPOINT=https://hf-mirror.com
    """

    # 推荐模型（按质量/速度排序）
    DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384d, 80MB, 适合本地

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "cpu",
        normalize: bool = True,
        hf_endpoint: str = "",
    ):
        self.model_name = model_name
        self.device = device
        self.normalize = normalize
        self.hf_endpoint = hf_endpoint
        self._model = None
        self._fallback: Optional[TfidfProvider] = None
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """检查 sentence-transformers 是否可用"""
        if self._available is None:
            try:
                import sentence_transformers
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def _get_model(self):
        """Lazy-load model."""
        if self._model is None and self.available:
            import os
            from sentence_transformers import SentenceTransformer

            # Support HF_ENDPOINT for mirrors (e.g. https://hf-mirror.com)
            if self.hf_endpoint:
                os.environ.setdefault("HF_ENDPOINT", self.hf_endpoint)

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def _get_fallback(self) -> TfidfProvider:
        """获取降级后端"""
        if self._fallback is None:
            self._fallback = TfidfProvider()
        return self._fallback

    def encode(self, texts: list[str]) -> np.ndarray:
        if not self.available:
            return self._get_fallback().encode(texts)

        model = self._get_model()
        if model is None:
            return self._get_fallback().encode(texts)

        vectors = model.encode(
            texts,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )
        return np.array(vectors)

    def encode_query(self, query: str) -> np.ndarray:
        if not self.available:
            return self._get_fallback().encode_query(query)

        model = self._get_model()
        if model is None:
            return self._get_fallback().encode_query(query)

        vec = model.encode(
            query,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )
        return np.array(vec)

    @property
    def dim(self) -> int:
        if self.available:
            model = self._get_model()
            if model is not None:
                return model.get_embedding_dimension()
        return self._get_fallback().dim

    @property
    def name(self) -> str:
        if self.available:
            return f"st-{self.model_name}"
        return "tfidf(fallback)"


def create_provider(
    backend: str = "auto",
    model_name: str = "all-MiniLM-L6-v2",
) -> EmbeddingProvider:
    """
    工厂函数：创建 embedding provider。

    Args:
        backend: "tfidf" | "st" | "auto"
            - tfidf: 强制 TF-IDF
            - st: 强制 SentenceTransformer
            - auto: 优先 SentenceTransformer，不可用则 TF-IDF
        model_name: SentenceTransformer 模型名（仅 st/auto 时生效）
    """
    if backend == "tfidf":
        return TfidfProvider()

    if backend == "st":
        provider = SentenceTransformerProvider(model_name=model_name)
        if not provider.available:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            )
        return provider

    if backend == "auto":
        provider = SentenceTransformerProvider(model_name=model_name)
        if provider.available:
            return provider
        # 静默降级
        return TfidfProvider()

    raise ValueError(f"Unknown backend: {backend}. Use 'tfidf', 'st', or 'auto'.")