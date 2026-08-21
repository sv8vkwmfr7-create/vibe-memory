"""
VibeMemory SDK — 统一入口

嵌入式 Python SDK，9 个核心方法：

store(content, session_id)       → 写入分片
recall(query, mode)               → 检索记忆
link(from_id, to_id, label)       → 手动建边
migrate(atom_id, to_partition)    → 分区迁移
forget(atom_id)                   → 删除分片
update(atom_id, **fields)         → 更新元数据
history(session_id, limit)        → 会话历史
stats()                           → 统计信息
collect_garbage()                 → GC 压缩

用法：
    from vibe_memory import VibeMemory

    mem = VibeMemory(agent_id="my-agent", db_path="memory.db")
    mem.store("Fixed API timeout", session_id="chat-1")
    results = mem.recall("API timeout")
"""

import uuid
from typing import Optional
from datetime import datetime
from enum import Enum

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle, DEFAULT_TENANT,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.chunking.chunker import chunk_session, should_ingest
from vibe_memory.chunking.episode import EpisodeBuilder
from vibe_memory.edges.edge_builder import (
    build_same_session_edges,
    build_cross_session_candidates,
    classify_cross_session_edge,
    merge_atoms,
)
from vibe_memory.retrieval.ppr import recall as _recall
from vibe_memory.retrieval.seed_filter import SeedFilter
from vibe_memory.embedding.provider import EmbeddingProvider, create_provider
from vibe_memory.learner.learner import DecayManager
from vibe_memory.coldstart import ColdStartManager, ColdPhase
from vibe_memory.metrics import MetricsCollector
from vibe_memory.gc import GarbageCollector, GCResult


