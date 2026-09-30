"""Exercise frozen final-rank RRF on preference counterexamples with local MiniLM."""

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from experiments.longmemeval_lexical_slot_probe import rank_fused_ids
from experiments.precision_stage_diagnostics import _recall_with_stages
from vibe_memory.embedding.provider import SentenceTransformerProvider
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


def judged(ids, target, negatives):
    return {"target_top5": target in ids, "target_top1": bool(ids and ids[0] == target),
            "known_negative_ids": sorted(set(ids) & negatives),
            "known_negative_top1": bool(ids and ids[0] in negatives)}


def run(cases_path: Path, model_dir: Path):
    raw = cases_path.read_bytes()
    data = json.loads(raw)
    if len(data["cases"]) != 4 or len({case["id"] for case in data["cases"]}) != 4:
        raise ValueError("expected four frozen unique preference cases")
    weight_hash = hashlib.sha256((model_dir / "model.safetensors").read_bytes()).hexdigest()
    if weight_hash != "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db":
        raise ValueError("expected the pinned MiniLM weights")
    provider = SentenceTransformerProvider(model_name=str(model_dir), device="cpu")
    if not provider.available:
        raise RuntimeError("sentence-transformers unavailable")
    rows = []
    for case in data["cases"]:
        ids = {atom["id"] for atom in case["atoms"]}
        negatives = set(case["negative_ids"])
        if len(ids) != len(case["atoms"]) or case["target_id"] not in ids or not negatives <= ids or case["target_id"] in negatives:
            raise ValueError("invalid case IDs/labels")
        store = VibeStorage(":memory:")
        try:
            for index, atom in enumerate(case["atoms"]):
                store.insert_atom(MemoryAtom(
                    id=atom["id"], agent_id=case["id"], session_id=f"session-{index}",
                    content=atom["content"], summary=atom["content"],
                    created_at=datetime(2026, 9, 28) + timedelta(minutes=index)))
            stored = store.get_atoms_by_agent(case["id"])
            documents = [atom.content for atom in stored]
            key = tuple((atom.id, atom.version) for atom in stored)
            bm25 = BM25Strategy()
            bm25.fit(documents)
            vectors = provider.encode(documents)
            if provider.name == "tfidf(fallback)":
                raise RuntimeError("MiniLM fallback is not allowed")
            baseline, stages = _recall_with_stages(
                store, case["query"], causal_bridge=False, agent_id=case["id"],
                embedding_provider=provider, semantic_cache={"key": key, "vectors": vectors},
                bm25_cache={"key": key, "index": bm25})
            lexical = [(stored[index].id, value) for index, value in bm25.search(case["query"], top_k=5)]
            if [item[0] for item in lexical] != stages["bm25"]:
                raise ValueError("BM25 stage mismatch")
            candidate = rank_fused_ids(baseline, lexical)
            rows.append({"id": case["id"], "baseline_ids": baseline, "bm25_ids": stages["bm25"],
                         "candidate_ids": candidate, "baseline": judged(baseline, case["target_id"], negatives),
                         "candidate": judged(candidate, case["target_id"], negatives)})
        finally:
            store.conn.close()
    return {"dataset_id": data["dataset_id"], "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "model_weight_sha256": weight_hash, "rows": rows,
            "summary": {arm: {metric: sum(row[arm][metric] for row in rows)
                              for metric in ("target_top5", "target_top1", "known_negative_top1")}
                        for arm in ("baseline", "candidate")},
            "rule": "Unchanged MiniLM final precision Top-5 + positive BM25 Top-5; equal RRF k=60, output five, final-rank list first.",
            "paid_api_calls": 0, "evaluation_is_independent": False, "eligible_for_default": False,
            "production_defaults_changed": False,
            "limits": data["provenance"] + " Actual cached CPU model encoding and core replay, not SDK/MCP end-to-end or answer generation. Labels used only by scorer. No automatic old/current selection. Retrieval of both a preference and a contradiction is not correct personalized answering. Costs/timing/memory unmeasured."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("experiments/preference_rank_negative_cases.json"))
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.cases, args.model_dir)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
