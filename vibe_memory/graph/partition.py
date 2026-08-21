"""
Graph Partition Manager

Session / Document / Parametric 三张独立图。
每个分区维护自己的节点和边索引，跨分区通过 REFERENCE/LOOKUP/INFLUENCE 边连接。

整合 Bug 修复：
- Bug 9: 图分区（Session/Document/Parametric）
- Bug 14: 跨分区边类型（REFERENCE/LOOKUP/INFLUENCE/VERSION）
"""

import uuid
from typing import Optional
from datetime import datetime
from collections import defaultdict

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle,
)
from vibe_memory.storage.sqlite_store import VibeStorage


class PartitionStats:
    """分区统计"""

    def __init__(self):
        self.atom_count: int = 0
        self.edge_count: int = 0
        self.episode_count: int = 0
        self.active_atoms: int = 0
        self.warm_atoms: int = 0
        self.cold_atoms: int = 0
        self.cross_partition_edges: int = 0
        self.total_weight: float = 0.0

    def to_dict(self) -> dict:
        return {
            "atom_count": self.atom_count,
            "edge_count": self.edge_count,
            "episode_count": self.episode_count,
            "active_atoms": self.active_atoms,
            "warm_atoms": self.warm_atoms,
            "cold_atoms": self.cold_atoms,
            "cross_partition_edges": self.cross_partition_edges,
            "total_weight": self.total_weight,
        }