class VibeMemory:
    """
    VibeMemory SDK — 嵌入式记忆系统。

    特性：
    - 多租户：tenant_id 隔离
    - 语义检索：自动选择 embedding 后端
    - 图结构：自动建边 + PPR 检索
    - 衰减管理：内置 DecayManager
    - 降级全覆盖：每个模块有兜底

    Args:
        agent_id: Agent 标识
        db_path: SQLite 数据库路径（":memory:" 为内存模式）
        tenant_id: 租户 ID（默认 "default"）
        embedding_backend: 向量化后端（"auto" | "tfidf" | "st"）
        embedding_model: 语义模型名（仅 st/auto 时生效）
    """

    def __init__(
        self,
        agent_id: str,
        db_path: str = ":memory:",
        tenant_id: str = DEFAULT_TENANT,
        embedding_backend: str = "auto",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.agent_id = agent_id
        self.tenant_id = tenant_id

        # 存储层
        self.storage = VibeStorage(db_path=db_path, tenant_id=tenant_id)

        # Embedding
        self.embedding = create_provider(backend=embedding_backend, model_name=embedding_model)

        # 种子过滤
        self.seed_filter = SeedFilter()

        # 衰减管理器
        self.decay_manager = DecayManager()

        # 冷启动管理器
        self.cold_start = ColdStartManager(
            storage=self.storage,
            agent_id=agent_id,
            tenant_id=tenant_id,
            embedding_provider=self.embedding,
        )

        # 可观测性
        self.metrics = MetricsCollector()

        # GC 垃圾回收
        self.gc = GarbageCollector(
            storage=self.storage,
            agent_id=agent_id,
            tenant_id=tenant_id,
        )

        # 统计
        self._store_count: int = 0
        self._recall_count: int = 0
        self._edge_count: int = 0

    # ── 1. store ──

    def store(
        self,
        content: str,
        session_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        summary: Optional[str] = None,
        context_before: str = "",
        context_after: str = "",
        partition: GraphPartition = GraphPartition.SESSION,
        confidence: float = 1.0,
        auto_build_edges: bool = True,
        auto_episode: bool = True,
    ) -> MemoryAtom:
        """
        写入一条记忆分片。

        Args:
            content: 分片内容
            session_id: 会话 ID（None 则自动生成）
            tags: 手动标签（None 则自动生成）
            summary: 摘要（None 则截取 content 前 200 字符）
            context_before: 上文
            context_after: 下文
            partition: 图分区
            confidence: 置信度
            auto_build_edges: 是否自动建边
            auto_episode: 是否自动 Episode 聚合

        Returns:
            创建的 MemoryAtom
        """
        from vibe_memory.chunking.chunker import _generate_tags

        sid = session_id or str(uuid.uuid4())
        atom = MemoryAtom(
            id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            session_id=sid,
            content=content,
            summary=summary or content[:200],
            tenant_id=self.tenant_id,
            type=partition,
            tags=tags or _generate_tags(content),
            lifecycle=Lifecycle.ACTIVE,
            weight=1.0,
            created_at=datetime.now(),
            source=sid,
            confidence=confidence,
            context_before=context_before,
            context_after=context_after,
        )

        # 持久化
        self.storage.insert_atom(atom)
        self._store_count += 1
        self.cold_start.invalidate_cache()
        self.metrics.record_store()

        # 冷启动阶段使用激进阈值建边
        if auto_build_edges:
            self._auto_build_edges(atom)

        # 自动 Episode
        if auto_episode:
            self._auto_episode_aggregation(sid)

        return atom

    def store_batch(
        self,
        messages: list[dict],
        session_id: Optional[str] = None,
    ) -> list[MemoryAtom]:
        """
        批量写入：从会话消息列表自动切分 + 入库。

        Args:
            messages: [{"role": "user"/"assistant", "content": "..."}, ...]
            session_id: 会话 ID

        Returns:
            创建的 MemoryAtom 列表
        """
        sid = session_id or str(uuid.uuid4())
        atoms = chunk_session(messages, self.agent_id, sid)
        stored: list[MemoryAtom] = []

        for atom in atoms:
            if should_ingest(atom.content, None):
                atom.tenant_id = self.tenant_id
                self.storage.insert_atom(atom)
                stored.append(atom)
                self._store_count += 1
                self.metrics.record_store()

        # 同会话建边
        if len(stored) >= 2:
            for edge in build_same_session_edges(stored):
                edge.tenant_id = self.tenant_id
                self.storage.insert_edge(edge)
                self._edge_count += 1
                self.metrics.record_edge_built(source="rule", label=edge.label.value)

        # Episode 聚合
        self._auto_episode_aggregation(sid)

        return stored

    # ── 2. recall ──

    def recall(
        self,
        query: str,
        mode: str = "precision",
        top_k: int = 20,
    ) -> dict:
        """
        检索记忆。

        Args:
            query: 查询文本
            mode: "precision" | "recall" | "budget"
            top_k: 向量预筛 Top-K

        Returns:
            {atoms: [MemoryAtom], trace: [...], mode: str, total_walked: int}
        """
        result = _recall(
            query=query,
            agent_id=self.agent_id,
            storage=self.storage,
            mode=mode,
            top_k=top_k,
            embedding_provider=self.embedding,
            seed_filter=self.seed_filter,
            tenant_id=self.tenant_id,
        )
        self._recall_count += 1
        self.metrics.record_recall(result_count=len(result.get("atoms", [])))

        # 冷启动增强：结果不足时用种子记忆补充
        result = self.cold_start.augment_recall(query, result)

        # 强化命中的分片和边
        for atom in result.get("atoms", []):
            self.decay_manager.reinforce_atom(atom)
            self.storage.update_atom(atom)

        for trace_item in result.get("trace", []):
            # 强化遍历过的边
            edges = self.storage.get_edges_between(
                trace_item.get("from", ""), trace_item.get("to", "")
            )
            for edge in edges:
                self.decay_manager.reinforce_edge(edge)
                self.storage.update_edge(edge)

        return result

    # ── 3. link ──

    def link(
        self,
        from_atom_id: str,
        to_atom_id: str,
        label: EdgeLabel = EdgeLabel.SIMILAR,
        confidence: float = 0.7,
        source: EdgeSource = EdgeSource.RULE,
    ) -> Optional[Edge]:
        """
        手动建边。

        Args:
            from_atom_id: 源分片 ID
            to_atom_id: 目标分片 ID
            label: 边标签
            confidence: 置信度
            source: 边来源

        Returns:
            创建的 Edge，失败返回 None
        """
        from_atom = self.storage.get_atom(from_atom_id)
        to_atom = self.storage.get_atom(to_atom_id)

        if from_atom is None or to_atom is None:
            return None

        # 跨租户检查
        if from_atom.tenant_id != self.tenant_id or to_atom.tenant_id != self.tenant_id:
            return None

        edge = Edge(
            id=str(uuid.uuid4()),
            from_atom_id=from_atom_id,
            to_atom_id=to_atom_id,
            tenant_id=self.tenant_id,
            label=label,
            confidence=confidence,
            source=source,
            created_at=datetime.now(),
            status=EdgeStatus.ACTIVE,
            cross_partition=(from_atom.type != to_atom.type),
        )

        self.storage.insert_edge(edge)
        self._edge_count += 1
        self.metrics.record_edge_built(source=edge.source.value, label=edge.label.value)
        return edge

    # ── 4. migrate ──

    def migrate(
        self,
        atom_id: str,
        to_partition: GraphPartition,
    ) -> bool:
        """
        分区迁移：将分片从一个分区移动到另一个分区。

        典型场景：
        - Session → Document：优质会话记忆提升为文档
        - Document → Parametric：高频文档提取为 Agent 画像

        Args:
            atom_id: 分片 ID
            to_partition: 目标分区

        Returns:
            是否成功
        """
        atom = self.storage.get_atom(atom_id)
        if atom is None or atom.tenant_id != self.tenant_id:
            return False

        old_partition = atom.type
        atom.type = to_partition

        # 迁移到 Parametric 则几乎不衰减
        if to_partition == GraphPartition.PARAMETRIC:
            atom.decay_rate = 0.99

        self.storage.update_atom(atom)
        return True

    # ── 5. forget ──

    def forget(self, atom_id: str) -> bool:
        """
        删除一条记忆。

        Args:
            atom_id: 分片 ID

        Returns:
            是否成功
        """
        atom = self.storage.get_atom(atom_id)
        if atom is None or atom.tenant_id != self.tenant_id:
            return False

        self.storage.delete_atom(atom_id)
        self.cold_start.invalidate_cache()
        return True

    # ── 6. update ──

    def update(
        self,
        atom_id: str,
        **fields,
    ) -> Optional[MemoryAtom]:
        """
        更新分片元数据。

        可更新字段：content, summary, tags, confidence, weight, decay_rate

        Args:
            atom_id: 分片 ID
            **fields: 要更新的字段

        Returns:
            更新后的 MemoryAtom，失败返回 None
        """
        atom = self.storage.get_atom(atom_id)
        if atom is None or atom.tenant_id != self.tenant_id:
            return None

        for key, value in fields.items():
            if hasattr(atom, key):
                setattr(atom, key, value)

        atom.version += 1
        self.storage.update_atom(atom)
        return atom

    # ── 7. history ──

    def history(
        self,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryAtom]:
        """
        查询会话历史。

        Args:
            session_id: 会话 ID（None 则返回所有会话）
            limit: 最大返回数量

        Returns:
            MemoryAtom 列表（按时间倒序）
        """
        if session_id:
            atoms = self.storage.get_atoms_by_session(session_id)
        else:
            atoms = self.storage.get_atoms_by_agent(self.agent_id, tenant_id=self.tenant_id)

        # 按时间倒序 + 截断
        atoms.sort(key=lambda a: a.created_at, reverse=True)
        return atoms[:limit]

    # ── 8. stats ──

    def stats(self) -> dict:
        """
        获取统计信息。

        Returns:
            {
                agent_id, tenant_id, embedding_backend,
                total_atoms, active_atoms, warm_atoms, cold_atoms,
                total_edges, pending_edges,
                store_count, recall_count,
                partition_stats, learner_stats
            }
        """
        all_atoms = self.storage.get_atoms_by_agent(self.agent_id, tenant_id=self.tenant_id)

        active = sum(1 for a in all_atoms if a.lifecycle == Lifecycle.ACTIVE)
        warm = sum(1 for a in all_atoms if a.lifecycle == Lifecycle.WARM)
        cold = sum(1 for a in all_atoms if a.lifecycle == Lifecycle.COLD)

        all_edges = self.storage.get_all_edges()
        pending = self.storage.get_pending_edges()

        # 分区统计
        partitions: dict[str, int] = {}
        for a in all_atoms:
            p = a.type.value
            partitions[p] = partitions.get(p, 0) + 1

        # 边标签统计
        edge_labels: dict[str, int] = {}
        for e in all_edges:
            l = e.label.value
            edge_labels[l] = edge_labels.get(l, 0) + 1

        stats = {
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "embedding_backend": self.embedding.name,
            "total_atoms": len(all_atoms),
            "active_atoms": active,
            "warm_atoms": warm,
            "cold_atoms": cold,
            "total_edges": len(all_edges),
            "pending_edges": len(pending),
            "store_count": self._store_count,
            "recall_count": self._recall_count,
            "partitions": partitions,
            "edge_labels": edge_labels,
        }

        # Learner 统计
        if self.decay_manager.learner:
            stats["learner_stats"] = self.decay_manager.learner.get_stats()

        # 冷启动统计
        stats["cold_start"] = self.cold_start.stats()

        # 图规模快照（必须在 metrics.stats() 之前）
        self.metrics.snapshot_graph_size(
            atoms=len(all_atoms),
            edges=len(all_edges),
            active_atoms=active,
            warm_atoms=warm,
            cold_atoms=cold,
        )

        # 可观测性统计
        stats["metrics"] = self.metrics.stats()

        # GC 统计
        stats["gc"] = self.gc.stats()

        return stats

    # ── 9. collect_garbage ──

    def collect_garbage(self, dry_run: bool = False) -> dict:
        """
        执行 GC 压缩管线。

        Args:
            dry_run: True 则只计算不实际删除

        Returns:
            GCResult dict
        """
        result = self.gc.collect(dry_run=dry_run)

        # 记录到可观测性
        if result.total_cleaned > 0:
            self.metrics.snapshot_graph_size(
                atoms=len(self.storage.get_atoms_by_agent(self.agent_id, tenant_id=self.tenant_id)),
                edges=len(self.storage.get_all_edges()),
            )

        return result.to_dict()

    # ── 内部辅助 ──

    def _auto_build_edges(self, new_atom: MemoryAtom) -> None:
        """自动为新分片建边（冷启动感知）"""
        existing = self.storage.get_atoms_by_agent(self.agent_id, tenant_id=self.tenant_id)
        # 排除自身
        existing = [a for a in existing if a.id != new_atom.id]

        if not existing:
            return

        # 同会话建边
        same_session = [a for a in existing if a.session_id == new_atom.session_id]
        if same_session:
            for edge in build_same_session_edges(same_session + [new_atom]):
                edge.tenant_id = self.tenant_id
                self.storage.insert_edge(edge)
                self._edge_count += 1
                self.metrics.record_edge_built(source="rule", label=edge.label.value)

        # 跨会话建边（冷启动感知阈值）
        edge_sim = self.cold_start.get_edge_similarity_threshold()
        merge_sim = self.cold_start.get_merge_similarity_threshold()
        candidates = build_cross_session_candidates(
            new_atom, existing,
            high_similarity=merge_sim,
            medium_similarity=edge_sim,
        )
        for dup in candidates["duplicate"]:
            merged = merge_atoms(dup, new_atom)
            merged.tenant_id = self.tenant_id
            self.storage.insert_atom(merged)
            self.storage.delete_atom(new_atom.id)
            self.storage.delete_atom(dup.id)
            self._store_count += 1
            return

        for sim in candidates["similar"]:
            label, conf = classify_cross_session_edge(new_atom, sim)
            if conf >= 0.3:
                edge = Edge(
                    id=str(uuid.uuid4()),
                    from_atom_id=new_atom.id,
                    to_atom_id=sim.id,
                    tenant_id=self.tenant_id,
                    label=label,
                    confidence=conf,
                    source=EdgeSource.RULE,
                    created_at=datetime.now(),
                    status=EdgeStatus.ACTIVE,
                )
                self.storage.insert_edge(edge)
                self._edge_count += 1
                self.metrics.record_edge_built(source="rule", label=edge.label.value)

    def _auto_episode_aggregation(self, session_id: str) -> None:
        """自动 Episode 聚合"""
        session_atoms = self.storage.get_atoms_by_session(session_id)
        if len(session_atoms) < 3:
            return

        builder = EpisodeBuilder()
        episodes = builder.build_episodes(session_atoms)

        for ep in episodes:
            ep.tenant_id = self.tenant_id
            self.storage.insert_episode(ep)