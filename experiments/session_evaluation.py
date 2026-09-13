"""Evaluate an external, manually labeled corpus without uploading its text."""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Lifecycle, GraphPartition,
    EdgeLabel, EdgeStatus, EdgeSource,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall


def evaluate(data: dict, top_k: int = 5) -> dict:
    if top_k < 1 or not data.get("queries"):
        raise ValueError("Positive top_k and nonempty queries are required")
    def decode(row, enums):
        row = dict(row)
        row["created_at"] = datetime.fromisoformat(row["created_at"])
        if row.get("last_accessed"):
            row["last_accessed"] = datetime.fromisoformat(row["last_accessed"])
        for key, enum in enums.items():
            if key in row:
                row[key] = enum(row[key])
        return row

    atoms = [MemoryAtom(**decode(row, {
        "type": GraphPartition, "lifecycle": Lifecycle,
    })) for row in data["atoms"]]
    edges = [Edge(**decode(row, {
        "label": EdgeLabel, "status": EdgeStatus, "source": EdgeSource,
    })) for row in data.get("edges", [])]
    if len({a.id for a in atoms}) != len(atoms):
        raise ValueError("Duplicate atom IDs")
    rows = []
    for query in data["queries"]:
        cutoff = datetime.fromisoformat(query["cutoff"])
        eligible = [a for a in atoms if a.created_at <= cutoff
                    and a.agent_id == query["agent_id"]
                    and a.tenant_id == query["tenant_id"]
                    and a.lifecycle.value in ("active", "warm")]
        ids = {a.id for a in eligible}
        relevant = set(query["relevant_ids"])
        if not relevant or not relevant <= ids:
            raise ValueError("Labels must reference eligible memories before the cutoff")
        store = VibeStorage(":memory:", tenant_id=query["tenant_id"])
        try:
            for atom in eligible:
                store.insert_atom(atom)
            for edge in edges:
                if edge.created_at <= cutoff and edge.from_atom_id in ids and edge.to_atom_id in ids:
                    store.insert_edge(edge)
            methods = {
                "no_memory": None,
                "keyword": ["bm25"],
                "tfidf": ["semantic"],
                "budget": ["semantic", "bm25", "graph", "temporal"],
            }
            for method, strategies in methods.items():
                start = time.perf_counter()
                result = [] if strategies is None else recall(
                    query["text"], query["agent_id"], store,
                    mode="budget" if method == "budget" else "precision",
                    top_k=top_k, strategies=strategies, budget_graph_hops=2,
                )["atoms"]
                returned = [a.id for a in result]
                hits = len(set(returned) & relevant)
                rows.append({
                    "query_id": query["id"], "method": method,
                    "returned_ids": returned,
                    "precision": hits / len(returned) if returned else 0.0,
                    "recall": hits / len(relevant),
                    "latency_ms": (time.perf_counter() - start) * 1000,
                })
        finally:
            store.conn.close()
    return {"dataset_id": data["dataset_id"], "top_k": top_k,
            "evidence": "retrieval-only; corpus provenance and labels require human review",
            "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    report = evaluate(json.loads(args.corpus.read_text(encoding="utf-8-sig")), args.top_k)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
