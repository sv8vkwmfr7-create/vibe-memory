"""Trace precision retrieval stages on frozen synthetic causal counterexamples.

This experiment observes the production recall path without changing SDK/MCP
defaults. The report contains fixed public IDs, not private conversation text.
"""

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


def _rank(ids: list[str], target_id: str) -> int | None:
    try:
        return ids.index(target_id) + 1
    except ValueError:
        return None


def _recall_with_stages(
    store: VibeStorage,
    query: str,
    *,
    causal_bridge: bool,
) -> tuple[list[str], dict[str, list[str]]]:
    observed: dict[str, list[str]] = {}
    original_fusion = fusion.rrf_fusion
    original_rerank = fusion.rerank_by_similarity

    def capture_fusion(ranked_lists, *args, **kwargs):
        names = ("semantic", "bm25", "graph", "temporal")
        for name, ranked in zip(names, ranked_lists):
            observed[name] = [atom_id for atom_id, _ in ranked]
        fused = original_fusion(ranked_lists, *args, **kwargs)
        observed["fused"] = [atom_id for atom_id, _ in fused]
        return fused

    def capture_rerank(query_vec, candidates, doc_vectors, candidate_indices, top_k=20):
        reranked = original_rerank(
            query_vec, candidates, doc_vectors, candidate_indices, top_k
        )
        observed["reranked"] = [atom_id for atom_id, _ in reranked]
        return reranked

    with patch.object(fusion, "rrf_fusion", capture_fusion), patch.object(
        fusion, "rerank_by_similarity", capture_rerank
    ):
        result = recall(
            query,
            "stage-probe",
            store,
            mode="precision",
            top_k=5,
            embedding_provider=TfidfProvider(),
            causal_bridge=causal_bridge,
        )
    final_ids = [atom.id for atom in result["atoms"]]
    observed["final"] = final_ids
    return final_ids, observed


def _diagnose_case(case: dict) -> dict:
    store = VibeStorage(":memory:")
    try:
        for atom in case["atoms"]:
            store.insert_atom(
                MemoryAtom(
                    id=atom["id"],
                    agent_id="stage-probe",
                    session_id=case["case_id"],
                    content=atom["content"],
                    summary=atom["content"],
                    created_at=datetime(2026, 9, 19),
                )
            )
        for index, edge in enumerate(case["edges"]):
            store.insert_edge(
                Edge(
                    id=f"edge-{index}",
                    from_atom_id=edge[0],
                    to_atom_id=edge[1],
                    label=EdgeLabel.CAUSAL,
                )
            )

        baseline_ids, stages = _recall_with_stages(
            store, case["query"], causal_bridge=False
        )
        bridge_ids, _ = _recall_with_stages(
            store, case["query"], causal_bridge=True
        )
        target_id = case["target_id"]
        candidate_ids = set().union(
            *(set(stages.get(name, [])) for name in ("semantic", "bm25", "graph"))
        )
        if target_id in baseline_ids:
            failure_stage = "retained"
        elif target_id not in candidate_ids:
            failure_stage = "candidate_generation"
        elif target_id not in stages.get("fused", []):
            failure_stage = "fusion"
        else:
            failure_stage = "final_rerank"

        target_ranks = {
            name: _rank(stages.get(name, []), target_id)
            for name in ("semantic", "bm25", "graph", "fused", "final")
        }
        negative_ids = set(case.get("negative_ids", []))
        return {
            "case_id": case["case_id"],
            "role": case["role"],
            "target_id": target_id,
            "target_ranks": target_ranks,
            "baseline_failure_stage": failure_stage,
            "baseline_ids": baseline_ids,
            "bridge_ids": bridge_ids,
            "baseline_negative_top1": bool(
                baseline_ids and baseline_ids[0] in negative_ids
            ),
            "bridge_negative_top1": bool(bridge_ids and bridge_ids[0] in negative_ids),
        }
    finally:
        store.conn.close()


def run(path: Path) -> dict:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    rows = [_diagnose_case(case) for case in data["cases"]]
    half_hits = [row for row in rows if row["role"] == "half_hit"]
    baseline_hits = sum(row["target_id"] in row["baseline_ids"] for row in half_hits)
    bridge_hits = sum(row["target_id"] in row["bridge_ids"] for row in half_hits)
    bridge_negative_top1 = sum(row["bridge_negative_top1"] for row in rows)
    return {
        "dataset_id": data["dataset_id"],
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "evaluation_is_independent": False,
        "evidence_boundary": (
            data["provenance"]
            + " This is not independent quality evidence and does not justify a default change."
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
            "baseline_target_recall_at_5": baseline_hits / len(half_hits),
            "causal_bridge_target_recall_at_5": bridge_hits / len(half_hits),
            "bridge_negative_top1_cases": bridge_negative_top1,
            "safe_to_enable_bridge_by_default": bridge_negative_top1 == 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("precision_stage_cases.json"),
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run(args.cases)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
