"""
PPR (Personalized PageRank) 检索算法

替代 BFS 层级展开。HippoRAG 启发：加权随机游走，收敛替代 max_depth 硬截断。
一次 PPR 游走 > 多轮迭代检索，便宜 10-30x。

三档可配置操作点（Bug 11 WISE 启发）：
- precision: 高重启，窄探索，适合排错/安全关键
- recall: 低重启，宽探索，适合创意发散
- budget: 极高重启，几乎不探索，适合高频简单任务

检索管道（v2）：
1. 向量预筛（embedding provider）→ 种子节点
2. 种子后过滤（图连通性）→ 高质量种子
3. PPR 图游走（边标签过滤）
4. 排序 + 构建注入上下文
"""

from typing import Optional
from datetime import datetime
from collections import defaultdict
import numpy as np

from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel, EdgeStatus, GraphPartition
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.embedding import index_flat, EmbeddingProvider, TfidfProvider
from vibe_memory.retrieval.seed_filter import SeedFilter


class PPRConfig:
    """PPR 三档可配置操作点"""

    def __init__(
        self,
        restart_probability: float = 0.15,
        convergence_threshold: float = 0.001,
        max_iterations: int = 100,
        allowed_edge_labels: Optional[list[EdgeLabel]] = None,
        top_n: int = 10,
        reverse_weight_penalty: float = 0.5,
        min_edge_weight: float = 0.05,
    ):
        self.restart_probability = restart_probability
        self.convergence_threshold = convergence_threshold
        self.max_iterations = max_iterations
        self.allowed_edge_labels = allowed_edge_labels or list(EdgeLabel)
        self.top_n = top_n
        self.reverse_weight_penalty = reverse_weight_penalty
        self.min_edge_weight = min_edge_weight

    @classmethod
    def precision(cls) -> "PPRConfig":
        """精确优先：高重启，只走因果+修正边"""
        return cls(
            restart_probability=0.3,
            convergence_threshold=0.001,
            allowed_edge_labels=[EdgeLabel.CAUSAL, EdgeLabel.REVISION],
            top_n=5,
        )

    @classmethod
    def recall(cls) -> "PPRConfig":
        """召回优先：低重启，走所有边类型"""
        return cls(
            restart_probability=0.1,
            convergence_threshold=0.0005,
            allowed_edge_labels=[
                EdgeLabel.CAUSAL, EdgeLabel.SIMILAR,
                EdgeLabel.REVISION, EdgeLabel.ADJACENT,
            ],
            top_n=15,
        )

    @classmethod
    def budget(cls) -> "PPRConfig":
        """成本优先：极高重启，只走因果边"""
        return cls(
            restart_probability=0.5,
            convergence_threshold=0.01,
            allowed_edge_labels=[EdgeLabel.CAUSAL],
            top_n=3,
        )


