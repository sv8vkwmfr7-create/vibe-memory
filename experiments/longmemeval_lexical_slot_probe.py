"""Offline fixed one-slot BM25 ablation of saved MiniLM Top-5 rankings."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from experiments.longmemeval_tfidf_baseline import SHA256, prepare
from experiments.safe_relation_rerank_probe import _baseline_with_stages
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom
from vibe_memory.retrieval.fusion import rrf_fusion
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


def lexical_slot(ids: list[str], lexical: list[tuple[str, float]]) -> list[str]:
    """Keep first four; reserve fifth only for a positive, absent BM25 winner."""
    if not lexical or lexical[0][1] <= 0 or lexical[0][0] in ids:
        return list(ids)
    return ids[:4] + [lexical[0][0]]


def score(ids: list[str], evidence: set[str]) -> dict:
    found = evidence.intersection(ids)
    return {"hit": bool(found), "evidence_recall": len(found) / len(evidence)}


def rank_fused_ids(ids: list[str], lexical: list[tuple[str, float]]) -> list[str]:
    """Equal-weight RRF of saved final Top-5 and positive BM25 Top-5."""
    return [atom_id for atom_id, _ in rrf_fusion(
        [[(atom_id, 0.0) for atom_id in ids], [item for item in lexical if item[1] > 0]],
        k=60, top_k=5)]


def negative_checks(path: Path, *, rank_fusion: bool = False) -> dict:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    rows = []
    for case in data["cases"]:
        store = VibeStorage(":memory:")
        try:
            for atom in case["atoms"]:
                store.insert_atom(MemoryAtom(
                    id=atom["id"], agent_id="safe-relation-probe",
                    session_id=case["case_id"], content=atom["content"],
                    summary=atom["content"], created_at=datetime(2026, 9, 19)))
            for index, (source, target) in enumerate(case["edges"]):
                store.insert_edge(Edge(
                    id=f"edge-{index}", from_atom_id=source, to_atom_id=target,
                    label=EdgeLabel.CAUSAL))
            baseline, stages = _baseline_with_stages(store, case["query"])
            candidate = (rank_fused_ids if rank_fusion else lexical_slot)(baseline, stages["bm25"])
            negatives = set(case.get("negative_ids", []))
            rows.append({"id": case["case_id"], "baseline_ids": baseline,
                         "candidate_ids": candidate,
                         "baseline_target_hit": case["target_id"] in baseline,
                         "candidate_target_hit": case["target_id"] in candidate,
                         "new_negative_ids": sorted((set(candidate) - set(baseline)) & negatives)})
            if rank_fusion:
                rows[-1].update({"baseline_negative_top1": bool(baseline and baseline[0] in negatives),
                                 "candidate_negative_top1": bool(candidate and candidate[0] in negatives)})
        finally:
            store.conn.close()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "rows": rows,
            "limits": "Existing assistant-authored synthetic fixtures with original causal edges; unchanged TF-IDF baseline, not MiniLM. No changed lists means the slot intervention is not exercised. Not independent safety evidence."}


def run(dataset: Path, comparison: Path, stages_path: Path, guards_path: Path,
        *, rank_fusion: bool = False) -> dict:
    raw = dataset.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError("dataset SHA-256 mismatch")
    cases = json.loads(raw)
    if len(cases) != 500 or len({case["question_id"] for case in cases}) != 500:
        raise ValueError("expected 500 unique official cases")
    selected = [case for case in cases if not case["question_id"].endswith("_abs")]
    comparison_raw = comparison.read_bytes()
    paired = json.loads(comparison_raw)
    if paired["source_sha256"] != SHA256 or len(selected) != 470:
        raise ValueError("source identity/abstention exclusion mismatch")
    if [row["id"] for row in paired["rows"]] != [case["question_id"] for case in selected]:
        raise ValueError("comparison IDs/order mismatch")
    stages_raw = stages_path.read_bytes()
    stages = json.loads(stages_raw)
    if stages["comparison_sha256"] != hashlib.sha256(comparison_raw).hexdigest():
        raise ValueError("stage comparison hash mismatch")
    traced = {row["id"]: row["arms"]["model"]["ids"]["bm25"] for row in stages["rows"]}
    if len(traced) != 107 or len(stages["rows"]) != 107 or not set(traced) <= {case["question_id"] for case in selected}:
        raise ValueError("expected all 107 unique stage replay cases")
    rows = []
    for case, prior in zip(selected, paired["rows"]):
        atoms, evidence = prepare(case)
        store = VibeStorage(":memory:", tenant_id="longmemeval")
        try:
            for atom in atoms:
                store.insert_atom(atom)
            stored = store.get_atoms_by_agent(case["question_id"])
            all_ids = {atom.id for atom in stored}
            baseline = prior["model_top5_ids"]
            if len(baseline) != 5 or len(set(baseline)) != 5 or not set(baseline) <= all_ids:
                raise ValueError("invalid saved Top-5")
            if score(baseline, evidence) != {"hit": prior["model_hit"], "evidence_recall": prior["model_evidence_recall"]}:
                raise ValueError("saved baseline score mismatch")
            if score(prior["top5_ids"], evidence)["hit"] != prior["hit"]:
                raise ValueError("saved TF-IDF score mismatch")
            bm25 = BM25Strategy()
            bm25.fit([atom.content for atom in stored])
            lexical = [(stored[index].id, value) for index, value in bm25.search(case["question"], top_k=5)]
            if case["question_id"] in traced and [item[0] for item in lexical] != traced[case["question_id"]]:
                raise ValueError("BM25 stage replay mismatch")
            candidate = (rank_fused_ids if rank_fusion else lexical_slot)(baseline, lexical)
            rows.append({"id": prior["id"], "type": prior["type"],
                         "baseline_ids": baseline, "candidate_ids": candidate,
                         "bm25_top1": lexical[:1], "baseline": score(baseline, evidence),
                         "candidate": score(candidate, evidence), "tfidf_hit": prior["hit"]})
            if rank_fusion:
                rows[-1].update({"bm25_top5": lexical,
                                 "slot": score(lexical_slot(baseline, lexical), evidence)})
        finally:
            store.conn.close()
        if len(rows) % 50 == 0:
            print(f"completed {len(rows)}/470", flush=True)
    def summarize(group):
        return {"count": len(group),
                "baseline_hits": sum(row["baseline"]["hit"] for row in group),
                "candidate_hits": sum(row["candidate"]["hit"] for row in group),
                "tfidf_hits": sum(row["tfidf_hit"] for row in group),
                "changed_lists": sum(row["baseline_ids"] != row["candidate_ids"] for row in group),
                "rescued_ids": [row["id"] for row in group if not row["baseline"]["hit"] and row["candidate"]["hit"]],
                "lost_ids": [row["id"] for row in group if row["baseline"]["hit"] and not row["candidate"]["hit"]],
                "baseline_mean_evidence_recall": sum(row["baseline"]["evidence_recall"] for row in group) / len(group),
                "candidate_mean_evidence_recall": sum(row["candidate"]["evidence_recall"] for row in group) / len(group)}
    result = {"source_sha256": SHA256, "comparison_sha256": hashlib.sha256(comparison_raw).hexdigest(),
            "stage_sha256": hashlib.sha256(stages_raw).hexdigest(),
            "rule": "Keep saved MiniLM first four; replace fifth with positive BM25 top1 only if absent from saved Top-5. No label-based selection.",
            "summary": summarize(rows),
            "by_type": {kind: summarize([row for row in rows if row["type"] == kind]) for kind in sorted({row["type"] for row in rows})},
            "stage_replay_matches": len(traced), "negative_checks": negative_checks(guards_path, rank_fusion=rank_fusion),
            "rows": rows, "evaluation_is_independent": False, "eligible_for_default": False,
            "paid_api_calls": 0, "production_defaults_changed": False,
            "limits": "Offline report-side ablation on all 470 previously inspected non-abstention cases. MiniLM rankings inherited, no model encoding or live SDK/MCP timing measured. Official evidence labels used only by scorer; unlabelled turns are not assumed harmful. No answer generation or independent holdout; synthetic guards do not establish MiniLM safety."}
    if rank_fusion:
        result["rule"] = "Equal-weight RRF (k=60), saved MiniLM final Top-5 first, positive BM25 Top-5 second; final Top-5. Stable ties follow first encounter. No sweep or label-based selection."
        result["limits"] += " Saved MiniLM final ranks already mix signals, including BM25: this is not pure semantic-vs-lexical fusion or replacement of the production pipeline."
        result["summary"].update({
            "slot_hits": sum(row["slot"]["hit"] for row in rows),
            "gained_vs_slot": [row["id"] for row in rows if not row["slot"]["hit"] and row["candidate"]["hit"]],
            "lost_vs_slot": [row["id"] for row in rows if row["slot"]["hit"] and not row["candidate"]["hit"]]})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--comparison", type=Path, default=Path("results/longmemeval_minilm_full.json"))
    parser.add_argument("--stages", type=Path, default=Path("results/longmemeval_stage_probe.json"))
    parser.add_argument("--guards", type=Path, default=Path("experiments/safe_relation_rerank_cases.json"))
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--rank-fusion", action="store_true")
    args = parser.parse_args()
    result = run(args.dataset, args.comparison, args.stages, args.guards, rank_fusion=args.rank_fusion)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
