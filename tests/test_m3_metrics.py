"""
Metrics Collector Tests (M3)

Verifies:
1. Latency measurement: measure() context manager
2. Operation counting: record_store/recall/edge_built
3. Edge source distribution: rule/llm/learner
4. Recall hit rate: result count tracking
5. Degradation event recording
6. Graph size snapshots
7. Cold start phase tracking
8. Stats aggregation: full stats() output
9. Reset: all counters back to zero
10. SDK integration: metrics in stats() output
11. Empty stats: no operations → zeros
12. Multiple operations: cumulative counts
"""

import time

from vibe_memory.metrics import MetricsCollector
from vibe_memory.sdk import VibeMemory


# ── Tests ──

def test_measure_latency():
    """Test: measure() context manager records latency"""
    m = MetricsCollector()

    with m.measure("store"):
        time.sleep(0.01)

    stats = m.stats()
    assert "store" in stats["latency_ms"]
    assert stats["latency_ms"]["store"]["count"] == 1
    assert stats["latency_ms"]["store"]["min_ms"] > 0
    # avg should be roughly 10ms (sleep 0.01s)
    assert 1 < stats["latency_ms"]["store"]["avg_ms"] < 100

    print("[PASS] measure latency test")


def test_measure_async():
    """Test: measure_async() records manual latency"""
    m = MetricsCollector()
    m.measure_async("recall", 42.5)

    stats = m.stats()
    assert stats["latency_ms"]["recall"]["count"] == 1
    assert stats["latency_ms"]["recall"]["avg_ms"] == 42.5

    print("[PASS] measure async test")


def test_record_operations():
    """Test: operation counting"""
    m = MetricsCollector()

    m.record_store()
    m.record_store()
    m.record_store()
    m.record_recall(result_count=3)
    m.record_recall(result_count=5)
    m.record_edge_built(source="rule")
    m.record_episode_built()
    m.record_chunk_created()

    stats = m.stats()
    ops = stats["operations"]
    assert ops["store"] == 3
    assert ops["recall"] == 2
    assert ops["edge_build"] == 1
    assert ops["episode_build"] == 1
    assert ops["chunk"] == 1

    print("[PASS] record operations test")


def test_edge_source_distribution():
    """Test: edge source and label distribution"""
    m = MetricsCollector()

    m.record_edge_built(source="rule", label="因果接续")
    m.record_edge_built(source="rule", label="同类经验")
    m.record_edge_built(source="llm", label="因果接续")
    m.record_edge_built(source="rule", label="同类经验")
    m.record_edge_built(source="learner", label="修正推翻")

    stats = m.stats()
    assert stats["edge_sources"] == {"rule": 3, "llm": 1, "learner": 1}
    assert stats["edge_labels"] == {"因果接续": 2, "同类经验": 2, "修正推翻": 1}

    print("[PASS] edge source distribution test")


def test_recall_hit_rate():
    """Test: recall hit rate aggregation"""
    m = MetricsCollector()

    m.record_recall(result_count=0)
    m.record_recall(result_count=5)
    m.record_recall(result_count=3)
    m.record_recall(result_count=0)
    m.record_recall(result_count=10)

    stats = m.stats()
    hr = stats["recall_hit_rate"]
    assert hr["total_recalls"] == 5
    assert hr["min_results"] == 0
    assert hr["max_results"] == 10
    assert hr["zero_hit_rate"] == 0.4  # 2/5 = 0.4

    print("[PASS] recall hit rate test")


def test_degradation_events():
    """Test: degradation event recording"""
    m = MetricsCollector()

    m.record_degradation("ppr_to_topk")
    m.record_degradation("ppr_to_topk")
    m.record_degradation("llm_to_rule")
    m.record_degradation("learner_to_fixed")
    m.record_degradation("custom_fallback")

    stats = m.stats()
    deg = stats["degradation"]
    assert deg["PPR 超时 → 向量 Top-K"] == 2
    assert deg["LLM 建边 → 规则边"] == 1
    assert deg["Vibe Learner → 固定衰减"] == 1
    assert "custom_fallback" in deg

    print("[PASS] degradation events test")