def personalized_pagerank(
    seed_atoms: list[MemoryAtom],
    storage: VibeStorage,
    config: Optional[PPRConfig] = None,
) -> dict[str, float]:
    """
    Personalized PageRank 图游走。

    算法：
    1. 从种子节点均匀分配初始分数
    2. 每轮迭代：
       - 以 alpha 概率重启到种子节点
       - 以 (1-alpha) 概率沿边游走到邻居
       - 游走概率 = 边权重 × 置信度 × 标签匹配度
       - 双向遍历：逆方向降权 0.5
    3. 收敛条件：所有节点分数变化 < epsilon

    Args:
        seed_atoms: 种子分片（向量检索 top-K 结果）
        storage: 存储层（用于获取边）
        config: PPR 配置

    Returns:
        {atom_id: ppr_score} 按分数降序
    """
    cfg = config or PPRConfig()

    # 初始化分数：种子节点均匀分配
    scores: dict[str, float] = {}
    seed_ids = set()
    for atom in seed_atoms:
        scores[atom.id] = 1.0 / len(seed_atoms)
        seed_ids.add(atom.id)

    # 预加载所有边（避免逐条查询）
    all_edges = storage.get_all_edges()
    outgoing: dict[str, list[Edge]] = defaultdict(list)
    incoming: dict[str, list[Edge]] = defaultdict(list)
    for edge in all_edges:
        if edge.status != EdgeStatus.ACTIVE:
            continue
        if edge.label not in cfg.allowed_edge_labels:
            continue
        outgoing[edge.from_atom_id].append(edge)
        incoming[edge.to_atom_id].append(edge)

    alpha = cfg.restart_probability
    epsilon = cfg.convergence_threshold

    for _ in range(cfg.max_iterations):
        new_scores: dict[str, float] = defaultdict(float)
        max_delta = 0.0

        for atom_id, score in scores.items():
            if score <= 0:
                continue

            # 重启：alpha 概率回到种子
            restart_share = score * alpha / len(seed_ids)
            for sid in seed_ids:
                new_scores[sid] += restart_share

            # 正向游走：沿 outgoing edges
            for edge in outgoing.get(atom_id, []):
                walk_prob = score * (1 - alpha) * edge.weight * edge.confidence
                if walk_prob < cfg.min_edge_weight:
                    continue
                new_scores[edge.to_atom_id] += walk_prob

            # 反向游走：沿 incoming edges（Bug 2 双向遍历，逆方向降权）
            for edge in incoming.get(atom_id, []):
                walk_prob = (
                    score * (1 - alpha) * edge.weight * edge.confidence
                    * cfg.reverse_weight_penalty
                )
                if walk_prob < cfg.min_edge_weight:
                    continue
                new_scores[edge.from_atom_id] += walk_prob

        # 归一化
        total = sum(new_scores.values())
        if total > 0:
            for nid in new_scores:
                new_scores[nid] /= total

        # 收敛检测
        all_ids = set(scores.keys()) | set(new_scores.keys())
        for nid in all_ids:
            old = scores.get(nid, 0.0)
            new_val = new_scores.get(nid, 0.0)
            delta = abs(new_val - old)
            if delta > max_delta:
                max_delta = delta

        scores = new_scores

        if max_delta < epsilon:
            break

    # Keep seed nodes in scores (they are valid results)
    # But mark them as seeds so recall() can prioritize non-seed results

    return scores


def build_trace(
    seed_atoms: list[MemoryAtom],
    ranked_atoms: list[MemoryAtom],
    storage: VibeStorage,
) -> list[dict]:
    """
    构建检索路径（Bug 18 检索路径可解释性）。

    对每个召回分片，找到从种子到它的最短路径。

    Returns:
        [{from, to, edge_label, depth, confidence}, ...]
    """
    traces: list[dict] = []
    seed_ids = {a.id for a in seed_atoms}

    # 简单路径：对每个召回分片，检查是否有直连边到任何种子
    all_edges = storage.get_all_edges()
    edge_map: dict[tuple[str, str], Edge] = {}
    for e in all_edges:
        edge_map[(e.from_atom_id, e.to_atom_id)] = e

    for atom in ranked_atoms:
        for seed_id in seed_ids:
            # 正向：种子 -> 召回分片
            key = (seed_id, atom.id)
            if key in edge_map:
                edge = edge_map[key]
                traces.append({
                    "from": seed_id,
                    "to": atom.id,
                    "edge_label": edge.label.value,
                    "depth": 1,
                    "confidence": edge.confidence,
                })
                break
            # 反向：召回分片 -> 种子
            key = (atom.id, seed_id)
            if key in edge_map:
                edge = edge_map[key]
                traces.append({
                    "from": seed_id,
                    "to": atom.id,
                    "edge_label": edge.label.value,
                    "depth": 1,
                    "confidence": edge.confidence,
                })
                break

    return traces