class GraphPartitionManager:
    """
    三图分区管理器。

    三张独立图：
    - Session: 会话记忆，高频读写，短期衰减
    - Document: 文档记忆，低频读写，长期保留
    - Parametric: Agent 画像，只读为主，几乎不衰减

    降级策略：分区管理器不可用 → 所有操作回退到单图模式（session partition）。
    """

    def __init__(self, storage: VibeStorage):
        self.storage = storage

        # 分区内索引（内存缓存，加速检索）
        # partition -> {atom_id -> MemoryAtom}
        self._atom_index: dict[GraphPartition, dict[str, MemoryAtom]] = {
            GraphPartition.SESSION: {},
            GraphPartition.DOCUMENT: {},
            GraphPartition.PARAMETRIC: {},
        }

        # 分区内边索引: partition -> {from_atom_id -> [Edge]}
        self._outgoing_index: dict[GraphPartition, dict[str, list[Edge]]] = {
            GraphPartition.SESSION: defaultdict(list),
            GraphPartition.DOCUMENT: defaultdict(list),
            GraphPartition.PARAMETRIC: defaultdict(list),
        }

        # 跨分区边（不按 partition 分组，按 from/to 分区对）
        self._cross_edges: list[Edge] = []

        # 是否已初始化
        self._initialized: bool = False

    # ── 初始化 ──

    def initialize(self, agent_id: Optional[str] = None) -> None:
        """
        从存储层加载所有数据，构建内存索引。

        Args:
            agent_id: 可选，只加载特定 Agent 的数据
        """
        if agent_id:
            atoms = self.storage.get_atoms_by_agent(agent_id)
        else:
            # 加载所有 atoms（L1 原型简化）
            atoms = self._load_all_atoms()

        edges = self.storage.get_all_edges()

        for atom in atoms:
            partition = atom.type
            self._atom_index[partition][atom.id] = atom

        for edge in edges:
            if edge.cross_partition:
                self._cross_edges.append(edge)
            else:
                # 通过 from_atom 确定分区
                from_atom = self._find_atom(edge.from_atom_id)
                if from_atom:
                    partition = from_atom.type
                    self._outgoing_index[partition][edge.from_atom_id].append(edge)

        self._initialized = True

    def _load_all_atoms(self) -> list[MemoryAtom]:
        """L1 原型：加载所有 atoms。后续可优化为分页加载。"""
        atoms: list[MemoryAtom] = []
        for partition in GraphPartition:
            atoms.extend(self._load_atoms_by_type(partition))
        return atoms

    def _load_atoms_by_type(self, partition: GraphPartition) -> list[MemoryAtom]:
        """按类型加载 atoms"""
        result: list[MemoryAtom] = []
        for agent_id in self._get_all_agent_ids():
            atoms = self.storage.get_atoms_by_agent(agent_id)
            result.extend([a for a in atoms if a.type == partition])
        return result

    def _get_all_agent_ids(self) -> list[str]:
        """L1 原型：获取所有 agent_id。后续升级为专用查询。"""
        # SQLite 直接查询
        try:
            rows = self.storage.conn.execute(
                "SELECT DISTINCT agent_id FROM atoms"
            ).fetchall()
            return [r["agent_id"] for r in rows]
        except Exception:
            return ["default"]

    def _find_atom(self, atom_id: str) -> Optional[MemoryAtom]:
        """在所有分区中查找 atom"""
        for partition in GraphPartition:
            if atom_id in self._atom_index[partition]:
                return self._atom_index[partition][atom_id]
        # 未命中缓存，尝试存储层
        return self.storage.get_atom(atom_id)

    # ── 分区写入 ──

    def route_atom(self, atom: MemoryAtom) -> None:
        """
        将 atom 路由到对应分区。

        根据 atom.type 自动分配：
        - SESSION → session 分区
        - DOCUMENT → document 分区
        - PARAMETRIC → parametric 分区
        """
        self._atom_index[atom.type][atom.id] = atom

    def route_edge(self, edge: Edge) -> None:
        """
        将 edge 路由到对应分区或跨分区边列表。

        规则：
        - 同分区 → 添加到对应分区的 outgoing_index
        - 跨分区 → 添加到 cross_edges，标记 cross_partition=True
        """
        from_atom = self._find_atom(edge.from_atom_id)
        to_atom = self._find_atom(edge.to_atom_id)

        if from_atom is None or to_atom is None:
            # 原子不存在，存为跨分区边以备后续
            edge.cross_partition = True
            self._cross_edges.append(edge)
            return

        if from_atom.type == to_atom.type:
            # 同分区
            edge.cross_partition = False
            self._outgoing_index[from_atom.type][edge.from_atom_id].append(edge)
        else:
            # 跨分区
            edge.cross_partition = True
            self._cross_edges.append(edge)

    def build_cross_partition_edges(
        self,
        atom: MemoryAtom,
        llm_classify=None,
    ) -> list[Edge]:
        """
        为 atom 构建跨分区边。

        规则：
        - Session atom → Document atom: LOOKUP（Agent 查阅了文档）
        - Document atom → Session atom: INFLUENCE（文档影响了后续会话）
        - 同分区不同版本: VERSION

        Args:
            atom: 目标分片
            llm_classify: 可选 LLM 分类回调

        Returns:
            新建的跨分区边列表
        """
        new_edges: list[Edge] = []

        for other_partition in GraphPartition:
            if other_partition == atom.type:
                continue

            other_atoms = list(self._atom_index[other_partition].values())
            if not other_atoms:
                continue

            for other in other_atoms:
                # 标签重叠率预筛
                overlap = _tag_overlap(atom, other)
                if overlap < 0.3:
                    continue

                if llm_classify:
                    label, confidence = llm_classify(atom, other)
                else:
                    # 规则推断
                    label, confidence = _infer_cross_edge_label(atom, other)

                if confidence < 0.3:
                    continue

                edge = Edge(
                    id=str(uuid.uuid4()),
                    from_atom_id=atom.id,
                    to_atom_id=other.id,
                    label=label,
                    confidence=confidence,
                    source=EdgeSource.RULE,
                    created_at=datetime.now(),
                    status=EdgeStatus.ACTIVE,
                    cross_partition=True,
                )
                new_edges.append(edge)
                self._cross_edges.append(edge)

        return new_edges

    # ── 分区查询 ──

    def get_atoms_in_partition(
        self,
        partition: GraphPartition,
        lifecycle_filter: Optional[list[Lifecycle]] = None,
    ) -> list[MemoryAtom]:
        """
        获取分区内的所有 atoms。

        Args:
            partition: 目标分区
            lifecycle_filter: 可选，只返回指定生命周期的 atoms
        """
        atoms = list(self._atom_index[partition].values())
        if lifecycle_filter:
            atoms = [a for a in atoms if a.lifecycle in lifecycle_filter]
        return atoms

    def get_edges_in_partition(
        self,
        partition: GraphPartition,
    ) -> list[Edge]:
        """获取分区内的所有边"""
        edges: list[Edge] = []
        for edge_list in self._outgoing_index[partition].values():
            edges.extend(edge_list)
        return edges

    def get_cross_partition_edges(
        self,
        from_partition: Optional[GraphPartition] = None,
        to_partition: Optional[GraphPartition] = None,
    ) -> list[Edge]:
        """
        获取跨分区边。

        Args:
            from_partition: 可选，只返回源分区为指定值的边
            to_partition: 可选，只返回目标分区为指定值的边
        """
        result: list[Edge] = []
        for edge in self._cross_edges:
            from_atom = self._find_atom(edge.from_atom_id)
            to_atom = self._find_atom(edge.to_atom_id)

            if from_partition and from_atom and from_atom.type != from_partition:
                continue
            if to_partition and to_atom and to_atom.type != to_partition:
                continue

            result.append(edge)

        return result

    def get_neighbors(
        self,
        atom_id: str,
        include_cross_partition: bool = True,
    ) -> list[MemoryAtom]:
        """
        获取一个 atom 的所有邻居（同分区 + 可选跨分区）。

        Args:
            atom_id: 目标 atom ID
            include_cross_partition: 是否包含跨分区邻居
        """
        atom = self._find_atom(atom_id)
        if atom is None:
            return []

        neighbors: list[MemoryAtom] = []
        visited: set[str] = set()

        # 同分区邻居
        for edge in self._outgoing_index[atom.type].get(atom_id, []):
            neighbor = self._find_atom(edge.to_atom_id)
            if neighbor and neighbor.id not in visited:
                neighbors.append(neighbor)
                visited.add(neighbor.id)

        # 反向边（其他节点指向当前节点）
        for other_id, edges in self._outgoing_index[atom.type].items():
            for edge in edges:
                if edge.to_atom_id == atom_id and other_id not in visited:
                    neighbor = self._find_atom(other_id)
                    if neighbor:
                        neighbors.append(neighbor)
                        visited.add(neighbor.id)

        # 跨分区邻居
        if include_cross_partition:
            for edge in self._cross_edges:
                if edge.from_atom_id == atom_id:
                    neighbor = self._find_atom(edge.to_atom_id)
                    if neighbor and neighbor.id not in visited:
                        neighbors.append(neighbor)
                        visited.add(neighbor.id)
                elif edge.to_atom_id == atom_id:
                    neighbor = self._find_atom(edge.from_atom_id)
                    if neighbor and neighbor.id not in visited:
                        neighbors.append(neighbor)
                        visited.add(neighbor.id)

        return neighbors

    # ── 分区统计 ──

    def get_partition_stats(self) -> dict[GraphPartition, PartitionStats]:
        """获取每个分区的统计信息"""
        stats: dict[GraphPartition, PartitionStats] = {}

        for partition in GraphPartition:
            ps = PartitionStats()
            atoms = self._atom_index[partition]
            ps.atom_count = len(atoms)

            for atom in atoms.values():
                ps.total_weight += atom.weight
                if atom.lifecycle == Lifecycle.ACTIVE:
                    ps.active_atoms += 1
                elif atom.lifecycle == Lifecycle.WARM:
                    ps.warm_atoms += 1
                elif atom.lifecycle == Lifecycle.COLD:
                    ps.cold_atoms += 1

            # 分区内边数
            for edge_list in self._outgoing_index[partition].values():
                ps.edge_count += len(edge_list)

            stats[partition] = ps

        # 跨分区边数
        cross_counts: dict[GraphPartition, int] = defaultdict(int)
        for edge in self._cross_edges:
            from_atom = self._find_atom(edge.from_atom_id)
            if from_atom:
                cross_counts[from_atom.type] += 1

        for partition, count in cross_counts.items():
            stats[partition].cross_partition_edges = count

        return stats

    def get_overall_stats(self) -> dict:
        """获取整体统计"""
        partition_stats = self.get_partition_stats()
        total_atoms = sum(ps.atom_count for ps in partition_stats.values())
        total_edges = sum(ps.edge_count for ps in partition_stats.values())
        total_cross = sum(ps.cross_partition_edges for ps in partition_stats.values())

        return {
            "total_atoms": total_atoms,
            "total_edges": total_edges,
            "total_cross_partition_edges": total_cross,
            "partitions": {
                p.value: s.to_dict() for p, s in partition_stats.items()
            },
        }

    # ── GC 辅助 ──

    def find_cold_atoms(
        self,
        partition: Optional[GraphPartition] = None,
        min_age_days: int = 30,
    ) -> list[MemoryAtom]:
        """
        查找冷分片（用于 GC 候选）。

        Args:
            partition: 可选，只查找特定分区
            min_age_days: 最小天数阈值
        """
        partitions = [partition] if partition else list(GraphPartition)
        cold: list[MemoryAtom] = []

        for p in partitions:
            for atom in self._atom_index[p].values():
                if atom.lifecycle == Lifecycle.COLD:
                    cold.append(atom)
                elif atom.lifecycle in (Lifecycle.ACTIVE, Lifecycle.WARM):
                    age_days = (datetime.now() - atom.created_at).days
                    if age_days >= min_age_days and atom.weight < 0.1:
                        cold.append(atom)

        return cold

    def evict_atoms(self, atom_ids: list[str]) -> int:
        """
        淘汰分片（GC 压缩优先）。

        Returns:
            实际淘汰数量
        """
        evicted = 0
        for atom_id in atom_ids:
            atom = self._find_atom(atom_id)
            if atom is None:
                continue

            # 从分区索引中移除
            if atom.id in self._atom_index[atom.type]:
                del self._atom_index[atom.type][atom.id]

            # 移除相关边
            if atom.id in self._outgoing_index[atom.type]:
                del self._outgoing_index[atom.type][atom.id]

            # 移除其他节点指向该节点的边
            for other_id, edges in list(self._outgoing_index[atom.type].items()):
                self._outgoing_index[atom.type][other_id] = [
                    e for e in edges if e.to_atom_id != atom_id
                ]

            # 移除跨分区边
            self._cross_edges = [
                e for e in self._cross_edges
                if e.from_atom_id != atom_id and e.to_atom_id != atom_id
            ]

            # 从存储层删除
            self.storage.delete_atom(atom_id)
            evicted += 1

        return evicted


