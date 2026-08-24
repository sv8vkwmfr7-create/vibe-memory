"""
VibeMemory Benchmark Suite

Measures:
  1. Throughput (store/recall ops/sec)
  2. Retrieval Quality (Precision@K, Recall@K, MRR)
  3. Graph Scale (100 -> 500 -> 1000 -> 5000 -> 10000 atoms)
  4. PPR Convergence (iterations vs graph size)
  5. Edge Building Speed (same-session + cross-session)
  6. Memory Overhead (atom/edge struct size)

Usage:
    python experiments/benchmark.py
    python experiments/benchmark.py --scale 1000  # override max scale
    python experiments/benchmark.py --json results.json  # save to file
"""

import sys
import os
import time
import json
import argparse
import gc as pygc
from collections import defaultdict
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vibe_memory.sdk import VibeMemory
from vibe_memory.models.memory_atom import GraphPartition, EdgeLabel, MemoryAtom, Edge


# ─── helpers ────────────────────────────────────────────────────────────────

def timeit(func, *args, **kwargs):
    """Measure execution time of a function call."""
    pygc.collect()
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


def color(text: str, code: str) -> str:
    """Simple ANSI color wrapper."""
    colors = {"green": "32", "yellow": "33", "red": "31", "cyan": "36", "bold": "1"}
    c = colors.get(code, "0")
    return f"\033[{c}m{text}\033[0m"


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_result(label: str, value, unit: str = "", ok: bool = True):
    marker = color("[OK]", "green") if ok else color("[WARN]", "yellow")
    print(f"  {marker} {label}: {value}{unit}")


# ─── 1. Throughput ──────────────────────────────────────────────────────────

def benchmark_throughput(mem: VibeMemory, n: int = 500):
    """Measure store and recall operations per second."""
    print_header("1. Throughput (ops/sec)")

    # -- Store throughput --
    t0 = time.perf_counter()
    for i in range(n):
        mem.store(
            f"Throughput test atom {i}: "
            f"Lorem ipsum dolor sit amet consectetur adipiscing elit "
            f"sed do eiusmod tempor incididunt ut labore. "
            f"Key: benchmark_{i % 100}",
            session_id=f"thru-{i // 10}",
            auto_build_edges=False,
            auto_episode=False,
        )
    store_time = time.perf_counter() - t0
    store_ops = n / store_time
    print_result("Store", f"{store_ops:.1f} ops/sec")

    # -- Recall throughput --
    t0 = time.perf_counter()
    for i in range(100):
        mem.recall(f"benchmark_{i % 100}", mode="budget", top_k=5)
    recall_time = time.perf_counter() - t0
    recall_ops = 100 / recall_time
    print_result("Recall", f"{recall_ops:.1f} ops/sec")

    return {"store_ops_per_sec": round(store_ops, 1), "recall_ops_per_sec": round(recall_ops, 1)}


# ─── 2. Retrieval Quality ───────────────────────────────────────────────────

