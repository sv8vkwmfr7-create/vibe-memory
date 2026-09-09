"""Measure SDK scale, latency, and write-after-read visibility.

The benchmark exercises the public :class:`VibeMemory` SDK against an
in-memory SQLite store with automatic edge building and Episode aggregation
disabled.  This isolates the core write path and the normal ``recall()`` path;
edge-building cost remains covered by the existing six-dimension benchmark.

Default scale points are 1,000, 10,000, and 100,000 atoms.  Every write is
timed, a fixed sample of writes is read back immediately through
``storage.get_atom()`` (post-commit storage visibility), and a small fixed set
of queries measures full SDK recall latency.  The direct-read check is not an
asynchronous index or "new atom appears in recall" SLA.  The dataset and
queries are deterministic; latency is machine-dependent.

Usage::

    python experiments/scale_visibility_benchmark.py
    python experiments/scale_visibility_benchmark.py --scale 1000 10000 --json results/scale_visibility.json
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibe_memory import VibeMemory


DEFAULT_SCALES = (1_000, 10_000, 100_000)
BASE_RECALL_QUERIES = (
    "API timeout",
    "database configuration",
    "benchmark memory",
    "topic 5 context",
    "operational context",
)
DEFAULT_RECALL_SAMPLES = 20
DATASET_VERSION = "sdk-scale-visibility-v3"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "p50": round(_percentile(values, 50), 3),
        "p95": round(_percentile(values, 95), 3),
        "p99": round(_percentile(values, 99), 3),
    }


def _content(index: int) -> str:
    return (
        f"Scale benchmark memory {index}: API timeout and database "
        f"configuration context for topic {index % 10}."
    )


def _run_scale(scale: int, recall_queries: tuple[str, ...], visibility_checks: int) -> dict[str, object]:
    memory = VibeMemory(
        agent_id=f"scale-{scale}",
        db_path=":memory:",
        embedding_backend="tfidf",
    )
    write_latencies: list[float] = []
    visibility_latencies: list[float] = []
    visible_count = 0
    last_atom_id = ""
    check_every = max(1, scale // max(visibility_checks, 1))

    started = time.perf_counter()
    for index in range(scale):
        write_started = time.perf_counter()
        atom = memory.store(
            _content(index),
            session_id=f"scale-session-{index // 20}",
            auto_build_edges=False,
            auto_episode=False,
        )
        write_latencies.append((time.perf_counter() - write_started) * 1000)
        last_atom_id = atom.id

        # Check both the beginning and end of the run, plus evenly spaced
        # points.  SQLite commits each store, so this is a direct visibility
        # check rather than a cached SDK result.
        should_check = (
            index < visibility_checks
            or index >= scale - visibility_checks
            or index % check_every == 0
        )
        if should_check:
            read_started = time.perf_counter()
            visible = memory.storage.get_atom(atom.id) is not None
            visibility_latencies.append((time.perf_counter() - read_started) * 1000)
            visible_count += int(visible)

    store_elapsed = time.perf_counter() - started

    recall_latencies: list[float] = []
    recall_counts: list[int] = []
    for query in recall_queries:
        recall_started = time.perf_counter()
        result = memory.recall(query, mode="budget", top_k=5)
        recall_latencies.append((time.perf_counter() - recall_started) * 1000)
        recall_counts.append(len(result.get("atoms", [])))

    result = {
        "atoms": scale,
        "store_ops_per_sec": round(scale / store_elapsed, 2),
        "write_latency_ms": _summary(write_latencies),
        "write_to_get_atom_ms": _summary(visibility_latencies),
        "visibility": {
            "checks": len(visibility_latencies),
            "visible": visible_count,
            "rate": round(visible_count / len(visibility_latencies), 4)
            if visibility_latencies
            else 0.0,
        },
        "recall_latency_ms": _summary(recall_latencies),
        "recall_cold_ms": round(recall_latencies[0], 3) if recall_latencies else 0.0,
        "recall_warm_latency_ms": _summary(recall_latencies[1:]),
        "recall_queries": len(recall_queries),
        "avg_recall_results": round(sum(recall_counts) / len(recall_counts), 2)
        if recall_counts
        else 0.0,
        "candidate_backend": "fts5" if memory.storage._fts_enabled else "like",
        "candidate_limit": 100,
        "indexer_queue_size": memory.indexer.stats()["queue_size"],
        "last_atom_readable": memory.storage.get_atom(last_atom_id) is not None,
    }

    memory.storage.conn.close()
    del memory
    gc.collect()
    return result


def run(scales: tuple[int, ...], recall_queries: tuple[str, ...], visibility_checks: int) -> dict[str, object]:
    return {
        "dataset_version": DATASET_VERSION,
        "storage": ":memory:",
        "auto_build_edges": False,
        "auto_episode": False,
        "recall_mode": "budget",
        "recall_top_k": 5,
        "visibility_checks_requested": visibility_checks,
        "scales": {
            str(scale): _run_scale(scale, recall_queries, visibility_checks)
            for scale in scales
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }


def _print_report(report: dict[str, object]) -> None:
    print("VibeMemory SDK scale and write-after-read benchmark")
    print(
        f"  storage={report['storage']}, edge_building={report['auto_build_edges']}, "
        f"episode={report['auto_episode']}, recall={report['recall_mode']}/top-{report['recall_top_k']}"
    )
    print()
    print(
        f"{'Atoms':>8} {'Store ops/s':>12} "
        f"{'Write p50/p95/p99 ms':>25} {'Read p50/p95/p99 ms':>24} "
        f"{'Recall p50/p95/p99 ms':>25} {'Visible':>10}"
    )
    print("-" * 116)
    for scale, result in report["scales"].items():
        write = result["write_latency_ms"]
        read = result["write_to_get_atom_ms"]
        recall = result["recall_latency_ms"]
        visibility = result["visibility"]
        print(
            f"{scale:>8} {result['store_ops_per_sec']:>12.2f} "
            f"{write['p50']:.3f}/{write['p95']:.3f}/{write['p99']:.3f}"
            f"{' ':>4}{read['p50']:.3f}/{read['p95']:.3f}/{read['p99']:.3f}"
            f"{' ':>4}{recall['p50']:.3f}/{recall['p95']:.3f}/{recall['p99']:.3f}"
            f"{' ':>6}{visibility['visible']}/{visibility['checks']}"
        )
    print("\nRecall cache breakdown (ms)")
    print(f"{'Atoms':>8} {'Cold':>12} {'Warm p50/p95/p99':>24}")
    print("-" * 48)
    for scale, result in report["scales"].items():
        warm = result["recall_warm_latency_ms"]
        print(
            f"{scale:>8} {result['recall_cold_ms']:>12.3f} "
            f"{warm['p50']:.3f}/{warm['p95']:.3f}/{warm['p99']:.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, nargs="+", default=list(DEFAULT_SCALES))
    parser.add_argument("--recall-samples", type=int, default=DEFAULT_RECALL_SAMPLES)
    parser.add_argument("--visibility-checks", type=int, default=100)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if any(scale < 1 for scale in args.scale):
        parser.error("--scale values must be positive")
    if args.recall_samples < 1 or args.visibility_checks < 1:
        parser.error("--recall-samples and --visibility-checks must be positive")

    queries = tuple(BASE_RECALL_QUERIES[i % len(BASE_RECALL_QUERIES)] for i in range(args.recall_samples))
    report = run(tuple(args.scale), queries, args.visibility_checks)
    _print_report(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nResults saved to: {args.json}")


if __name__ == "__main__":
    main()
