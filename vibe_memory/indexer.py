"""
Incremental Indexer (M3 — 增量索引)

双速索引：
- 实时层（Tier 1）：store() 时同步建同会话边（零延迟）
- 批处理层（Tier 2）：跨会话边候选排队，批量处理（节省 LLM 成本）

回压控制：
- 队列上限：max_queue_size，超限丢弃最旧候选
- 批量上限：batch_size，每次 flush 最多处理 N 对
- 评分优先：候选按相似度排序，高分优先处理
- 去重：同一对只排队一次

设计原则：
- 降级：flush 失败不阻塞 store
- 可观测：队列大小、处理计数、丢弃计数
- 幂等：重复 flush 不会重复建边（INSERT OR REPLACE）
"""

import uuid
import time
from typing import Optional, Callable
from datetime import datetime
from collections import OrderedDict

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, EdgeLabel, EdgeSource, EdgeStatus,
    DEFAULT_TENANT,
)
from vibe_memory.edges.edge_builder import (
    classify_cross_session_edge,
    build_cross_session_candidates,
)


class IndexCandidate:
    """待索引的跨会话边候选"""

    def __init__(
        self,
        new_atom: MemoryAtom,
        existing_atom: MemoryAtom,
        similarity: float,
        queued_at: Optional[datetime] = None,
    ):
        self.new_atom = new_atom
        self.existing_atom = existing_atom
        self.similarity = similarity
        self.queued_at = queued_at or datetime.now()

    @property
    def pair_key(self) -> str:
        """去重键：按 ID 排序保证唯一"""
        ids = sorted([self.new_atom.id, self.existing_atom.id])
        return f"{ids[0]}-{ids[1]}"


class BackpressureStrategy:
    """回压策略"""

    DROP_OLDEST = "drop_oldest"   # 丢弃队列中最旧的
    DROP_LOWEST = "drop_lowest"   # 丢弃相似度最低的
    BLOCK = "block"               # 阻塞 store（不推荐）