def benchmark_retrieval_quality(mem: VibeMemory):
    """Measure Precision@K, Recall@K, MRR on labeled data."""
    print_header("2. Retrieval Quality")

    # Build labeled dataset: 3 sessions, known groupings
    atoms_map = {}

    # Session A: API debugging (3 atoms)
    for i, content in enumerate([
        "API timeout error investigation: increased timeout from 30s to 60s",
        "Database connection pool exhausted after API timeout fix",
        "Redis cache invalidation causing stale data in API responses",
    ]):
        a = mem.store(content, session_id="quality-api", tags=["api", "debug", "error"],
                      auto_build_edges=False, auto_episode=False)
        atoms_map[f"api-{i}"] = a.id

    # Session B: frontend styling (3 atoms)
    for i, content in enumerate([
        "CSS flexbox layout broken in Safari after grid migration",
        "Dark mode color scheme contrast ratios failing WCAG AA",
        "Responsive breakpoint causing horizontal scroll on mobile",
    ]):
        a = mem.store(content, session_id="quality-frontend", tags=["frontend", "css", "ui"],
                      auto_build_edges=False, auto_episode=False)
        atoms_map[f"frontend-{i}"] = a.id

    # Session C: database migration (3 atoms)
    for i, content in enumerate([
        "MySQL to PostgreSQL migration: 8 schemas converted",
        "Foreign key constraint review after PostgreSQL migration",
        "Stored procedure rewrite: IFNULL to COALESCE conversion",
    ]):
        a = mem.store(content, session_id="quality-db", tags=["database", "migration", "postgresql"],
                      auto_build_edges=False, auto_episode=False)
        atoms_map[f"db-{i}"] = a.id

    # Build connections within each session
    for prefix in ["api", "frontend", "db"]:
        a0 = atoms_map[f"{prefix}-0"]
        a1 = atoms_map[f"{prefix}-1"]
        a2 = atoms_map[f"{prefix}-2"]
        mem.link(a0, a1, label=EdgeLabel.CAUSAL, confidence=0.9)
        mem.link(a1, a2, label=EdgeLabel.CAUSAL, confidence=0.9)

    # Labeled queries: query -> expected relevant atom labels
    labeled_queries = [
        {
            "query": "API timeout investigation",
            "relevant": {"api-0", "api-1"},
        },
        {
            "query": "CSS Safari flexbox layout",
            "relevant": {"frontend-0"},
        },
        {
            "query": "PostgreSQL migration conversion",
            "relevant": {"db-0", "db-1", "db-2"},
        },
        {
            "query": "database connection pool",
            "relevant": {"api-1"},
        },
        {
            "query": "responsive mobile breakpoint",
            "relevant": {"frontend-2"},
        },
    ]

    total_precision = 0.0
    total_recall = 0.0
    total_mrr = 0.0
    n_queries = len(labeled_queries)

    for qi, lq in enumerate(labeled_queries):
        relevant_ids = {atoms_map[k] for k in lq["relevant"]}
        result = mem.recall(lq["query"], mode="precision", top_k=10)
        returned_ids = [a.id for a in result["atoms"]]

        # Precision@K: |returned AND relevant| / |returned|
        if returned_ids:
            hits = sum(1 for rid in returned_ids if rid in relevant_ids)
            precision = hits / len(returned_ids)
        else:
            precision = 0.0

        # Recall@K: |returned AND relevant| / |relevant|
        if relevant_ids:
            hits = sum(1 for rid in returned_ids if rid in relevant_ids)
            recall = hits / len(relevant_ids)
        else:
            recall = 1.0

        # MRR: 1 / rank_of_first_relevant (1-indexed)
        mrr = 0.0
        for rank, rid in enumerate(returned_ids, start=1):
            if rid in relevant_ids:
                mrr = 1.0 / rank
                break

        total_precision += precision
        total_recall += recall
        total_mrr += mrr

    avg_precision = total_precision / n_queries
    avg_recall = total_recall / n_queries
    avg_mrr = total_mrr / n_queries

    print_result("Precision@K", f"{avg_precision:.3f}")
    print_result("Recall@K", f"{avg_recall:.3f}")
    print_result("MRR", f"{avg_mrr:.3f}")

    return {
        "precision_at_k": round(avg_precision, 3),
        "recall_at_k": round(avg_recall, 3),
        "mrr": round(avg_mrr, 3),
    }


# ─── 3. Graph Scale ─────────────────────────────────────────────────────────

def benchmark_graph_scale(scale_points: list[int] = None):
    """Measure store/recall performance as graph grows."""
    if scale_points is None:
        scale_points = [100, 500, 1000, 5000, 10000]

    print_header("3. Graph Scale")

    results = {}

    for n in scale_points:
        mem = VibeMemory(agent_id=f"scale-{n}", db_path=":memory:", embedding_backend="tfidf")

        # Store N atoms in batches to avoid excessive edge building
        t0 = time.perf_counter()
        batch_size = 100
        for i in range(0, n, batch_size):
            batch_end = min(i + batch_size, n)
            for j in range(i, batch_end):
                # Generate varied content to simulate realistic data
                topic = j % 10
                topics = [
                    "API timeout error handling in production",
                    "Database migration from MySQL to PostgreSQL",
                    "Frontend CSS grid layout refactoring",
                    "Redis cache invalidation strategy",
                    "Authentication token refresh flow",
                    "Docker container orchestration setup",
                    "CI/CD pipeline optimization",
                    "Logging aggregation with ELK stack",
                    "Rate limiting implementation",
                    "WebSocket connection management",
                ]
                mem.store(
                    f"{topics[topic]} - iteration {j}: "
                    f"Additional context for benchmark atom number {j} "
                    f"with topic variation {topic} and details about config.",
                    session_id=f"scale-session-{j // 20}",
                    auto_build_edges=False,
                    auto_episode=False,
                )
        store_time = time.perf_counter() - t0

        # Recall: 10 queries
        t0 = time.perf_counter()
        for i in range(10):
            mem.recall(topics[i % 10], mode="budget", top_k=20)
        recall_time = time.perf_counter() - t0

        stats = mem.stats()
        store_ops = n / store_time if store_time > 0 else 0
        avg_recall = recall_time / 10 if recall_time > 0 else 0

        print(f"  n={n:>5}: store={store_ops:>8.1f} ops/s  "
              f"recall={avg_recall*1000:>6.1f} ms/op  "
              f"atoms={stats['total_atoms']}")

        results[n] = {
            "store_ops_per_sec": round(store_ops, 1),
            "recall_ms_per_op": round(avg_recall * 1000, 1),
            "total_atoms": stats["total_atoms"],
        }

    return results


