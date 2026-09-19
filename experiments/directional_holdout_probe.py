"""Compare directional reranking on a labeled corpus without reporting private text."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
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

        rankings = {
            strategy: _rank(data, query["text"], strategy) for strategy in strategies
        }
        row = {"query_id": f"query-{index}"}
        for strategy in strategies:
            ids = rankings[strategy]
            row[strategy] = {
                "recall": len(set(ids) & positives) / len(positives),
                "precision_at_5": len(set(ids) & positives) / 5,
                "negative_hits": sum(atom_id in negatives for atom_id in ids),
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