def recall(
    query: str,
    agent_id: str,
    storage: VibeStorage,
    mode: str = "precision",
    top_k: int = 20,
    embedding_provider: Optional[EmbeddingProvider] = None,
    seed_filter: Optional[SeedFilter] = None,
) -> dict:
    """
    统一检索入口（v2：embedding provider + seed filter）。

    四阶段：
    1. 向量预筛（embedding provider）→ 种子节点
    2. 种子后过滤（图连通性）→ 高质量种子
    3. PPR 图游走（边标签过滤）
    4. 排序 + 构建注入上下文

    Args:
        query: 查询文本
        agent_id: Agent 标识
        storage: 存储层
        mode: 操作点 ("precision" | "recall" | "budget")
        top_k: 向量预筛 top-K
        embedding_provider: 向量化后端（None → TF-IDF）
        seed_filter: 种子后过滤器（None → 默认配置）

    Returns:
        {atoms, trace, mode, total_walked, seed_count, filtered_count}
    """
    provider = embedding_provider or TfidfProvider()
    seed_filter = seed_filter or SeedFilter()

    # 阶段 1：向量预筛
    all_atoms = storage.get_atoms_by_agent(agent_id)
    active_atoms = [a for a in all_atoms if a.lifecycle.value in ("active", "warm")]

    if not active_atoms:
        return {
            "atoms": [], "trace": [], "mode": mode,
            "total_walked": 0, "seed_count": 0, "filtered_count": 0,
        }

    # 构建文档向量（首次拟合 + 增量编码）
    documents = [a.content for a in active_atoms]
    if isinstance(provider, TfidfProvider) and not provider._fitted:
        provider.fit(documents)
    doc_vectors = provider.encode(documents)
    query_vec = provider.encode_query(query)

    # 向量 Top-K
    indices, _ = index_flat(doc_vectors, query_vec, top_k=top_k)
    seed_atoms = [active_atoms[i] for i in indices if i < len(active_atoms)]

    if not seed_atoms:
        return {
            "atoms": [], "trace": [], "mode": mode,
            "total_walked": 0, "seed_count": 0, "filtered_count": 0,
        }

    seed_count = len(seed_atoms)

    # 阶段 2：种子后过滤
    filtered_seeds = seed_filter.filter(seed_atoms, storage)
    filtered_count = len(filtered_seeds)

    # 阶段 3：PPR 图游走
    if mode == "precision":
        config = PPRConfig.precision()
    elif mode == "recall":
        config = PPRConfig.recall()
    elif mode == "budget":
        config = PPRConfig.budget()
    else:
        config = PPRConfig()

    ppr_scores = personalized_pagerank(filtered_seeds, storage, config)

    # 阶段 4：排序 + 截断
    ranked = sorted(ppr_scores.items(), key=lambda x: x[1], reverse=True)
    ranked_ids = [aid for aid, _ in ranked[:config.top_n]]
    ranked_atoms = []
    for aid in ranked_ids:
        atom = storage.get_atom(aid)
        if atom:
            ranked_atoms.append(atom)

    # 构建 trace
    trace = build_trace(filtered_seeds, ranked_atoms, storage)

    return {
        "atoms": ranked_atoms,
        "trace": trace,
        "mode": mode,
        "total_walked": len(ppr_scores),
        "seed_count": seed_count,
        "filtered_count": filtered_count,
    }


def _tag_match_score(query_lower: str, atom: MemoryAtom) -> float:
    """Tag + content match score (L1 fallback without embeddings).

    Match query keywords against:
    1. Atom tags
    2. Atom content words
    3. Atom summary words
    """
    score = 0.0

    # Tag matching: tag keywords in query
    tag_keywords = {
        "error": ["error", "timeout", "fail", "bug", "exception"],
        "config": ["config", "timeout", "param", "setting", "change"],
        "task": ["task", "done", "start", "continue"],
        "query": ["query", "search", "lookup", "find", "weather"],
        "decision": ["decision", "plan", "solution", "decide"],
        "routine": ["fix", "passed", "ok", "done"],
    }

    for tag in atom.tags:
        keywords = tag_keywords.get(tag, [tag])
        for kw in keywords:
            if kw in query_lower:
                score += 1.0
                break

    # Content matching: query words in atom content
    query_words = set(query_lower.split())
    content_lower = atom.content.lower()
    for word in query_words:
        if len(word) > 2 and word in content_lower:
            score += 0.5

    # Summary matching
    summary_lower = atom.summary.lower()
    for word in query_words:
        if len(word) > 2 and word in summary_lower:
            score += 0.3

    # Normalize
    max_score = len(atom.tags) + len(query_words) * 0.8
    return min(score / max(max_score, 1), 1.0)


def fallback_vector_topk(
    query: str,
    agent_id: str,
    storage: VibeStorage,
    top_k: int = 5,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> list[MemoryAtom]:
    """
    降级策略：PPR 不可用时回退纯向量 Top-K（Bug 5 降级）。

    每模块有兜底，不可用时不崩溃只退化。
    """
    provider = embedding_provider or TfidfProvider()

    all_atoms = storage.get_atoms_by_agent(agent_id)
    active_atoms = [a for a in all_atoms if a.lifecycle.value in ("active", "warm")]

    if not active_atoms:
        return []

    documents = [a.content for a in active_atoms]
    if isinstance(provider, TfidfProvider) and not provider._fitted:
        provider.fit(documents)
    doc_vectors = provider.encode(documents)
    query_vec = provider.encode_query(query)

    indices, _ = index_flat(doc_vectors, query_vec, top_k=top_k)
    return [active_atoms[i] for i in indices if i < len(active_atoms)]