# ─── 4. PPR Convergence ─────────────────────────────────────────────────────

def benchmark_ppr_convergence():
    """Measure PPR iterations needed for convergence at different graph sizes."""
    print_header("4. PPR Convergence")

    from vibe_memory.retrieval.ppr import PPRConfig, personalized_pagerank

    scale_points = [10, 50, 100, 500, 1000]
    results = {}

    for n in scale_points:
        mem = VibeMemory(agent_id=f"ppr-{n}", db_path=":memory:", embedding_backend="tfidf")

        atoms = []
        for i in range(n):
            a = mem.store(
                f"PPR test atom {i}: graph structure analysis with "
                f"varying connectivity patterns and edge density.",
                session_id=f"ppr-{i // 10}",
                auto_build_edges=False,
                auto_episode=False,
            )
            atoms.append(a)

        # Build a chain: 0 -> 1 -> 2 -> ... -> n-1
        for i in range(n - 1):
            mem.link(atoms[i].id, atoms[i + 1].id, label=EdgeLabel.CAUSAL, confidence=0.9)

        # Measure PPR convergence
        config = PPRConfig.precision()
        t0 = time.perf_counter()
        scores = personalized_pagerank(
            seed_atoms=[atoms[0]],
            storage=mem.storage,
            config=config,
        )
        ppr_time = time.perf_counter() - t0

        results[n] = {
            "nodes_walked": len(scores),
            "time_ms": round(ppr_time * 1000, 2),
        }
        print(f"  n={n:>5}: {len(scores)} nodes walked, {ppr_time*1000:>6.2f} ms")

    return results


# ─── 5. Edge Building Speed ─────────────────────────────────────────────────

def benchmark_edge_building():
    """Measure same-session and cross-session edge building speed."""
    print_header("5. Edge Building Speed")

    from vibe_memory.edges.edge_builder import (
        build_same_session_edges,
        build_cross_session_candidates,
    )

    # Same-session: 50 atoms in one session
    mem = VibeMemory(agent_id="edge-speed", db_path=":memory:", embedding_backend="tfidf")

    atoms = []
    for i in range(50):
        a = mem.store(
            f"Edge building test atom {i}: API error handling "
            f"with timeout configuration and retry logic.",
            session_id="edge-same",
            auto_build_edges=False,
            auto_episode=False,
        )
        atoms.append(a)

    t0 = time.perf_counter()
    edges = build_same_session_edges(atoms)
    same_time = time.perf_counter() - t0

    print_result("Same-session (50 atoms)", f"{len(edges)} edges, {same_time*1000:.2f} ms")

    # Cross-session: 10 atoms in session A, 10 in session B
    new_atoms = []
    for i in range(10):
        a = mem.store(
            f"Cross-session test atom {i}: API timeout fix with retry.",
            session_id="edge-cross",
            auto_build_edges=False,
            auto_episode=False,
        )
        new_atoms.append(a)

    existing = atoms[:10]  # first 10 from same-session

    t0 = time.perf_counter()
    candidates = build_cross_session_candidates(
        new_atoms[0], existing,
        high_similarity=0.8,
        medium_similarity=0.5,
    )
    cross_time = time.perf_counter() - t0

    total_candidates = len(candidates["duplicate"]) + len(candidates["similar"])
    print_result("Cross-session (10x10)", f"{total_candidates} candidates, {cross_time*1000:.2f} ms")

    return {
        "same_session_50_atoms": {
            "edges": len(edges),
            "time_ms": round(same_time * 1000, 2),
        },
        "cross_session_10x10": {
            "candidates": total_candidates,
            "time_ms": round(cross_time * 1000, 2),
        },
    }