def test_graph_size_snapshots():
    """Test: graph size snapshot tracking"""
    m = MetricsCollector()

    m.snapshot_graph_size(atoms=10, edges=5, active_atoms=8, warm_atoms=2)
    m.snapshot_graph_size(atoms=20, edges=15, active_atoms=15, warm_atoms=4, cold_atoms=1)
    m.snapshot_graph_size(atoms=15, edges=10, active_atoms=10, warm_atoms=3, cold_atoms=2)

    stats = m.stats()
    gs = stats["graph_size"]
    assert gs["snapshot_count"] == 3
    assert gs["current"]["atoms"] == 15
    assert gs["current"]["edges"] == 10
    assert gs["peak"]["atoms"] == 20
    assert gs["peak"]["edges"] == 15

    print("[PASS] graph size snapshots test")


def test_cold_start_phase_tracking():
    """Test: cold start phase transition recording"""
    m = MetricsCollector()

    m.record_cold_start_phase("cold")
    m.record_cold_start_phase("cold")
    m.record_cold_start_phase("warmup")
    m.record_cold_start_phase("normal")

    stats = m.stats()
    cs = stats["cold_start"]
    assert cs["transition_count"] == 4
    assert len(cs["phase_history"]) == 4
    assert cs["phase_history"][0]["phase"] == "cold"
    assert cs["phase_history"][-1]["phase"] == "normal"

    print("[PASS] cold start phase tracking test")


def test_timestamps():
    """Test: timestamp tracking"""
    m = MetricsCollector()

    # Should have created_at
    stats = m.stats()
    assert stats["timestamps"]["created"] is not None
    assert stats["timestamps"]["first_store"] is None
    assert stats["timestamps"]["first_recall"] is None

    m.record_store()
    m.record_recall()

    stats = m.stats()
    assert stats["timestamps"]["first_store"] is not None
    assert stats["timestamps"]["first_recall"] is not None
    assert stats["timestamps"]["last_store"] is not None
    assert stats["timestamps"]["last_recall"] is not None

    print("[PASS] timestamps test")


def test_uptime():
    """Test: uptime calculation"""
    m = MetricsCollector()

    stats = m.stats()
    assert stats["uptime_seconds"] >= 0
    assert stats["uptime_seconds"] < 10  # just created

    print("[PASS] uptime test")


def test_reset():
    """Test: reset() clears all metrics"""
    m = MetricsCollector()

    m.record_store()
    m.record_recall(result_count=5)
    m.record_edge_built(source="rule")
    m.record_degradation("ppr_to_topk")
    m.snapshot_graph_size(atoms=10, edges=5)

    assert m.stats()["operations"]["store"] == 1

    m.reset()

    stats = m.stats()
    assert stats["operations"]["store"] == 0
    assert stats["operations"]["recall"] == 0
    assert stats["recall_hit_rate"]["total_recalls"] == 0
    assert stats["graph_size"]["snapshot_count"] == 0
    assert len(stats["degradation"]) == 0

    print("[PASS] reset test")


def test_empty_stats():
    """Test: stats() on fresh collector returns zeros"""
    m = MetricsCollector()

    stats = m.stats()

    assert stats["operations"]["store"] == 0
    assert stats["operations"]["recall"] == 0
    assert stats["recall_hit_rate"]["total_recalls"] == 0
    assert stats["recall_hit_rate"]["zero_hit_rate"] == 0.0
    assert stats["graph_size"]["snapshot_count"] == 0
    assert stats["graph_size"]["current"]["atoms"] == 0

    # Latency summary for empty should return zeros
    assert "store" not in stats["latency_ms"] or stats["latency_ms"].get("store", {}).get("count", 0) == 0

    print("[PASS] empty stats test")


