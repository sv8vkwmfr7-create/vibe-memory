from vibe_memory.metrics import MetricsCollector
from vibe_memory import VibeMemory


def test_latency_keeps_recent_samples_only():
    metrics = MetricsCollector()
    metrics.measure_async("store", 99999)
    for i in range(1100):
        metrics.measure_async("store", i)
        metrics.record_store()
    assert list(metrics._latencies["store"]) == list(range(100, 1100))
    stats = metrics.stats()
    assert stats["operations"]["store"] == 1100
    assert stats["latency_ms"]["store"] == {
        "count": 1000, "min_ms": 100, "max_ms": 1099, "avg_ms": 599.5,
        "p50_ms": 600, "p95_ms": 1050, "p99_ms": 1090,
    }


def test_recall_window_is_separate_from_total_recalls():
    metrics = MetricsCollector()
    for i in range(1100):
        metrics.record_recall(0 if i < 100 else 5)
    assert len(metrics._recall_result_counts) == 1000
    stats = metrics.stats()
    assert stats["operations"]["recall"] == 1100
    assert stats["recall_hit_rate"]["total_recalls"] == 1100
    assert stats["recall_hit_rate"]["sample_count"] == 1000
    assert stats["recall_hit_rate"]["zero_hit_rate"] == 0
    assert stats["recall_hit_rate"]["avg_results"] == 5


def test_graph_and_phase_history_are_bounded_without_losing_totals_or_peak():
    metrics = MetricsCollector()
    metrics.snapshot_graph_size(atoms=9999, edges=8888, episodes=7777)
    for i in range(1100):
        metrics.snapshot_graph_size(atoms=i, edges=i, episodes=i)
        metrics.record_cold_start_phase(str(i))
    assert len(metrics._graph_size_snapshots) == 1000
    assert len(metrics._cold_start_phase_history) == 20
    stats = metrics.stats()
    assert stats["graph_size"]["peak"] == {"atoms": 9999, "edges": 8888, "episodes": 7777}
    assert stats["graph_size"]["snapshot_count"] == 1101
    assert stats["graph_size"]["current"]["atoms"] == 1099
    assert stats["cold_start"]["transition_count"] == 1100
    assert [row["phase"] for row in stats["cold_start"]["phase_history"]] == [str(i) for i in range(1080, 1100)]


def test_reset_clears_cumulative_and_window_state_and_can_record_again():
    metrics = MetricsCollector()
    metrics.measure_async("store", 100)
    metrics.record_store()
    metrics.record_recall(5)
    metrics.snapshot_graph_size(atoms=9999, edges=99)
    metrics.record_cold_start_phase("normal")
    metrics.reset()
    metrics.snapshot_graph_size(atoms=1, edges=2)
    metrics.record_recall(0)
    metrics.record_cold_start_phase("cold")
    stats = metrics.stats()
    assert stats["latency_ms"] == {}
    assert stats["operations"]["store"] == 0
    assert stats["recall_hit_rate"]["total_recalls"] == 1
    assert stats["graph_size"]["peak"] == {"atoms": 1, "edges": 2, "episodes": 0}
    assert stats["graph_size"]["snapshot_count"] == 1
    assert stats["cold_start"]["transition_count"] == 1


def test_context_measure_and_sdk_stats_expose_retention_policy():
    memory = VibeMemory(agent_id="metrics-test", embedding_backend="tfidf")
    try:
        for _ in range(1001):
            with memory.metrics.measure("store"):
                pass
        stats = memory.stats()["metrics"]
        assert stats["latency_ms"]["store"]["count"] == 1000
        assert stats["sampling"] == {
            "scope": "recent_samples", "sample_limit": 1000, "phase_history_limit": 20,
        }
    finally:
        memory.storage.conn.close()
