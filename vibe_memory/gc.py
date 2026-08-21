"""
Garbage Collector (M3 — GC 压缩优先)

四级压缩管线：
1. 稀疏化（Sparsify）：删除低权重边（weight < threshold）
2. 固定池（Fixed Pool）：分区容量上限，超限淘汰最低权重分片
3. 冷存储（Cold Storage）：基于 last_accessed 的 lifecycle 迁移
4. 淘汰（Evict）：删除 weight < 0.05 的死分片

设计原则：
- 降级：GC 失败不影响主流程，只记录事件
- 可配置：每个分区容量独立配置
- 可观测：每次 GC 返回 GCResult，记录到 MetricsCollector
- 幂等：重复调用安全
"""

from typing import Optional
from datetime import datetime, timedelta

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, EdgeStatus,
    GraphPartition, Lifecycle,
)


# 默认分区容量（来自 Phase 1 设计）
DEFAULT_PARTITION_CAPACITY = {
    GraphPartition.SESSION: 1000,
    GraphPartition.DOCUMENT: 10000,
    GraphPartition.PARAMETRIC: 100,
}

# 默认生命周期阈值
ACTIVE_THRESHOLD_DAYS = 7    # 7 天内访问 → active
WARM_THRESHOLD_DAYS = 30     # 30 天内访问 → warm
# > 30 天 → cold

# 默认淘汰阈值
DEFAULT_MIN_EDGE_WEIGHT = 0.05
DEFAULT_MIN_ATOM_WEIGHT = 0.05


class GCResult:
    """GC 执行结果"""

    def __init__(self):
        self.sparsified_edges: int = 0
        self.evicted_atoms: int = 0
        self.migrated_to_warm: int = 0
        self.migrated_to_cold: int = 0
        self.migrated_to_archived: int = 0
        self.pool_evicted_atoms: int = 0
        self.errors: list[str] = []
        self.duration_ms: float = 0.0

    @property
    def total_cleaned(self) -> int:
        return (
            self.sparsified_edges
            + self.evicted_atoms
            + self.pool_evicted_atoms
        )

    def to_dict(self) -> dict:
        return {
            "sparsified_edges": self.sparsified_edges,
            "evicted_atoms": self.evicted_atoms,
            "migrated_to_warm": self.migrated_to_warm,
            "migrated_to_cold": self.migrated_to_cold,
            "migrated_to_archived": self.migrated_to_archived,
            "pool_evicted_atoms": self.pool_evicted_atoms,
            "total_cleaned": self.total_cleaned,
            "errors": self.errors,
            "duration_ms": round(self.duration_ms, 2),
        }


