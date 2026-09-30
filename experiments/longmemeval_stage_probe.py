"""Observe unchanged retrieval stages on the 107 paired LongMemEval hit flips."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from experiments.longmemeval_tfidf_baseline import SHA256, prepare, save_checkpoint
from experiments.precision_stage_diagnostics import _rank, _recall_with_stages
from vibe_memory.embedding.provider import SentenceTransformerProvider, TfidfProvider
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


STAGES = ("semantic", "bm25", "graph", "temporal", "fused", "final")


def loss_stage(evidence: set[str], stages: dict) -> str:
    if evidence.intersection(stages["final"]):
        return "retained"
    if not evidence.intersection(set().union(*(set(stages[name]) for name in STAGES[:4]))):
        return "before_fusion"
    if not evidence.intersection(stages["fused"]):
        return "fusion_top10"
    return "final_rerank"


def run(dataset: Path, comparison: Path, model_dir: Path, checkpoint: Path, smoke: int = 0):
    raw = dataset.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError("dataset SHA-256 mismatch")
    comparison_raw = comparison.read_bytes()
    paired = json.loads(comparison_raw)
    model_hash = hashlib.sha256((model_dir / "model.safetensors").read_bytes()).hexdigest()
    if paired["source_sha256"] != SHA256 or paired["model_weight_sha256"] != model_hash:
        raise ValueError("comparison dataset/model hash mismatch")
    expected = {row["id"]: row for row in paired["rows"] if row["hit"] != row["model_hit"]}
    if len(expected) != 107 or sum(row["hit"] for row in expected.values()) != 63:
        raise ValueError("expected 63 model losses and 44 rescues")
    cases = [case for case in json.loads(raw) if case["question_id"] in expected]
    if len(cases) != len(expected) or len({case["question_id"] for case in cases}) != len(expected):
        raise ValueError("selected question IDs missing or duplicated")
    if smoke:
        cases = cases[:smoke]
    identity = {"source_sha256": SHA256, "model_weight_sha256": model_hash,
                "comparison_sha256": hashlib.sha256(comparison_raw).hexdigest(),
                "question_ids": [case["question_id"] for case in cases]}
    rows = []
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if saved["identity"] != identity:
            raise ValueError("stage checkpoint identity mismatch")
        rows = saved["rows"]
        if len(rows) > len(cases) or [row["id"] for row in rows] != identity["question_ids"][:len(rows)]:
            raise ValueError("stage checkpoint rows are not the selected prefix")
    provider = SentenceTransformerProvider(model_name=str(model_dir), device="cpu")
    if not provider.available:
        raise RuntimeError("sentence-transformers unavailable")
    provider._get_model()
    for case in cases[len(rows):]:
        atoms, evidence = prepare(case)
        store = VibeStorage(":memory:", tenant_id="longmemeval")
        try:
            for atom in atoms:
                store.insert_atom(atom)
            stored = store.get_atoms_by_agent(case["question_id"])
            documents = [atom.content for atom in stored]
            key = tuple((atom.id, atom.version) for atom in stored)
            tfidf = TfidfProvider().fit(documents)
            bm25 = BM25Strategy()
            bm25.fit(documents)
            vectors = provider.encode(documents)
            if provider.name == "tfidf(fallback)":
                raise RuntimeError("MiniLM fell back to TF-IDF")
            traces = {}
            for arm in ("tfidf", "model"):
                ids, stages = _recall_with_stages(
                    store, case["question"], causal_bridge=False,
                    agent_id=case["question_id"],
                    embedding_provider=tfidf if arm == "tfidf" else provider,
                    semantic_cache=({"key": key, "tfidf_fitted": True} if arm == "tfidf"
                                    else {"key": key, "vectors": vectors}),
                    bm25_cache={"key": key, "index": bm25})
                prior_ids = expected[case["question_id"]]["top5_ids" if arm == "tfidf" else "model_top5_ids"]
                if ids != prior_ids or any(name not in stages for name in STAGES):
                    raise RuntimeError(f'{case["question_id"]} {arm}: replay/stage mismatch')
                traces[arm] = {"loss_stage": loss_stage(evidence, stages),
                               "ids": {name: stages[name] for name in STAGES},
                               "evidence_ranks": {atom_id: {name: _rank(stages[name], atom_id)
                                                             for name in STAGES}
                                                  for atom_id in sorted(evidence)}}
            rows.append({"id": case["question_id"], "type": case["question_type"],
                         "group": "model_lost" if expected[case["question_id"]]["hit"] else "model_rescued",
                         "arms": traces})
        finally:
            store.conn.close()
        save_checkpoint(checkpoint, {"identity": identity, "rows": rows})
        if len(rows) % 10 == 0:
            print(f"completed {len(rows)}/{len(cases)}", flush=True)
    summary = {}
    for group, arm in (("model_lost", "model"), ("model_rescued", "tfidf")):
        summary[group] = dict(Counter(row["arms"][arm]["loss_stage"] for row in rows if row["group"] == group))
    losses = [row for row in rows if row["group"] == "model_lost"]
    summary["model_lost_route_evidence_hits"] = {
        name: sum(any(ranks[name] is not None for ranks in row["arms"]["model"]["evidence_ranks"].values())
                  for row in losses) for name in STAGES[:4]}
    summary["model_lost_fused_top5_evidence_hits"] = sum(
        any(ranks["fused"] is not None and ranks["fused"] <= 5
            for ranks in row["arms"]["model"]["evidence_ranks"].values()) for row in losses)
    summary["replay_match_rows"] = len(rows)
    return {**identity, "scope": "first-N stage smoke" if smoke else "all 107 paired hit flips",
            "mode": "unchanged precision Top-5; all four routes; fused Top-10",
            "summary": summary, "rows": rows, "paid_api_calls": 0,
            "limits": "Selected after observing full comparison, not independent evaluation or quality improvement. No ranking intervention, answer generation, performance claims, raw dialogue or production changes. final_rerank means evidence present in fused Top-10 but absent in final Top-5; it does not mean it was in fused Top-5 or prove harm caused by reranking. Stage traces do not establish causal benefit from disabling a stage."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--comparison", type=Path, default=Path("results/longmemeval_minilm_full.json"))
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--smoke", type=int, default=0)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    if args.smoke < 0:
        parser.error("smoke must be nonnegative")
    result = run(args.dataset, args.comparison, args.model_dir, args.checkpoint, args.smoke)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
