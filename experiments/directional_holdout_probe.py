"""Compare directional reranking on a labeled corpus without reporting private text."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from experiments.safe_relation_rerank_probe import (
    _baseline_with_stages,
    _directional_ids,
)
from vibe_memory.embedding import TfidfProvider
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom
from vibe_memory.retrieval.ppr import recall
from vibe_memory.storage.sqlite_store import VibeStorage


def _store(data: dict) -> VibeStorage:
    store = VibeStorage(":memory:")
    for atom in data["atoms"]:
        store.insert_atom(
            MemoryAtom(
                id=atom["id"],
                agent_id="safe-relation-probe",
                session_id=atom["session_id"],
                content=atom["content"],
                summary=atom["content"],
                created_at=datetime(2026, 9, 19),
            )
        )
    for index, (source, target) in enumerate(data["edges"]):
        store.insert_edge(
            Edge(
                id=f"edge-{index}",
                from_atom_id=source,
                to_atom_id=target,
                label=EdgeLabel.CAUSAL,
            )
        )
    return store


def _rank(data: dict, query: str, strategy: str) -> list[str]:
    store = _store(data)
    try:
        if strategy == "directional_chain":
            _, stages = _baseline_with_stages(store, query)
            return _directional_ids(store, stages)
        result = recall(
            query,
            "safe-relation-probe",
            store,
            mode="precision",
            top_k=5,
            embedding_provider=TfidfProvider(),
            causal_bridge=strategy == "causal_bridge",
        )
        return [atom.id for atom in result["atoms"]]
    finally:
        store.conn.close()


def _directional_rank_and_diagnostic(
    data: dict, query: str, anonymous: dict[str, str]
) -> tuple[list[str], dict]:
    store = _store(data)
    try:
        baseline_ids, stages = _baseline_with_stages(store, query)
        directional_ids = _directional_ids(store, stages)
        semantic = stages.get("semantic", [])
        bm25 = stages.get("bm25", [])
        anchors = {atom_id for atom_id, _ in semantic} & {
            atom_id for atom_id, score in bm25 if score > 0
        }
        primary = semantic[0][0] if semantic else None
        primary_candidates: set[str] = set()
        supported: set[str] = set()
        outgoing_to_anchors: dict[str, set[str]] = {}
        for edge in store.get_retrieval_edges(
            "safe-relation-probe", atom_ids=list(anchors)
        ):
            if edge.label != EdgeLabel.CAUSAL or edge.weight * edge.confidence < 0.05:
                continue
            if edge.from_atom_id == primary and edge.to_atom_id not in anchors:
                primary_candidates.add(edge.to_atom_id)
            if edge.from_atom_id not in anchors and edge.to_atom_id in anchors:
                outgoing_to_anchors.setdefault(edge.from_atom_id, set()).add(
                    edge.to_atom_id
                )
        for candidate in primary_candidates:
            if outgoing_to_anchors.get(candidate, set()) - {primary}:
                supported.add(candidate)

        reranked_ids = [atom_id for atom_id, _ in stages.get("full_reranked", [])]
        eligible_supported = supported & set(reranked_ids)
        if len(anchors) < 2 or primary is None:
            outcome = "insufficient_common_anchors"
        elif not primary_candidates:
            outcome = "no_primary_outgoing_candidate"
        elif not supported:
            outcome = "no_candidate_to_second_anchor"
        elif not eligible_supported:
            outcome = "supported_candidate_outside_fused"
        elif directional_ids != baseline_ids:
            outcome = "triggered"
        else:
            outcome = "supported_candidate_already_ranked"
        diagnostic = {
            "primary_anchor_id": anonymous.get(primary) if primary else None,
            "common_anchor_count": len(anchors),
            "primary_outgoing_candidate_count": len(primary_candidates),
            "supported_candidate_count": len(eligible_supported),
            "outcome": outcome,
        }
        return directional_ids, diagnostic
    finally:
        store.conn.close()


def evaluate(data: dict) -> dict:
    atom_ids = [atom["id"] for atom in data["atoms"]]
    anonymous = {atom_id: f"atom-{index}" for index, atom_id in enumerate(atom_ids)}
    strategies = ("baseline", "causal_bridge", "directional_chain")
    rows = []

    for index, query in enumerate(data["queries"]):
        positives = set(query["relevant_ids"])
        negatives = set(query["negative_ids"])
        if not positives or positives & negatives or not positives | negatives <= set(atom_ids):
            raise ValueError("Invalid labels")

        directional_ids, directional_diagnostic = _directional_rank_and_diagnostic(
            data, query["text"], anonymous
        )
        rankings = {
            "baseline": _rank(data, query["text"], "baseline"),
            "causal_bridge": _rank(data, query["text"], "causal_bridge"),
            "directional_chain": directional_ids,
        }
        row = {
            "query_id": f"query-{index}",
            "directional_diagnostic": directional_diagnostic,
        }
        for strategy in strategies:
            ids = rankings[strategy]
            row[strategy] = {
                "recall": len(set(ids) & positives) / len(positives),
                "precision_at_5": len(set(ids) & positives) / 5,
                "negative_hits": sum(atom_id in negatives for atom_id in ids),
                "negative_top1": bool(ids and ids[0] in negatives),
                "returned_ids": [anonymous[atom_id] for atom_id in ids],
                "ranking_changed": ids != rankings["baseline"],
            }
        rows.append(row)

    aggregates = {}
    for strategy in strategies:
        values = [row[strategy] for row in rows]
        aggregates[strategy] = {
            "macro_recall": statistics.mean(value["recall"] for value in values),
            "macro_precision_at_5": statistics.mean(
                value["precision_at_5"] for value in values
            ),
            "queries_with_negative_hits": sum(
                bool(value["negative_hits"]) for value in values
            ),
            "queries_with_negative_top1": sum(
                value["negative_top1"] for value in values
            ),
            "queries_with_ranking_changes": sum(
                value["ranking_changed"] for value in values
            ),
        }

    return {
        "dataset_id": data.get("dataset_id", "private-holdout"),
        "evaluation_is_independent": False,
        "evidence_boundary": (
            "Assistant-authored questions, labels, and manual edges; not independent "
            "human evaluation or raw-session replay. Private text and original atom IDs omitted."
        ),
        "conditions": {
            "mode": "precision",
            "top_k": 5,
            "embedding": "tfidf",
            "atoms": len(data["atoms"]),
            "queries": len(data["queries"]),
            "timing_included": False,
            "production_defaults_changed": False,
        },
        "directional_diagnostics": {
            "outcome_counts": dict(
                sorted(
                    Counter(
                        row["directional_diagnostic"]["outcome"] for row in rows
                    ).items()
                )
            )
        },
        "aggregates": aggregates,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    raw = args.corpus.read_bytes()
    report = evaluate(json.loads(raw.decode("utf-8-sig")))
    report["corpus_sha256"] = hashlib.sha256(raw).hexdigest()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
