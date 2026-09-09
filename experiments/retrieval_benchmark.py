"""Reproducible retrieval ablation for the VibeMemory core.

This benchmark deliberately keeps the dataset and the graph construction in
the script so that a run does not depend on a model download, wall-clock
timestamps, or an external service.  It compares three retrieval paths:

* ``vector``: pre-indexed TF-IDF Top-K;
* ``graph_all_edges``: PPR with every edge label and no seed post-filter;
* ``graph_precision``: PPR with the precision edge-label allow-list and the
  existing graph-connectivity seed filter;
* ``budget_pipeline``: the public multi-strategy recall pipeline with bounded
  storage candidates.

The synthetic corpus contains 20 topics x 50 atoms (1,000 atoms) and five
fixed query variants per topic (100 queries).  Each topic has a five-atom
causal answer chain.  The first three atoms contain the query phrase; one
isolated cross-reference atom is a lexical hard negative.  A high-weight
``SIMILAR`` edge points to a non-seed atom in the next topic so the edge-label
ablation has a measurable failure mode.

Usage::

    python experiments/retrieval_benchmark.py
    python experiments/retrieval_benchmark.py --json results/retrieval.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

# Allow running the file directly from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibe_memory.embedding import TfidfProvider, index_flat
from vibe_memory.models.memory_atom import (
    Edge,
    EdgeLabel,
    EdgeSource,
    EdgeStatus,
    MemoryAtom,
)
from vibe_memory.retrieval.ppr import PPRConfig, personalized_pagerank, recall
from vibe_memory.retrieval.seed_filter import SeedFilter
from vibe_memory.storage.sqlite_store import VibeStorage


DATASET_VERSION = "retrieval-ablation-v2"
AGENT_ID = "retrieval-benchmark"
TOP_K = 5
ATOMS_PER_TOPIC = 50
ANSWER_ATOMS = 5
QUERIES_PER_TOPIC = 5

# The phrases intentionally cover API, data, infra, and UI tasks.  They are
# constants rather than random samples, making a result diff meaningful.
TOPICS: tuple[tuple[str, str], ...] = (
    ("api_timeout", "API timeout"),
    ("database_pool", "database pool"),
    ("auth_token", "authentication token"),
    ("queue_backpressure", "queue backpressure"),
    ("cache_invalidation", "cache invalidation"),
    ("file_upload_retry", "file upload retry"),
    ("docker_deployment", "Docker deployment"),
    ("css_overflow", "CSS layout overflow"),
    ("rate_limiting", "rate limiting"),
    ("websocket_disconnect", "WebSocket disconnect"),
    ("oauth_refresh", "OAuth refresh"),
    ("kafka_lag", "Kafka consumer lag"),
    ("index_drift", "search index drift"),
    ("billing_retry", "billing retry"),
    ("schema_migration", "schema migration"),
    ("cron_miss", "scheduled job miss"),
    ("memory_leak", "memory leak"),
    ("tls_certificate", "TLS certificate"),
    ("image_resize", "image resize"),
    ("tenant_isolation", "tenant isolation"),
)

QUERY_SUFFIXES: tuple[str, ...] = (
    "incident",
    "previous fix",
    "root cause",
    "how did we resolve",
    "remediation",
)


def _atom_id(topic_key: str, index: int) -> str:
    return f"{topic_key}-{index:02d}"


def build_dataset() -> tuple[VibeStorage, list[MemoryAtom], dict[str, set[str]], list[dict]]:
    """Build the fixed corpus, graph, relevance labels, and query list."""

    storage = VibeStorage(":memory:")
    atoms: list[MemoryAtom] = []
    relevant: dict[str, set[str]] = {}
    base_time = datetime(2026, 1, 1)

    for topic_index, (topic_key, phrase) in enumerate(TOPICS):
        topic_ids: list[str] = []
        for atom_index in range(ATOMS_PER_TOPIC):
            atom_id = _atom_id(topic_key, atom_index)
            if atom_index < 3:
                content = (
                    f"Incident report: {phrase} observed in production; "
                    "investigate the issue and continue."
                )
            elif atom_index < 5:
                # These are relevant answers but intentionally do not repeat
                # the query phrase.  A graph walk must recover them.
                content = (
                    f"Resolution step {atom_index}: root cause, configuration "
                    "change, verification and rollback notes for the incident."
                )
            elif atom_index == ATOMS_PER_TOPIC - 1:
                previous_phrase = TOPICS[(topic_index - 1) % len(TOPICS)][1]
                content = (
                    f"Cross-reference only: {previous_phrase} appears in an "
                    "unrelated task comparison; not a solution."
                )
            else:
                content = (
                    f"Background note {atom_index}: operational housekeeping, "
                    "status update and unrelated details."
                )

            atom = MemoryAtom(
                id=atom_id,
                agent_id=AGENT_ID,
                session_id=f"session-{topic_index:02d}",
                content=content,
                summary=content[:120],
                tags=[topic_key],
                created_at=base_time + timedelta(minutes=len(atoms)),
            )
            storage.insert_atom(atom)
            atoms.append(atom)
            topic_ids.append(atom_id)

        relevant[topic_key] = set(topic_ids[:ANSWER_ATOMS])

    # Each answer chain is causal.  The high-weight cross-task edge is
    # intentionally SIMILAR and therefore should be excluded in precision
    # mode.  Its destination is atom 48, not the lexical hard-negative seed
    # at atom 49, so seed filtering can be measured independently.
    for topic_index, (topic_key, _) in enumerate(TOPICS):
        answer_ids = sorted(relevant[topic_key])
        for from_id, to_id in zip(answer_ids, answer_ids[1:]):
            storage.insert_edge(
                Edge(
                    id=f"causal-{from_id}-{to_id}",
                    from_atom_id=from_id,
                    to_atom_id=to_id,
                    label=EdgeLabel.CAUSAL,
                    confidence=0.7,
                    weight=0.5,
                    source=EdgeSource.RULE,
                    created_at=base_time,
                    status=EdgeStatus.ACTIVE,
                )
            )

        next_topic_key = TOPICS[(topic_index + 1) % len(TOPICS)][0]
        storage.insert_edge(
            Edge(
                id=f"cross-topic-{topic_index:02d}",
                from_atom_id=answer_ids[0],
                to_atom_id=_atom_id(next_topic_key, ATOMS_PER_TOPIC - 2),
                label=EdgeLabel.SIMILAR,
                confidence=0.99,
                weight=4.0,
                source=EdgeSource.RULE,
                created_at=base_time,
                status=EdgeStatus.ACTIVE,
            )
        )

    queries = [
        {
            "query": f"{phrase} {suffix}",
            "topic": topic_key,
            "relevant_ids": relevant[topic_key],
        }
        for topic_key, phrase in TOPICS
        for suffix in QUERY_SUFFIXES
    ]
    return storage, atoms, relevant, queries


def _percentile(values: list[float], percentile: float) -> float:
    """Return a deterministic linearly interpolated percentile."""

    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _metrics(ranked: Iterable[MemoryAtom], relevant_ids: set[str], top_k: int) -> dict[str, float]:
    ranked_ids = [atom.id for atom in ranked][:top_k]
    hits = sum(atom_id in relevant_ids for atom_id in ranked_ids)
    first_hit = next(
        (1.0 / rank for rank, atom_id in enumerate(ranked_ids, start=1) if atom_id in relevant_ids),
        0.0,
    )
    returned = len(ranked_ids)
    precision = hits / returned if returned else 0.0
    recall = hits / len(relevant_ids) if relevant_ids else 0.0
    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "mrr": first_hit,
        "noise_rate": 1.0 - precision if returned else 0.0,
    }


def _aggregate(
    metric_rows: list[dict[str, float]], latencies_ms: list[float],
) -> dict[str, object]:
    keys = ("precision_at_k", "recall_at_k", "mrr", "noise_rate")
    return {
        key: sum(row[key] for row in metric_rows) / len(metric_rows)
        for key in keys
    } | {
        "latency_ms": {
            "p50": _percentile(latencies_ms, 50),
            "p95": _percentile(latencies_ms, 95),
            "p99": _percentile(latencies_ms, 99),
        },
        "queries": len(metric_rows),
    }


def _run_benchmark(top_k: int = TOP_K) -> dict[str, object]:
    storage, atoms, _, queries = build_dataset()
    documents = [atom.content for atom in atoms]
    provider = TfidfProvider().fit(documents)
    document_vectors = provider.encode(documents)
    atom_by_id = {atom.id: atom for atom in atoms}
    seed_filter = SeedFilter()

    all_edge_config = PPRConfig(
        restart_probability=0.15,
        allowed_edge_labels=list(EdgeLabel),
        top_n=top_k,
        reverse_weight_penalty=0.5,
        min_edge_weight=0.05,
    )
    precision_config = PPRConfig.precision()
    precision_config.top_n = top_k

    rows: dict[str, list[dict[str, float]]] = {
        "vector": [],
        "graph_all_edges": [],
        "graph_precision": [],
        "budget_pipeline": [],
    }
    latencies: dict[str, list[float]] = {name: [] for name in rows}
    filtered_seed_counts: list[int] = []
    budget_provider = TfidfProvider()
    budget_semantic_cache: dict = {}
    budget_bm25_cache: dict = {}

    for item in queries:
        query = item["query"]
        relevant_ids = item["relevant_ids"]

        # The document matrix is the fixed index.  Timing starts at query
        # encoding, which excludes one-time index construction from all paths.
        started = time.perf_counter()
        query_vector = provider.encode_query(query)
        indices, _ = index_flat(document_vectors, query_vector, top_k=top_k)
        seeds = [atoms[index] for index in indices if index < len(atoms)]
        vector_elapsed = (time.perf_counter() - started) * 1000
        rows["vector"].append(_metrics(seeds, relevant_ids, top_k))
        latencies["vector"].append(vector_elapsed)

        started = time.perf_counter()
        all_scores = personalized_pagerank(seeds, storage, all_edge_config)
        all_ranked = [
            atom_by_id[atom_id]
            for atom_id, _ in sorted(all_scores.items(), key=lambda pair: pair[1], reverse=True)
            if atom_id in atom_by_id
        ]
        all_elapsed = (time.perf_counter() - started) * 1000 + vector_elapsed
        rows["graph_all_edges"].append(_metrics(all_ranked, relevant_ids, top_k))
        latencies["graph_all_edges"].append(all_elapsed)

        started = time.perf_counter()
        filtered_seeds = seed_filter.filter(seeds, storage)
        filtered_seed_counts.append(len(filtered_seeds))
        precision_scores = personalized_pagerank(filtered_seeds, storage, precision_config)
        precision_ranked = [
            atom_by_id[atom_id]
            for atom_id, _ in sorted(precision_scores.items(), key=lambda pair: pair[1], reverse=True)
            if atom_id in atom_by_id
        ]
        precision_elapsed = (time.perf_counter() - started) * 1000 + vector_elapsed
        rows["graph_precision"].append(_metrics(precision_ranked, relevant_ids, top_k))
        latencies["graph_precision"].append(precision_elapsed)

        started = time.perf_counter()
        budget_result = recall(
            query,
            AGENT_ID,
            storage,
            mode="budget",
            top_k=top_k,
            embedding_provider=budget_provider,
            tenant_id="default",
            semantic_cache=budget_semantic_cache,
            bm25_cache=budget_bm25_cache,
        )
        budget_elapsed = (time.perf_counter() - started) * 1000
        rows["budget_pipeline"].append(
            _metrics(budget_result["atoms"], relevant_ids, top_k)
        )
        latencies["budget_pipeline"].append(budget_elapsed)

    methods = {
        name: _aggregate(rows[name], latencies[name]) for name in rows
    }
    for name in methods:
        methods[name]["precision_at_k"] = round(methods[name]["precision_at_k"], 4)
        methods[name]["recall_at_k"] = round(methods[name]["recall_at_k"], 4)
        methods[name]["mrr"] = round(methods[name]["mrr"], 4)
        methods[name]["noise_rate"] = round(methods[name]["noise_rate"], 4)
        methods[name]["latency_ms"] = {
            key: round(value, 3)
            for key, value in methods[name]["latency_ms"].items()
        }

    edge_counts = {
        "total": len(storage.get_all_edges()),
        "causal": sum(edge.label == EdgeLabel.CAUSAL for edge in storage.get_all_edges()),
        "similar": sum(edge.label == EdgeLabel.SIMILAR for edge in storage.get_all_edges()),
    }
    return {
        "dataset_version": DATASET_VERSION,
        "dataset": {
            "atoms": len(atoms),
            "topics": len(TOPICS),
            "queries": len(queries),
            "queries_per_topic": QUERIES_PER_TOPIC,
            "relevant_atoms_per_query": ANSWER_ATOMS,
            "top_k": top_k,
            "budget_candidate_limit": max(100, top_k * 20),
            "edges": edge_counts,
            "index": "TF-IDF matrix precomputed for ablations; budget pipeline includes FTS5 candidate lookup",
        },
        "methods": methods,
        "seed_filter": {
            "avg_filtered_seeds": round(sum(filtered_seed_counts) / len(filtered_seed_counts), 3),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }


def _print_report(report: dict[str, object]) -> None:
    dataset = report["dataset"]
    print("VibeMemory retrieval ablation")
    print(
        f"  dataset={dataset['atoms']} atoms, {dataset['queries']} queries, "
        f"top_k={dataset['top_k']}, edges={dataset['edges']['total']}"
    )
    print(f"  seed filter: {report['seed_filter']['avg_filtered_seeds']:.2f} seeds/query")
    print()
    print(f"{'Method':<20} {'P@K':>8} {'R@K':>8} {'MRR':>8} {'Noise':>8} {'p50 ms':>10} {'p95 ms':>10} {'p99 ms':>10}")
    print("-" * 86)
    labels = {
        "vector": "TF-IDF vector",
        "graph_all_edges": "PPR all labels",
        "graph_precision": "PPR + labels/filter",
        "budget_pipeline": "Budget pipeline",
    }
    for name, label in labels.items():
        result = report["methods"][name]
        latency = result["latency_ms"]
        print(
            f"{label:<20} {result['precision_at_k']:>8.4f} {result['recall_at_k']:>8.4f} "
            f"{result['mrr']:>8.4f} {result['noise_rate']:>8.4f} "
            f"{latency['p50']:>10.3f} {latency['p95']:>10.3f} {latency['p99']:>10.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=TOP_K, help="Results per query (default: 5)")
    parser.add_argument("--json", type=Path, help="Write the report as UTF-8 JSON")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")

    report = _run_benchmark(args.top_k)
    _print_report(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nResults saved to: {args.json}")


if __name__ == "__main__":
    main()
