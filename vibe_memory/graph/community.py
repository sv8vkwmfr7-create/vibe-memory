"""
Louvain Community Detection

基于模块度最优化的社区检测算法（Louvain 启发）。
用于将图分区内的节点聚类为社区（community），每个 Episode 可属于一个社区。

算法阶段：
1. 局部优化：每个节点尝试移动到邻居社区，选择最大化模块度增益的移动
2. 图压缩：将社区压缩为超级节点，重复阶段 1
3. 收敛：模块度不再提升时停止

L1 原型：简化版 Louvain，不包含 Leiden 的细化步骤。
后续可升级为 Leiden（更快的收敛 + 保证连通社区）。
"""

import uuid
from typing import Optional
from collections import defaultdict

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeStatus, GraphPartition,
)


class CommunityDetectionConfig:
    """社区检测配置"""

    def __init__(
        self,
        resolution: float = 1.0,       # 模块度分辨率参数（>1 → 更多小社区）
        max_iterations: int = 100,      # 最大迭代次数
        min_community_size: int = 2,    # 最小社区大小（少于 N 个节点的社区被合并）
        min_modularity_gain: float = 0.0001,  # 最小模块度增益（收敛阈值）
        edge_weight_threshold: float = 0.05,  # 边权重阈值（低于此值不参与计算）
    ):
        self.resolution = resolution
        self.max_iterations = max_iterations
        self.min_community_size = min_community_size
        self.min_modularity_gain = min_modularity_gain
        self.edge_weight_threshold = edge_weight_threshold