# ── 辅助函数 ──

def _tag_overlap(a: MemoryAtom, b: MemoryAtom) -> float:
    """标签重叠率"""
    set_a = set(a.tags)
    set_b = set(b.tags)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _infer_cross_edge_label(
    from_atom: MemoryAtom,
    to_atom: MemoryAtom,
) -> tuple[EdgeLabel, float]:
    """
    推断跨分区边标签。

    规则：
    - Session → Document: LOOKUP（Agent 查阅了文档）
    - Document → Session: INFLUENCE（文档影响了会话）
    - Session → Session (不同 version): VERSION
    - Parametric → Session: INFLUENCE
    - Session → Parametric: 不建边（Agent 画像由系统维护）
    """
    if from_atom.type == GraphPartition.SESSION and to_atom.type == GraphPartition.DOCUMENT:
        return EdgeLabel.LOOKUP, 0.6
    elif from_atom.type == GraphPartition.DOCUMENT and to_atom.type == GraphPartition.SESSION:
        return EdgeLabel.INFLUENCE, 0.6
    elif from_atom.type == GraphPartition.PARAMETRIC and to_atom.type == GraphPartition.SESSION:
        return EdgeLabel.INFLUENCE, 0.5
    elif from_atom.type == GraphPartition.SESSION and to_atom.type == GraphPartition.SESSION:
        overlap = _tag_overlap(from_atom, to_atom)
        if overlap > 0.7:
            return EdgeLabel.VERSION, 0.7
        return EdgeLabel.REFERENCE, 0.4
    elif from_atom.type == GraphPartition.DOCUMENT and to_atom.type == GraphPartition.DOCUMENT:
        return EdgeLabel.REFERENCE, 0.5
    else:
        return EdgeLabel.REFERENCE, 0.3