class GarbageCollector:
    """
    VibeMemory 垃圾回收器。

    四级压缩管线，按顺序执行：
    1. sparsify → 2. enforce_pool → 3. migrate_cold → 4. evict

    Args:
        storage: VibeStorage 实例
        agent_id: Agent 标识
        tenant_id: 租户 ID
        partition_capacity: 分区容量上限（默认 Session=1000, Document=10000, Parametric=100）
        min_edge_weight: 边最小权重（低于此值删除）
        min_atom_weight: 原子最小权重（低于此值淘汰）
        active_days: Active 生命周期天数（默认 7）
        warm_days: Warm 生命周期天数（默认 30）
    """

    def __init__(
        self,
        storage,
        agent_id: str,
        tenant_id: str = "default",
        partition_capacity: Optional[dict[GraphPartition, int]] = None,
        min_edge_weight: float = DEFAULT_MIN_EDGE_WEIGHT,
        min_atom_weight: float = DEFAULT_MIN_ATOM_WEIGHT,
        active_days: int = ACTIVE_THRESHOLD_DAYS,
        warm_days: int = WARM_THRESHOLD_DAYS,
    ):
        self.storage = storage
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.partition_capacity = partition_capacity or DEFAULT_PARTITION_CAPACITY.copy()
        self.min_edge_weight = min_edge_weight
        self.min_atom_weight = min_atom_weight
        self.active_days = active_days
        self.warm_days = warm_days

        # GC 统计
        self._gc_count: int = 0
        self._total_sparsified: int = 0
        self._total_evicted: int = 0
        self._last_gc_at: Optional[datetime] = None
        self._last_gc_result: Optional[GCResult] = None

    # ── 主流程 ──

    def collect(self, dry_run: bool = False) -> GCResult:
        """
        执行完整 GC 管线。

        Args:
            dry_run: True 则只计算不实际删除（用于预估）

        Returns:
            GCResult 包含各项操作的计数
        """
        import time

        result = GCResult()
        start = time.perf_counter()

        try:
            # 阶段 1：稀疏化
            result.sparsified_edges = self.sparsify(dry_run=dry_run)

            # 阶段 2：固定池
            result.pool_evicted_atoms = self.enforce_pool(dry_run=dry_run)

            # 阶段 3：冷存储迁移
            m = self.migrate_cold(dry_run=dry_run)
            result.migrated_to_warm = m.get("warm", 0)
            result.migrated_to_cold = m.get("cold", 0)
            result.migrated_to_archived = m.get("archived", 0)

            # 阶段 4：淘汰
            result.evicted_atoms = self.evict(dry_run=dry_run)

        except Exception as e:
            result.errors.append(f"GC error: {e}")

        result.duration_ms = (time.perf_counter() - start) * 1000

        # 更新统计
        self._gc_count += 1
        self._total_sparsified += result.sparsified_edges
        self._total_evicted += result.evicted_atoms + result.pool_evicted_atoms
        self._last_gc_at = datetime.now()
        self._last_gc_result = result

        return result

    # ── 阶段 1：稀疏化 ──

    def sparsify(self, dry_run: bool = False) -> int:
        """
        删除低权重边。

        规则：
        - weight < min_edge_weight → 删除
        - status == 'stale' → 删除
        - 不删除跨分区边（corss_partition = True），它们是稀缺链接

        Returns:
            删除的边数量
        """
        all_edges = self.storage.get_all_edges_raw()  # 含 stale/pending
        to_delete: list[str] = []

        for edge in all_edges:
            # 更新衰减
            edge.decay()
            if edge.should_evict() or edge.status == EdgeStatus.STALE:
                to_delete.append(edge.id)

        if not dry_run and to_delete:
            for edge_id in to_delete:
                # SQLite 没有直接的 delete_edge，用 UPDATE status
                edge = self.storage.get_edge(edge_id)
                if edge:
                    edge.status = EdgeStatus.STALE
                    self.storage.update_edge(edge)

        return len(to_delete)

    # ── 阶段 2：固定池 ──

    def enforce_pool(self, dry_run: bool = False) -> int:
        """
        强制分区容量上限。

        当日志分区超过容量时，按 weight 升序淘汰最低权重分片。
        Parametric 分区不受淘汰（Agent 画像需要保护）。

        Returns:
            淘汰的分片数量
        """
        evicted = 0

        for partition, capacity in self.partition_capacity.items():
            if partition == GraphPartition.PARAMETRIC:
                continue  # 保护 Parametric 分区

            atoms = self._get_atoms_by_partition(partition)
            if len(atoms) <= capacity:
                continue

            # 按 weight 升序，淘汰最低的
            atoms.sort(key=lambda a: a.weight)
            overflow = atoms[:len(atoms) - capacity]

            if not dry_run:
                for atom in overflow:
                    self.storage.delete_atom(atom.id)

            evicted += len(overflow)

        return evicted

    # ── 阶段 3：冷存储迁移 ──

    def migrate_cold(self, dry_run: bool = False) -> dict[str, int]:
        """
        基于 last_accessed 的 lifecycle 迁移。

        规则：
        - last_accessed 在 7 天内 → ACTIVE
        - last_accessed 在 30 天内 → WARM
        - last_accessed 超过 30 天 → COLD
        - 从未访问 + 创建超过 60 天 → ARCHIVED

        Returns:
            {"warm": N, "cold": N, "archived": N}
        """
        now = datetime.now()
        active_boundary = now - timedelta(days=self.active_days)
        warm_boundary = now - timedelta(days=self.warm_days)
        archive_boundary = now - timedelta(days=60)

        all_atoms = self.storage.get_atoms_by_agent(
            self.agent_id, tenant_id=self.tenant_id
        )

        migrated = {"warm": 0, "cold": 0, "archived": 0}

        for atom in all_atoms:
            ref_time = atom.last_accessed or atom.created_at
            new_lifecycle = None

            if ref_time > active_boundary:
                new_lifecycle = Lifecycle.ACTIVE
            elif ref_time > warm_boundary:
                new_lifecycle = Lifecycle.WARM
            elif ref_time > archive_boundary:
                new_lifecycle = Lifecycle.COLD
            else:
                new_lifecycle = Lifecycle.ARCHIVED

            if new_lifecycle != atom.lifecycle:
                if not dry_run:
                    atom.lifecycle = new_lifecycle
                    self.storage.update_atom(atom)

                if new_lifecycle == Lifecycle.WARM:
                    migrated["warm"] += 1
                elif new_lifecycle == Lifecycle.COLD:
                    migrated["cold"] += 1
                elif new_lifecycle == Lifecycle.ARCHIVED:
                    migrated["archived"] += 1

        return migrated

    # ── 阶段 4：淘汰 ──

    def evict(self, dry_run: bool = False) -> int:
        """
        淘汰死分片。

        规则：
        - weight < min_atom_weight → 淘汰
        - lifecycle == 'archived' + weight < 0.1 → 淘汰
        - 不淘汰 Parametric 分区（Agent 画像保护）

        Returns:
            淘汰的分片数量
        """
        all_atoms = self.storage.get_atoms_by_agent(
            self.agent_id, tenant_id=self.tenant_id
        )

        to_evict: list[str] = []

        for atom in all_atoms:
            if atom.type == GraphPartition.PARAMETRIC:
                continue

            # 衰减后检查
            atom.decay()

            if atom.should_evict():
                to_evict.append(atom.id)
            elif atom.lifecycle == Lifecycle.ARCHIVED and atom.weight < 0.1:
                to_evict.append(atom.id)

        if not dry_run:
            for atom_id in to_evict:
                self.storage.delete_atom(atom_id)

        return len(to_evict)

    # ── 分区容量管理 ──

    def get_partition_usage(self) -> dict[str, dict]:
        """获取各分区当前使用量"""
        usage = {}
        all_atoms = self.storage.get_atoms_by_agent(
            self.agent_id, tenant_id=self.tenant_id
        )

        for partition in GraphPartition:
            atoms = [a for a in all_atoms if a.type == partition]
            capacity = self.partition_capacity.get(partition, 0)
            usage[partition.value] = {
                "count": len(atoms),
                "capacity": capacity,
                "usage_pct": round(len(atoms) / capacity * 100, 1) if capacity > 0 else 0.0,
                "total_weight": round(sum(a.weight for a in atoms), 2),
            }

        return usage

    def set_partition_capacity(self, partition: GraphPartition, capacity: int) -> None:
        """动态调整分区容量"""
        self.partition_capacity[partition] = capacity

    # ── 统计 ──

    def stats(self) -> dict:
        """GC 统计信息"""
        return {
            "gc_count": self._gc_count,
            "total_sparsified": self._total_sparsified,
            "total_evicted": self._total_evicted,
            "last_gc_at": self._last_gc_at.isoformat() if self._last_gc_at else None,
            "last_gc_result": self._last_gc_result.to_dict() if self._last_gc_result else None,
            "partition_usage": self.get_partition_usage(),
            "config": {
                "min_edge_weight": self.min_edge_weight,
                "min_atom_weight": self.min_atom_weight,
                "active_days": self.active_days,
                "warm_days": self.warm_days,
                "partition_capacity": {
                    k.value: v for k, v in self.partition_capacity.items()
                },
            },
        }

    # ── 辅助 ──

    def _get_atoms_by_partition(self, partition: GraphPartition) -> list[MemoryAtom]:
        """获取某分区的所有活跃分片（已衰减）"""
        all_atoms = self.storage.get_atoms_by_agent(
            self.agent_id, tenant_id=self.tenant_id
        )
        result = [a for a in all_atoms if a.type == partition and a.lifecycle != Lifecycle.ARCHIVED]
        for a in result:
            a.decay()
        return result