class IncrementalIndexer:
    """
    增量索引器。

    双速索引 + 回压控制。

    Args:
        storage: VibeStorage 实例
        agent_id: Agent 标识
        tenant_id: 租户 ID
        batch_size: 每次 flush 最多处理候选数（默认 10）
        max_queue_size: 队列最大容量（默认 1000）
        backpressure: 回压策略（默认 drop_oldest）
        edge_similarity_threshold: 建边相似度阈值（默认 0.7）
        llm_classify: LLM 分类回调（None 则用规则）
    """

    def __init__(
        self,
        storage,
        agent_id: str,
        tenant_id: str = DEFAULT_TENANT,
        batch_size: int = 10,
        max_queue_size: int = 1000,
        backpressure: str = BackpressureStrategy.DROP_OLDEST,
        edge_similarity_threshold: float = 0.7,
        llm_classify: Optional[Callable] = None,
    ):
        self.storage = storage
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self.backpressure = backpressure
        self.edge_similarity_threshold = edge_similarity_threshold
        self.llm_classify = llm_classify

        # 候选队列（OrderedDict 保证插入顺序 + 去重）
        self._queue: OrderedDict[str, IndexCandidate] = OrderedDict()

        # 统计
        self._enqueued_count: int = 0
        self._processed_count: int = 0
        self._dropped_count: int = 0
        self._edges_created: int = 0
        self._flush_count: int = 0
        self._last_flush_at: Optional[datetime] = None
        self._store_since_last_flush: int = 0

        # 回压阈值：每 N 次 store 自动触发 flush
        self._auto_flush_threshold: int = 20

    # ── 入队 ──

    def enqueue(self, new_atom: MemoryAtom, existing_atom: MemoryAtom, similarity: float) -> bool:
        """
        将跨会话边候选加入队列。

        Args:
            new_atom: 新分片
            existing_atom: 已有分片
            similarity: 相似度分数

        Returns:
            True 如果入队成功，False 如果被丢弃
        """
        candidate = IndexCandidate(new_atom, existing_atom, similarity)
        pair_key = candidate.pair_key

        # 去重：已存在则更新相似度（取最大值）
        if pair_key in self._queue:
            if similarity > self._queue[pair_key].similarity:
                self._queue[pair_key] = candidate
            return True

        # 回压：队列已满
        if len(self._queue) >= self.max_queue_size:
            self._dropped_count += 1
            self._apply_backpressure(candidate)
            return False

        # 相似度低于阈值：不建边，但也不入队
        if similarity < self.edge_similarity_threshold:
            return False

        self._queue[pair_key] = candidate
        self._enqueued_count += 1
        return True

    def enqueue_batch(
        self,
        new_atom: MemoryAtom,
        existing_atoms: list[MemoryAtom],
        similarity_threshold: Optional[float] = None,
    ) -> int:
        """
        批量入队：从 KNN 预筛结果中提取候选。

        Args:
            new_atom: 新分片
            existing_atoms: 已有分片列表
            similarity_threshold: 相似度阈值（None 则用默认）

        Returns:
            入队数量
        """
        threshold = similarity_threshold or self.edge_similarity_threshold
        candidates = build_cross_session_candidates(
            new_atom, existing_atoms,
            high_similarity=0.9,
            medium_similarity=threshold,
        )

        count = 0
        for sim in candidates["similar"]:
            # 计算精确相似度
            from vibe_memory.edges.edge_builder import _tag_overlap_ratio
            sim_score = _tag_overlap_ratio(new_atom, sim)
            if self.enqueue(new_atom, sim, sim_score):
                count += 1

        return count

    # ── 出队 & 处理 ──

    def flush(self, max_batch: Optional[int] = None) -> int:
        """
        批量处理队列中的候选。

        按相似度降序处理，每次最多 batch_size 个。

        Args:
            max_batch: 覆盖 batch_size（None 则用默认）

        Returns:
            创建的边数量
        """
        batch_limit = max_batch or self.batch_size
        if not self._queue:
            return 0

        # 按相似度降序排序
        sorted_candidates = sorted(
            self._queue.values(),
            key=lambda c: c.similarity,
            reverse=True,
        )

        batch = sorted_candidates[:batch_limit]
        edges_created = 0

        for candidate in batch:
            # 从队列中移除
            self._queue.pop(candidate.pair_key, None)

            try:
                label, conf = classify_cross_session_edge(
                    candidate.new_atom,
                    candidate.existing_atom,
                    llm_classify=self.llm_classify,
                )

                if conf >= 0.3:
                    edge = Edge(
                        id=str(uuid.uuid4()),
                        from_atom_id=candidate.new_atom.id,
                        to_atom_id=candidate.existing_atom.id,
                        tenant_id=self.tenant_id,
                        label=label,
                        confidence=conf,
                        source=EdgeSource.LLM if self.llm_classify else EdgeSource.RULE,
                        created_at=datetime.now(),
                        status=EdgeStatus.ACTIVE,
                    )
                    self.storage.insert_edge(edge)
                    edges_created += 1
                    self._edges_created += 1

                self._processed_count += 1

            except Exception:
                # 单个候选失败不影响整批
                self._processed_count += 1
                continue

        self._flush_count += 1
        self._last_flush_at = datetime.now()
        self._store_since_last_flush = 0

        return edges_created

    def flush_all(self) -> int:
        """处理队列中所有候选（不限制 batch_size）"""
        total = 0
        while self._queue:
            created = self.flush(max_batch=self.batch_size)
            total += created
            if created == 0:
                break
        return total

    # ── 自动触发 ──

    def on_store(self) -> Optional[int]:
        """
        store 操作后调用。检查是否需要自动 flush。

        Returns:
            如果触发了 flush，返回创建的边数；否则 None
        """
        self._store_since_last_flush += 1

        if self._store_since_last_flush >= self._auto_flush_threshold:
            if self._queue:
                return self.flush()

        return None

    def should_flush(self) -> bool:
        """判断是否应该 flush"""
        return len(self._queue) >= self.batch_size

    # ── 回压控制 ──

    def _apply_backpressure(self, candidate: IndexCandidate) -> None:
        """实施回压策略"""
        if self.backpressure == BackpressureStrategy.DROP_OLDEST:
            # 删除最旧的候选
            if self._queue:
                oldest_key = next(iter(self._queue))
                self._queue.pop(oldest_key)
                self._dropped_count += 1
                # 重新插入新候选
                self._queue[candidate.pair_key] = candidate
                self._enqueued_count += 1

        elif self.backpressure == BackpressureStrategy.DROP_LOWEST:
            # 删除相似度最低的
            if self._queue:
                lowest = min(self._queue.values(), key=lambda c: c.similarity)
                if candidate.similarity > lowest.similarity:
                    self._queue.pop(lowest.pair_key)
                    self._dropped_count += 1
                    self._queue[candidate.pair_key] = candidate
                    self._enqueued_count += 1

        # BLOCK: do nothing, candidate is simply dropped

    # ── 队列管理 ──

    def clear_queue(self) -> int:
        """清空队列，返回丢弃的候选数"""
        count = len(self._queue)
        self._queue.clear()
        self._dropped_count += count
        return count

    def compact_queue(self) -> int:
        """
        压缩队列：合并相似度极高且指向同一原子的候选。

        如果多个候选指向同一 existing_atom，只保留相似度最高的。

        Returns:
            合并后丢弃的数量
        """
        by_existing: dict[str, list[IndexCandidate]] = {}
        for candidate in self._queue.values():
            by_existing.setdefault(candidate.existing_atom.id, []).append(candidate)

        dropped = 0
        for atom_id, candidates in by_existing.items():
            if len(candidates) > 1:
                # 保留相似度最高的
                best = max(candidates, key=lambda c: c.similarity)
                for c in candidates:
                    if c.pair_key != best.pair_key:
                        self._queue.pop(c.pair_key, None)
                        dropped += 1

        self._dropped_count += dropped
        return dropped

    # ── 统计 ──

    def stats(self) -> dict:
        """索引器统计"""
        linked = self.storage.get_all_edges()
        return {
            "queue_size": len(self._queue),
            "max_queue_size": self.max_queue_size,
            "batch_size": self.batch_size,
            "enqueued_count": self._enqueued_count,
            "processed_count": self._processed_count,
            "dropped_count": self._dropped_count,
            "edges_created": self._edges_created,
            "flush_count": self._flush_count,
            "last_flush_at": self._last_flush_at.isoformat() if self._last_flush_at else None,
            "store_since_last_flush": self._store_since_last_flush,
            "auto_flush_threshold": self._auto_flush_threshold,
            "total_edges_in_graph": len(linked),
            "backpressure": self.backpressure,
            "edge_similarity_threshold": self.edge_similarity_threshold,
            "has_llm": self.llm_classify is not None,
        }

    def reset(self) -> None:
        """重置统计（用于测试）"""
        self._queue.clear()
        self._enqueued_count = 0
        self._processed_count = 0
        self._dropped_count = 0
        self._edges_created = 0
        self._flush_count = 0
        self._last_flush_at = None
        self._store_since_last_flush = 0