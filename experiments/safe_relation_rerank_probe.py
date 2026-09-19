"""Compare the current bridge with an experiment-only directional chain rerank."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from vibe_memory.embedding import TfidfProvider
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom
from vibe_memory.retrieval import fusion
from vibe_memory.retrieval.ppr import recall
from vibe_memory.storage.sqlite_store import VibeStorage


def _baseline_with_stages(store: VibeStorage, query: str) -> tuple[list[str], dict]:
    observed: dict = {}
    original_fusion = fusion.rrf_fusion
    original_rerank = fusion.rerank_by_similarity

    def capture_fusion(ranked_lists, *args, **kwargs):
        names = ("semantic", "bm25", "graph", "temporal")
        for name, ranked in zip(names, ranked_lists):
            observed[name] = list(ranked)
        return original_fusion(ranked_lists, *args, **kwargs)

    def capture_rerank(query_vec, candidates, doc_vectors, candidate_indices, top_k=20):
        observed["full_reranked"] = original_rerank(
            query_vec,
            candidates,
            doc_vectors,
            candidate_indices,
            top_k=len(candidates),
        )
        return observed["full_reranked"][:top_k]

    with patch.object(fusion, "rrf_fusion", capture_fusion), patch.object(
        fusion, "rerank_by_similarity", capture_rerank
    ):
        result = recall(
            query,
            "safe-relation-probe",
            store,
            mode="precision",
            top_k=5,
            embedding_provider=TfidfProvider(),
            causal_bridge=False,
        )
    return [atom.id for atom in result["atoms"]], observed


def _directional_ids(store: VibeStorage, stages: dict) -> list[str]:
    semantic = stages.get("semantic", [])
    bm25 = stages.get("bm25", [])
    anchors = {atom_id for atom_id, _ in semantic} & {
        atom_id for atom_id, score in bm25 if score > 0
    }
    if not semantic or len(anchors) < 2:
        return [atom_id for atom_id, _ in stages.get("full_reranked", [])[:5]]

    primary = semantic[0][0]
    incoming: dict[str, set[str]] = {}
    outgoing: dict[str, set[str]] = {}
    for edge in store.get_retrieval_edges(
        "safe-relation-probe", atom_ids=list(anchors)
    ):
        if edge.label != EdgeLabel.CAUSAL or edge.weight * edge.confidence < 0.05:
            continue
        if edge.from_atom_id in anchors and edge.to_atom_id not in anchors:
            incoming.setdefault(edge.to_atom_id, set()).add(edge.from_atom_id)
        if edge.from_atom_id not in anchors and edge.to_atom_id in anchors:
            outgoing.setdefault(edge.from_atom_id, set()).add(edge.to_atom_id)

    supported = {
        node
        for node, sources in incoming.items()
        if primary in sources and outgoing.get(node, set()) - {primary}
    }
    reranked = list(stages.get("full_reranked", []))
    reranked.sort(key=lambda item: item[0] not in supported)
    return [atom_id for atom_id, _ in reranked[:5]]


def _evaluate(case: dict) -> dict:
    store = VibeStorage(":memory:")
    try:
        for atom in case["atoms"]:
            store.insert_atom(
                MemoryAtom(
                    id=atom["id"],
                    agent_id="safe-relation-probe",
                    session_id=case["case_id"],
                    content=atom["content"],
                    summary=atom["content"],
                    created_at=datetime(2026, 9, 19),
                )
            )
        for index, (source, target) in enumerate(case["edges"]):
            store.insert_edge(
                Edge(
                    id=f"edge-{index}",
                    from_atom_id=source,
                    to_atom_id=target,
                    label=EdgeLabel.CAUSAL,
                )
            )

        baseline_ids, stages = _baseline_with_stages(store, case["query"])
        bridge = recall(
            case["query"],
            "safe-relation-probe",
            store,
            mode="precision",
            top_k=5,
            embedding_provider=TfidfProvider(),
            causal_bridge=True,
        )
        bridge_ids = [atom.id for atom in bridge["atoms"]]
        directional_ids = _directional_ids(store, stages)
        negatives = set(case.get("negative_ids", []))
        return {
            "case_id": case["case_id"],
            "role": case["role"],
            "target_id": case["target_id"],
            "baseline_ids": baseline_ids,
            "causal_bridge_ids": bridge_ids,
            "directional_ids": directional_ids,
            "causal_bridge_negative_top1": bool(
                bridge_ids and bridge_ids[0] in negatives
            ),
            "directional_negative_top1": bool(
                directional_ids and directional_ids[0] in negatives
            ),
        }
    finally:
        store.conn.close()


def run(path: Path) -> dict:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    rows = [_evaluate(case) for case in data["cases"]]
    half_hits = [row for row in rows if row["role"] == "half_hit"]
    guards = [row for row in rows if row["role"] == "guard"]

    def recall_at_5(key: str) -> float:
        return sum(row["target_id"] in row[key] for row in half_hits) / len(half_hits)

    directional_negative_top1 = sum(
        row["directional_negative_top1"] for row in rows
    )
    no_edge_stable = next(
        row["baseline_ids"] == row["directional_ids"]
        for row in guards
        if row["case_id"] == "no-causal-edge"
    )
    synthetic_guards_passed = directional_negative_top1 == 0 and no_edge_stable
    return {
        "dataset_id": data["dataset_id"],
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "evaluation_is_independent": False,
        "evidence_boundary": (
            data["provenance"]
            + " Passing these synthetic guards is insufficient to change production defaults."
        ),
        "conditions": {
            "mode": "precision",
            "top_k": 5,
            "embedding": "tfidf",
            "production_defaults_changed": False,
        },
        "rows": rows,
        "summary": {
            "half_hit_cases": len(half_hits),
            "baseline_target_recall_at_5": recall_at_5("baseline_ids"),
            "causal_bridge_target_recall_at_5": recall_at_5("causal_bridge_ids"),
            "directional_chain_target_recall_at_5": recall_at_5("directional_ids"),
            "causal_bridge_negative_top1_cases": sum(
                row["causal_bridge_negative_top1"] for row in rows
            ),
            "directional_negative_top1_cases": directional_negative_top1,
            "synthetic_guards_passed": synthetic_guards_passed,
            "eligible_for_default": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("safe_relation_rerank_cases.json"),
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(run(args.cases), ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
