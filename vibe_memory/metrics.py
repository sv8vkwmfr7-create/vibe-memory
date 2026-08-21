"""
Metrics Collector (M3 — 可观测性)

追踪 VibeMemory 运行时指标：

维度：
- 延迟：store/recall/edge_build 操作耗时（ms）
- 吞吐：store/recall 操作计数
- 图规模：atoms/edges/episodes 数量随时间变化
- 边来源分布：rule/llm/learner 占比
- 检索命中率：recall 结果数分布
- 降级事件：各模块 fallback 触发次数
- 冷启动阶段：cold/warmup/normal 过渡时间

设计原则：
- 纯内存，零外部依赖（不引入 Prometheus）
- stats() 方法暴露所有指标
- 支持 reset() 用于测试隔离
- 不阻塞主流程（所有记录操作 O(1)）
"""

import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
from contextlib import contextmanager


class MetricsCollector:
    """
    运行时指标收集器。

    使用方式：
        metrics = MetricsCollector()

        with metrics.measure("store"):
            mem.store(content)

        with metrics.measure("recall"):
            mem.recall(query)

        metrics.record_edge_built(source="rule")
        metrics.record_recall_result(count=5)
        metrics.snapshot_graph_size(atoms=100, edges=200)
    """

    def __init__(self):
        # 操作延迟（ms）：{operation_name: [latencies]}
        self._latencies: dict[str, list[float]] = defaultdict(list)

        # 操作计数
        self._store_count: int = 0
        self._recall_count: int = 0
        self._edge_build_count: int = 0
        self._episode_build_count: int = 0
        self._chunk_count: int = 0

        # 边来源分布
        self._edge_sources: dict[str, int] = defaultdict(int)

        # 边标签分布
        self._edge_labels: dict[str, int] = defaultdict(int)

        # 检索结果数分布
        self._recall_result_counts: list[int] = []

        # 降级事件
        self._degradation_events: dict[str, int] = defaultdict(int)
        # 已知降级类型
        self._DEGRADATION_TYPES = {
            "ppr_to_topk": "PPR 超时 → 向量 Top-K",
            "llm_to_rule": "LLM 建边 → 规则边",
            "learner_to_fixed": "Vibe Learner → 固定衰减",
            "graphdb_to_vector": "图 DB → 纯向量检索",
            "seed_filter_skipped": "种子过滤跳过（种子不足）",
        }

        # 图规模快照（时间序列）
        self._graph_size_snapshots: list[dict] = []

        # 冷启动阶段历史
        self._cold_start_phase_history: list[dict] = []

        # 创建时间（用于计算 uptime）
        self._created_at: datetime = datetime.now()

        # 首次 store/recall 时间
        self._first_store_at: Optional[datetime] = None
        self._first_recall_at: Optional[datetime] = None
        self._last_store_at: Optional[datetime] = None
        self._last_recall_at: Optional[datetime] = None

    # ── 延迟测量 ──

    @contextmanager
    def measure(self, operation: str):
        """上下文管理器：测量操作延迟。

        with metrics.measure("store"):
            ...
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._latencies[operation].append(elapsed_ms)

    def measure_async(self, operation: str, elapsed_ms: float) -> None:
        """手动记录延迟（用于 async 操作）"""
        self._latencies[operation].append(elapsed_ms)

    # ── 操作计数 ──

    def record_store(self, atom_count: int = 1) -> None:
        """记录一次 store 操作"""
        self._store_count += 1
        now = datetime.now()
        if self._first_store_at is None:
            self._first_store_at = now
        self._last_store_at = now

    def record_recall(self, result_count: int = 0) -> None:
        """记录一次 recall 操作"""
        self._recall_count += 1
        self._recall_result_counts.append(result_count)
        now = datetime.now()
        if self._first_recall_at is None:
            self._first_recall_at = now
        self._last_recall_at = now

    def record_edge_built(self, source: str = "rule", label: Optional[str] = None) -> None:
        """记录一条边被创建"""
        self._edge_build_count += 1
        self._edge_sources[source] += 1
        if label:
            self._edge_labels[label] += 1

    def record_episode_built(self) -> None:
        """记录一次 Episode 聚合"""
        self._episode_build_count += 1

    def record_chunk_created(self) -> None:
        """记录一次分片创建"""
        self._chunk_count += 1

    # ── 降级事件 ──

    def record_degradation(self, event_type: str) -> None:
        """记录一次降级事件。

        Args:
            event_type: "ppr_to_topk" | "llm_to_rule" | "learner_to_fixed" | "graphdb_to_vector" | "seed_filter_skipped"
        """
        if event_type in self._DEGRADATION_TYPES:
            self._degradation_events[event_type] += 1
        else:
            self._degradation_events[event_type] += 1

    # ── 图规模快照 ──

    def snapshot_graph_size(
        self,
        atoms: int,
        edges: int,
        episodes: int = 0,
        active_atoms: int = 0,
        warm_atoms: int = 0,
        cold_atoms: int = 0,
    ) -> None:
        """记录一次图规模快照"""
        self._graph_size_snapshots.append({
            "timestamp": datetime.now().isoformat(),
            "atoms": atoms,
            "edges": edges,
            "episodes": episodes,
            "active_atoms": active_atoms,
            "warm_atoms": warm_atoms,
            "cold_atoms": cold_atoms,
        })

    def record_cold_start_phase(self, phase: str) -> None:
        """记录冷启动阶段变更"""
        self._cold_start_phase_history.append({
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
        })

    # ── 统计聚合 ──

    def stats(self) -> dict:
        """
        聚合所有指标，返回可读的统计字典。

        Returns:
            {
                uptime_seconds, operations: {store/recall/edge_build},
                latency: {store/recall/edge_build: {min/max/avg/p50/p95/p99}},
                edge_sources: {rule/llm/learner: count},
                edge_labels: {label: count},
                recall_hit_rate: {total, min/max/avg/p50/p95},
                graph_size: {current, peak, snapshots},
                degradation: {event_type: count},
                cold_start: {phase_history, transitions},
                timestamps: {created, first_store, first_recall}
            }
        """
        uptime = (datetime.now() - self._created_at).total_seconds()

        return {
            "uptime_seconds": round(uptime, 1),
            "operations": {
                "store": self._store_count,
                "recall": self._recall_count,
                "edge_build": self._edge_build_count,
                "episode_build": self._episode_build_count,
                "chunk": self._chunk_count,
            },
            "latency_ms": {
                op: self._latency_summary(latencies)
                for op, latencies in self._latencies.items()
            },
            "edge_sources": dict(self._edge_sources),
            "edge_labels": dict(self._edge_labels),
            "recall_hit_rate": self._recall_hit_rate_summary(),
            "graph_size": self._graph_size_summary(),
            "degradation": {
                self._DEGRADATION_TYPES.get(k, k): v
                for k, v in self._degradation_events.items()
            },
            "cold_start": {
                "phase_history": self._cold_start_phase_history[-20:],  # 最近 20 次
                "transition_count": len(self._cold_start_phase_history),
            },
            "timestamps": {
                "created": self._created_at.isoformat(),
                "first_store": self._first_store_at.isoformat() if self._first_store_at else None,
                "first_recall": self._first_recall_at.isoformat() if self._first_recall_at else None,
                "last_store": self._last_store_at.isoformat() if self._last_store_at else None,
                "last_recall": self._last_recall_at.isoformat() if self._last_recall_at else None,
            },
        }

    def _latency_summary(self, latencies: list[float]) -> dict:
        """计算延迟分布统计"""
        if not latencies:
            return {"count": 0, "min_ms": 0, "max_ms": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0}

        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        return {
            "count": n,
            "min_ms": round(sorted_lat[0], 2),
            "max_ms": round(sorted_lat[-1], 2),
            "avg_ms": round(sum(sorted_lat) / n, 2),
            "p50_ms": round(sorted_lat[n * 50 // 100], 2),
            "p95_ms": round(sorted_lat[min(n * 95 // 100, n - 1)], 2),
            "p99_ms": round(sorted_lat[min(n * 99 // 100, n - 1)], 2),
        }

    def _recall_hit_rate_summary(self) -> dict:
        """计算检索命中率统计"""
        if not self._recall_result_counts:
            return {"total_recalls": 0, "min_results": 0, "max_results": 0, "avg_results": 0, "p50_results": 0, "p95_results": 0, "zero_hit_rate": 0.0}

        counts = self._recall_result_counts
        sorted_counts = sorted(counts)
        n = len(sorted_counts)
        zero_hits = sum(1 for c in counts if c == 0)

        return {
            "total_recalls": n,
            "min_results": sorted_counts[0],
            "max_results": sorted_counts[-1],
            "avg_results": round(sum(counts) / n, 2),
            "p50_results": sorted_counts[n * 50 // 100],
            "p95_results": sorted_counts[min(n * 95 // 100, n - 1)],
            "zero_hit_rate": round(zero_hits / n, 4) if n > 0 else 0.0,
        }

    def _graph_size_summary(self) -> dict:
        """计算图规模变化摘要"""
        if not self._graph_size_snapshots:
            return {
                "current": {"atoms": 0, "edges": 0, "episodes": 0},
                "peak": {"atoms": 0, "edges": 0, "episodes": 0},
                "snapshot_count": 0,
            }

        current = self._graph_size_snapshots[-1]
        peak_atoms = max(s["atoms"] for s in self._graph_size_snapshots)
        peak_edges = max(s["edges"] for s in self._graph_size_snapshots)
        peak_episodes = max(s["episodes"] for s in self._graph_size_snapshots)

        return {
            "current": {
                "atoms": current["atoms"],
                "edges": current["edges"],
                "episodes": current["episodes"],
                "active": current.get("active_atoms", 0),
                "warm": current.get("warm_atoms", 0),
                "cold": current.get("cold_atoms", 0),
            },
            "peak": {
                "atoms": peak_atoms,
                "edges": peak_edges,
                "episodes": peak_episodes,
            },
            "snapshot_count": len(self._graph_size_snapshots),
        }

    # ── 生命周期 ──

    def reset(self) -> None:
        """重置所有指标（用于测试）"""
        self._latencies.clear()
        self._store_count = 0
        self._recall_count = 0
        self._edge_build_count = 0
        self._episode_build_count = 0
        self._chunk_count = 0
        self._edge_sources.clear()
        self._edge_labels.clear()
        self._recall_result_counts.clear()
        self._degradation_events.clear()
        self._graph_size_snapshots.clear()
        self._cold_start_phase_history.clear()
        self._created_at = datetime.now()
        self._first_store_at = None
        self._first_recall_at = None
        self._last_store_at = None
        self._last_recall_at = None