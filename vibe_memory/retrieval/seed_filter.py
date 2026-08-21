"""
Seed Post-Filter: 图结构种子质量检查

问题：向量检索返回的种子可能包含噪声分片（语义相似但主题无关）。
PPR 边标签过滤只能抑制图游走阶段引入的噪声，无法过滤种子本身的噪声。

解决方案：种子后过滤——在 PPR 前剔除"孤立种子"（在图中与其他种子无连接的分片）。
原理：真正的相关分片在图中会有边连接到其他相关分片；噪声分片是孤立的。

降级策略：图结构不可用 → 不过滤，返回全部种子。
"""

from typing import Optional

from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeStatus
from vibe_memory.storage.sqlite_store import VibeStorage


class SeedFilter:
    """
    种子后过滤器。

    策略：
    1. 图连通性过滤：剔除与其他种子无边连接的分片
    2. 社区一致性过滤：剔除与多数种子不在同一社区的分片
    3. 冷启动兜底：种子数 < 3 时不过滤
    """

    def __init__(
        self,
        min_cross_seed_edges: int = 1,
        min_seeds_to_filter: int = 3,
        enable_community_filter: bool = False,
    ):
        self.min_cross_seed_edges = min_cross_seed_edges
        self.min_seeds_to_filter = min_seeds_to_filter
        self.enable_community_filter = enable_community_filter

    def filter(
        self,
        seed_atoms: list[MemoryAtom],
        storage: VibeStorage,
    ) -> list[MemoryAtom]:
        """
        过滤种子列表。

        Args:
            seed_atoms: 向量检索返回的种子分片
            storage: 存储层（用于查询边）

        Returns:
            过滤后的种子列表
        """
        if len(seed_atoms) < self.min_seeds_to_filter:
            return list(seed_atoms)  # 冷启动：种子太少，不过滤

        seed_ids = {a.id for a in seed_atoms}

        # 策略 1：图连通性过滤
        kept = self._filter_by_graph_connectivity(seed_atoms, seed_ids, storage)

        # 策略 2：社区一致性过滤（可选）
        if self.enable_community_filter and len(kept) >= self.min_seeds_to_filter:
            kept = self._filter_by_community_consistency(kept, storage)

        return kept

    def _filter_by_graph_connectivity(
        self,
        seed_atoms: list[MemoryAtom],
        seed_ids: set[str],
        storage: VibeStorage,
    ) -> list[MemoryAtom]:
        """
        图连通性过滤：剔除与其他种子无边的孤立种子。

        对每个种子，检查它是否有边连接到其他种子。
        至少需要 min_cross_seed_edges 条跨种子边。
        """
        kept: list[MemoryAtom] = []
        removed: list[MemoryAtom] = []

        for atom in seed_atoms:
            outgoing = storage.get_outgoing_edges(atom.id)
            incoming = storage.get_incoming_edges(atom.id)
            all_edges = outgoing + incoming

            # 只统计到其他种子的边（排除自环）
            cross_seed_count = sum(
                1 for e in all_edges
                if e.status == EdgeStatus.ACTIVE
                and (
                    (e.from_atom_id == atom.id and e.to_atom_id in seed_ids and e.to_atom_id != atom.id)
                    or (e.to_atom_id == atom.id and e.from_atom_id in seed_ids and e.from_atom_id != atom.id)
                )
            )

            if cross_seed_count >= self.min_cross_seed_edges:
                kept.append(atom)
            else:
                removed.append(atom)

        # 如果全部被过滤，保留所有（不过滤）
        if not kept:
            return list(seed_atoms)

        return kept

    def _filter_by_community_consistency(
        self,
        seed_atoms: list[MemoryAtom],
        storage: VibeStorage,
    ) -> list[MemoryAtom]:
        """
        社区一致性过滤：剔除与多数种子不在同一社区的分片。

        使用 episode_id 作为社区标识（L1 近似）。
        """
        from collections import Counter

        # 统计社区分布
        community_counts: Counter = Counter()
        for atom in seed_atoms:
            if atom.episode_id:
                community_counts[atom.episode_id] += 1

        if not community_counts:
            return list(seed_atoms)

        # 多数社区（> 50% 种子）
        total = len(seed_atoms)
        majority_community = community_counts.most_common(1)[0][0]
        majority_count = community_counts[majority_community]

        if majority_count < total * 0.5:
            return list(seed_atoms)  # 没有明显多数社区，不过滤

        # 保留多数社区的种子
        kept = [a for a in seed_atoms if a.episode_id == majority_community]

        if not kept:
            return list(seed_atoms)

        return kept

    def get_filter_stats(
        self,
        original: list[MemoryAtom],
        filtered: list[MemoryAtom],
    ) -> dict:
        """获取过滤统计"""
        removed_ids = {a.id for a in original} - {a.id for a in filtered}
        return {
            "original_count": len(original),
            "filtered_count": len(filtered),
            "removed_count": len(removed_ids),
            "removed_summaries": [
                a.summary for a in original if a.id in removed_ids
            ],
        }