def test_multiple_operations_latency():
    """Test: multiple operations produce correct p50/p95/p99"""
    m = MetricsCollector()

    for i in range(100):
        with m.measure("store"):
            time.sleep(0.001)  # ~1ms

    stats = m.stats()
    lat = stats["latency_ms"]["store"]
    assert lat["count"] == 100
    assert lat["min_ms"] > 0
    assert lat["p50_ms"] > 0
    assert lat["p95_ms"] > 0
    assert lat["p99_ms"] > 0
    # p50 ≤ p95 ≤ p99
    assert lat["p50_ms"] <= lat["p95_ms"] <= lat["p99_ms"]

    print("[PASS] multiple operations latency test")


def test_sdk_metrics_integration():
    """Test: SDK stats() includes metrics section"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    # Do some operations
    with mem.metrics.measure("store"):
        mem.store("Test content", session_id="s1", auto_build_edges=False)
    mem.recall("test")

    stats = mem.stats()
    assert "metrics" in stats
    m = stats["metrics"]

    assert "operations" in m
    assert "latency_ms" in m
    assert "recall_hit_rate" in m
    assert "graph_size" in m
    assert "degradation" in m
    assert "timestamps" in m

    # Operations should be counted
    assert m["operations"]["store"] >= 1
    assert m["operations"]["recall"] >= 1

    # Latency should be recorded
    assert "store" in m["latency_ms"]

    # Graph size should be snapshot
    assert m["graph_size"]["current"]["atoms"] >= 1

    print("[PASS] SDK metrics integration test")


def test_sdk_edge_metrics():
    """Test: edge building is tracked in metrics"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    mem.store("API timeout error", session_id="s1", tags=["error", "config"])
    mem.store("Changed timeout to 60s", session_id="s1", tags=["config"])

    stats = mem.stats()
    m = stats["metrics"]

    assert m["operations"]["edge_build"] >= 1
    assert "edge_sources" in m
    assert "rule" in m["edge_sources"]

    print("[PASS] SDK edge metrics test")


def test_sdk_degradation_tracking():
    """Test: SDK can track degradation events"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    mem.metrics.record_degradation("ppr_to_topk")
    mem.metrics.record_degradation("seed_filter_skipped")

    stats = mem.stats()
    deg = stats["metrics"]["degradation"]
    assert "PPR 超时 → 向量 Top-K" in deg
    assert "种子过滤跳过（种子不足）" in deg

    print("[PASS] SDK degradation tracking test")


def test_sdk_recall_hit_rate():
    """Test: recall hit rate tracked across multiple recalls"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    # Store some content
    mem.store("API timeout error", session_id="s1", tags=["error"])
    mem.store("DB pool config", session_id="s2", tags=["config"])

    # Multiple recalls
    mem.recall("API timeout")
    mem.recall("nonexistent query")
    mem.recall("config")

    stats = mem.stats()
    hr = stats["metrics"]["recall_hit_rate"]
    assert hr["total_recalls"] == 3

    print("[PASS] SDK recall hit rate test")


def run_all():
    print("=" * 50)
    print("VibeMemory M3 Metrics Tests")
    print("=" * 50)

    test_measure_latency()
    test_measure_async()
    test_record_operations()
    test_edge_source_distribution()
    test_recall_hit_rate()
    test_degradation_events()
    test_graph_size_snapshots()
    test_cold_start_phase_tracking()
    test_timestamps()
    test_uptime()
    test_reset()
    test_empty_stats()
    test_multiple_operations_latency()
    test_sdk_metrics_integration()
    test_sdk_edge_metrics()
    test_sdk_degradation_tracking()
    test_sdk_recall_hit_rate()

    print()
    print("=" * 50)
    print("All metrics tests passed [PASS]")
    print("=" * 50)


if __name__ == "__main__":
    run_all()