class LouvainCommunityDetector:
    """
    Louvain 社区检测器。

    在分区内运行，将节点聚类为社区。
    每个社区对应一个 community_id，可用于 Episode 分组。

    降级策略：社区检测不可用时 → 所有节点归入 "default" 社区。
    """

    def __init__(
        self,
        atoms: list[MemoryAtom],
        edges: list[Edge],
        config: Optional[CommunityDetectionConfig] = None,
    ):
        self.cfg = config or CommunityDetectionConfig()

        # 节点和边
        self.atoms: dict[str, MemoryAtom] = {a.id: a for a in atoms}
        self.atom_ids: list[str] = list(self.atoms.keys())

        # 过滤有效边（active + 权重超过阈值）
        self.edges: list[Edge] = [
            e for e in edges
            if e.status == EdgeStatus.ACTIVE
            and e.weight >= self.cfg.edge_weight_threshold
            and e.from_atom_id in self.atoms
            and e.to_atom_id in self.atoms
        ]

        # 邻接表: {atom_id: [(neighbor_id, edge_weight), ...]}
        self.adjacency: dict[str, list[tuple[str, float]]] = defaultdict(list)
        # 自环权重（压缩图时使用）
        self.self_loops: dict[str, float] = defaultdict(float)
        # 总边权（2m）
        self.total_weight: float = 0.0

        self._build_adjacency()

        # 社区分配: {atom_id: community_id}
        self.community: dict[str, str] = {}
        # 社区内边权: {community_id: sum of internal edge weights}
        self.community_internal: dict[str, float] = defaultdict(float)
        # 社区总度（连接边权之和）: {community_id: total degree}
        self.community_degree: dict[str, float] = defaultdict(float)

        # 模块度
        self.modularity: float = 0.0

    def _build_adjacency(self) -> None:
        """构建邻接表"""
        self.total_weight = 0.0

        for edge in self.edges:
            w = edge.weight * edge.confidence
            self.adjacency[edge.from_atom_id].append((edge.to_atom_id, w))
            self.adjacency[edge.to_atom_id].append((edge.from_atom_id, w))
            self.total_weight += w

        # 确保所有节点都在 adj 中（包括孤立节点）
        for atom_id in self.atom_ids:
            if atom_id not in self.adjacency:
                self.adjacency[atom_id] = []

    def detect(self) -> dict[str, str]:
        """
        运行 Louvain 社区检测。

        Returns:
            {atom_id: community_id}
        """
        n = len(self.atom_ids)

        if n == 0:
            return {}
        if n == 1:
            self.community = {self.atom_ids[0]: str(uuid.uuid4())}
            return self.community

        # 阶段 0：初始化——每个节点一个社区
        self.community = {}
        for atom_id in self.atom_ids:
            community_id = str(uuid.uuid4())
            self.community[atom_id] = community_id
            # 初始化社区统计
            self.community_internal[community_id] = self.self_loops.get(atom_id, 0.0)
            degree = sum(w for _, w in self.adjacency.get(atom_id, []))
            self.community_degree[community_id] = degree

        self.modularity = self._compute_modularity()

        # 阶段 1：局部优化
        for iteration in range(self.cfg.max_iterations):
            moved = self._local_optimization()
            if not moved:
                break

        # 阶段 2：合并小社区
        self._merge_small_communities()

        return dict(self.community)

    def _local_optimization(self) -> bool:
        """
        局部优化：每个节点尝试移动到邻居社区。

        Returns:
            True 如果有任何节点移动
        """
        moved = False
        # 随机打乱节点顺序（避免确定性偏差）
        import random
        node_order = list(self.atom_ids)
        random.shuffle(node_order)

        for atom_id in node_order:
            current_community = self.community[atom_id]

            # 计算移动到每个邻居社区后的模块度增益
            best_community = current_community
            best_gain = 0.0

            # 统计邻居社区及其边权
            neighbor_communities: dict[str, float] = defaultdict(float)
            for neighbor_id, weight in self.adjacency.get(atom_id, []):
                neighbor_community = self.community.get(neighbor_id)
                if neighbor_community and neighbor_community != current_community:
                    neighbor_communities[neighbor_community] += weight

            if not neighbor_communities:
                continue

            # 当前节点的度
            node_degree = sum(w for _, w in self.adjacency.get(atom_id, []))
            if node_degree == 0:
                continue

            for target_community, edge_weight_to_target in neighbor_communities.items():
                gain = self._modularity_gain(
                    atom_id=atom_id,
                    current_community=current_community,
                    target_community=target_community,
                    edge_weight_to_target=edge_weight_to_target,
                    node_degree=node_degree,
                )

                if gain > best_gain:
                    best_gain = gain
                    best_community = target_community

            # 执行移动
            if best_gain > self.cfg.min_modularity_gain and best_community != current_community:
                self._move_node(atom_id, current_community, best_community)
                moved = True

        return moved

    def _modularity_gain(
        self,
        atom_id: str,
        current_community: str,
        target_community: str,
        edge_weight_to_target: float,
        node_degree: float,
    ) -> float:
        """
        计算模块度增益 ΔQ。

        公式（Louvain 标准）：
        ΔQ = [Σ_in + k_i,in] / 2m - γ * [(Σ_tot + k_i) / 2m]²
           - [Σ_in / 2m - γ * (Σ_tot / 2m)² - γ * (k_i / 2m)²]

        其中：
        - Σ_in: 目标社区内部边权和
        - Σ_tot: 目标社区总度
        - k_i,in: 节点 i 到目标社区的边权和
        - k_i: 节点 i 的度
        - 2m: 总边权
        - γ: 分辨率参数
        """
        if self.total_weight == 0:
            return 0.0

        m2 = self.total_weight  # 2m
        gamma = self.cfg.resolution

        # 目标社区统计
        target_internal = self.community_internal.get(target_community, 0.0)
        target_degree = self.community_degree.get(target_community, 0.0)

        # 当前社区统计
        current_internal = self.community_internal.get(current_community, 0.0)
        current_degree = self.community_degree.get(current_community, 0.0)

        # 移除节点后当前社区的变化（用于计算移动后的模块度）
        # 注意：这里简化处理，不计入自环

        # 增益计算
        gain = (edge_weight_to_target / m2) - gamma * (
            (target_degree * node_degree) / (m2 * m2)
        )

        return gain

    def _move_node(
        self,
        atom_id: str,
        from_community: str,
        to_community: str,
    ) -> None:
        """将节点从旧社区移动到新社区，更新社区统计"""
        # 更新社区分配
        self.community[atom_id] = to_community

        # 更新旧社区：移除节点的度
        node_degree = sum(w for _, w in self.adjacency.get(atom_id, []))
        self.community_degree[from_community] = max(
            0, self.community_degree.get(from_community, 0.0) - node_degree
        )

        # 更新旧社区内部边权：减去节点到旧社区其他节点的边权
        for neighbor_id, weight in self.adjacency.get(atom_id, []):
            if self.community.get(neighbor_id) == from_community:
                self.community_internal[from_community] = max(
                    0, self.community_internal.get(from_community, 0.0) - weight
                )

        # 更新新社区：添加节点的度
        self.community_degree[to_community] = (
            self.community_degree.get(to_community, 0.0) + node_degree
        )

        # 更新新社区内部边权：添加节点到新社区其他节点的边权
        for neighbor_id, weight in self.adjacency.get(atom_id, []):
            if self.community.get(neighbor_id) == to_community:
                self.community_internal[to_community] = (
                    self.community_internal.get(to_community, 0.0) + weight
                )

    def _compute_modularity(self) -> float:
        """
        计算当前分区模块度 Q。

        公式：Q = 1/2m * Σ_ij [A_ij - γ * k_i * k_j / 2m] * δ(c_i, c_j)
        """
        if self.total_weight == 0:
            return 0.0

        m2 = self.total_weight
        gamma = self.cfg.resolution

        # 计算节点度
        degrees: dict[str, float] = {}
        for atom_id in self.atom_ids:
            degrees[atom_id] = sum(w for _, w in self.adjacency.get(atom_id, []))

        q = 0.0
        for edge in self.edges:
            i = edge.from_atom_id
            j = edge.to_atom_id
            if self.community.get(i) == self.community.get(j):
                w = edge.weight * edge.confidence
                q += w - gamma * degrees.get(i, 0.0) * degrees.get(j, 0.0) / m2

        return q / m2

    def _merge_small_communities(self) -> None:
        """合并小社区（< min_community_size）到相邻最大社区"""
        # 统计社区大小
        community_sizes: dict[str, int] = defaultdict(int)
        for atom_id, comm_id in self.community.items():
            community_sizes[comm_id] += 1

        small_communities = [
            cid for cid, size in community_sizes.items()
            if size < self.cfg.min_community_size
        ]

        for small_comm in small_communities:
            # 找到该社区节点连接最多的邻居社区
            neighbor_comm_weights: dict[str, float] = defaultdict(float)
            for atom_id, comm_id in self.community.items():
                if comm_id != small_comm:
                    continue
                for neighbor_id, weight in self.adjacency.get(atom_id, []):
                    neighbor_comm = self.community.get(neighbor_id)
                    if neighbor_comm and neighbor_comm != small_comm:
                        neighbor_comm_weights[neighbor_comm] += weight

            if not neighbor_comm_weights:
                continue

            # 合并到最大邻居社区
            target_comm = max(neighbor_comm_weights, key=neighbor_comm_weights.get)

            for atom_id, comm_id in list(self.community.items()):
                if comm_id == small_comm:
                    self.community[atom_id] = target_comm

    def get_communities(self) -> dict[str, list[str]]:
        """
        获取社区分组。

        Returns:
            {community_id: [atom_id, ...]}
        """
        communities: dict[str, list[str]] = defaultdict(list)
        for atom_id, comm_id in self.community.items():
            communities[comm_id].append(atom_id)
        return dict(communities)

    def get_stats(self) -> dict:
        """获取社区检测统计"""
        communities = self.get_communities()
        sizes = [len(members) for members in communities.values()]

        if not sizes:
            return {
                "num_communities": 0,
                "modularity": 0.0,
                "avg_community_size": 0.0,
                "max_community_size": 0,
                "min_community_size": 0,
            }

        return {
            "num_communities": len(communities),
            "modularity": self.modularity,
            "avg_community_size": sum(sizes) / len(sizes),
            "max_community_size": max(sizes),
            "min_community_size": min(sizes),
        }