# ─── 6. Memory Overhead ─────────────────────────────────────────────────────

def benchmark_memory_overhead():
    """Measure struct sizes and growth patterns."""
    print_header("6. Memory Overhead")

    # Estimate struct sizes
    atom = MemoryAtom(
        id="bench-id",
        agent_id="bench-agent",
        session_id="bench-session",
        content="test content",
        summary="test summary",
        tags=["benchmark", "test"],
        created_at=datetime.now(),
    )
    edge = Edge(
        id="bench-edge",
        from_atom_id="bench-id-1",
        to_atom_id="bench-id-2",
        label=EdgeLabel.CAUSAL,
        created_at=datetime.now(),
    )

    # Rough size estimate via sys.getsizeof + content strings
    import sys as _sys
    atom_struct_size = _sys.getsizeof(atom) + _sys.getsizeof(atom.content) + _sys.getsizeof(atom.summary)
    edge_struct_size = _sys.getsizeof(edge)

    print_result("Atom struct (empty)", f"{_sys.getsizeof(atom)} bytes")
    print_result("Atom struct (with content)", f"{atom_struct_size} bytes")
    print_result("Edge struct", f"{edge_struct_size} bytes")

    # Estimate per-atom overhead in SQLite
    mem = VibeMemory(agent_id="mem-size", db_path=":memory:", embedding_backend="tfidf")
    for i in range(100):
        mem.store(
            f"Memory overhead test atom {i} with some content to measure.",
            session_id="mem-size",
            auto_build_edges=False,
            auto_episode=False,
        )

    stats = mem.stats()
    print_result("100 atoms (SQLite)", f"{stats['total_atoms']} atoms, {stats['total_edges']} edges")

    return {
        "atom_struct_bytes": atom_struct_size,
        "edge_struct_bytes": edge_struct_size,
        "sqlite_100_atoms": stats["total_atoms"],
    }


# ─── main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VibeMemory Benchmark Suite")
    parser.add_argument("--scale", type=int, nargs="*", default=None,
                        help="Graph scale points (default: 100 500 1000 5000 10000)")
    parser.add_argument("--json", type=str, default=None,
                        help="Output JSON file path")
    parser.add_argument("--skip-scale", action="store_true",
                        help="Skip graph scale benchmark (slow)")
    args = parser.parse_args()

    print(color("VibeMemory Benchmark Suite", "bold"))
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"  Python:  {sys.version}")

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "python_version": sys.version,
    }

    # 1. Throughput
    mem = VibeMemory(agent_id="bench", db_path=":memory:", embedding_backend="tfidf")
    all_results["throughput"] = benchmark_throughput(mem)

    # 2. Retrieval Quality
    mem2 = VibeMemory(agent_id="bench-quality", db_path=":memory:", embedding_backend="tfidf")
    all_results["retrieval_quality"] = benchmark_retrieval_quality(mem2)

    # 3. Graph Scale
    if not args.skip_scale:
        scale_points = args.scale or [100, 500, 1000, 5000, 10000]
        all_results["graph_scale"] = benchmark_graph_scale(scale_points)
    else:
        print_header("3. Graph Scale")
        print("  [SKIPPED] use --skip-scale to skip")

    # 4. PPR Convergence
    all_results["ppr_convergence"] = benchmark_ppr_convergence()

    # 5. Edge Building
    all_results["edge_building"] = benchmark_edge_building()

    # 6. Memory Overhead
    all_results["memory_overhead"] = benchmark_memory_overhead()

    # Summary
    print_header("Summary")
    print(f"  Store:   {all_results['throughput']['store_ops_per_sec']} ops/sec")
    print(f"  Recall:  {all_results['throughput']['recall_ops_per_sec']} ops/sec")
    print(f"  Prec@K:  {all_results['retrieval_quality']['precision_at_k']}")
    print(f"  Rec@K:   {all_results['retrieval_quality']['recall_at_k']}")
    print(f"  MRR:     {all_results['retrieval_quality']['mrr']}")

    # Save JSON
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"\n  Results saved to: {args.json}")

    print(f"\n{color('Benchmark complete.', 'green')}")


if __name__ == "__main__":
    main()