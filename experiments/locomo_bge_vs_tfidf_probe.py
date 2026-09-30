"""Compare warm TF-IDF and local BGE core precision recall on the same MCP-written LoCoMo DB."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from experiments.hybrid_embedding_probe import working_set_bytes
from experiments.locomo_answer_pilot import select_cases
from experiments.locomo_retrieval import build_corpus
from vibe_memory.doctor import MCPProcess
from vibe_memory.embedding.provider import SentenceTransformerProvider, TfidfProvider
from vibe_memory.retrieval.ppr import recall
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


def hit(ids: list[str], evidence: list[str]) -> bool:
    return bool(set(ids) & set(evidence))


def run(dataset: Path, model_dir: Path) -> dict:
    if not model_dir.is_dir():
        raise FileNotFoundError(model_dir)
    raw = dataset.read_bytes()
    sample = json.loads(raw)[0]
    cases = select_cases(sample, 11)
    corpus, _ = build_corpus(sample)
    provider = SentenceTransformerProvider(model_name=str(model_dir), device="cpu")
    if not provider.available:
        raise RuntimeError("sentence-transformers is not installed; BGE comparison cannot run")

    with TemporaryDirectory(prefix="vibe-locomo-bge-") as directory:
        db_path = str(Path(directory) / "memory.db")
        source_ids = {}
        client = MCPProcess(db_path, sample["sample_id"], 30, sys.executable)
        write_start = perf_counter()
        try:
            client.request("initialize")
            for atom in corpus["atoms"]:
                stored = client.call_tool("vibe_store", {"content": atom["content"],
                                                         "session_id": atom["session_id"]})
                source_ids[stored["id"][:8]] = atom["id"]
        finally:
            client.close()
        write_ms = round((perf_counter() - write_start) * 1000, 1)
        sleep(0.2)

        mcp = {}
        client = MCPProcess(db_path, sample["sample_id"], 30, sys.executable)
        try:
            client.request("initialize")
            for case in cases:
                result = client.call_tool("vibe_recall", {"query": case["question"],
                                                          "mode": "precision", "top_k": 5})
                mcp[case["id"]] = [source_ids[item["id"]] for item in result["memories"]]
        finally:
            client.close()
        sleep(0.2)

        storage = VibeStorage(db_path)
        try:
            atoms = storage.get_atoms_by_agent(sample["sample_id"])
            if len(atoms) != len(corpus["atoms"]):
                raise RuntimeError("MCP store did not preserve all dialogue turns")
            documents = [atom.content for atom in atoms]
            cache_key = tuple((atom.id, atom.version) for atom in atoms)
            bm25 = BM25Strategy()
            bm25.fit(documents)
            bm25_cache = {"key": cache_key, "index": bm25}
            tfidf = TfidfProvider()
            tfidf_start = perf_counter()
            tfidf.fit(documents)
            tfidf_setup_ms = round((perf_counter() - tfidf_start) * 1000, 1)
            tfidf_cache = {"key": cache_key, "tfidf_fitted": True}

            before_bge = working_set_bytes()
            bge_start = perf_counter()
            vectors = provider.encode(documents)
            bge_setup_ms = round((perf_counter() - bge_start) * 1000, 1)
            after_bge = working_set_bytes()
            if provider.name == "tfidf(fallback)":
                raise RuntimeError("BGE silently fell back to TF-IDF")
            bge_cache = {"key": cache_key, "vectors": vectors}

            rows = []
            for index, case in enumerate(cases):
                results = {}
                for name in (("tfidf", "bge") if index % 2 == 0 else ("bge", "tfidf")):
                    start = perf_counter()
                    found = recall(case["question"], sample["sample_id"], storage,
                                   mode="precision", top_k=5,
                                   embedding_provider=tfidf if name == "tfidf" else provider,
                                   semantic_cache=tfidf_cache if name == "tfidf" else bge_cache,
                                   bm25_cache=bm25_cache)
                    elapsed = round((perf_counter() - start) * 1000, 1)
                    results[name] = {"ids": [source_ids[atom.id[:8]] for atom in found["atoms"]],
                                     "recall_ms": elapsed}
                rows.append({"id": case["id"], "mcp_hit": hit(mcp[case["id"]], case["evidence"]),
                             "tfidf_hit": hit(results["tfidf"]["ids"], case["evidence"]),
                             "bge_hit": hit(results["bge"]["ids"], case["evidence"]),
                             "tfidf_matches_mcp": results["tfidf"]["ids"] == mcp[case["id"]],
                             "tfidf_recall_ms": results["tfidf"]["recall_ms"],
                             "bge_recall_ms": results["bge"]["recall_ms"]})
        finally:
            storage.conn.close()

    return {"source": "https://github.com/snap-research/locomo/blob/main/data/locomo10.json",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "sample_id": sample["sample_id"], "question_count": len(cases),
            "stored_turns": len(corpus["atoms"]), "mode": "precision Top-5; same MCP-written DB; warm core recall",
            "model": "BAAI/bge-small-zh-v1.5", "model_dir": str(model_dir),
            "model_files_bytes": sum(path.stat().st_size for path in model_dir.rglob("*") if path.is_file()),
            "paid_model_calls": 0, "write_ms": write_ms,
            "tfidf_setup_ms": tfidf_setup_ms, "bge_load_and_encode_ms": bge_setup_ms,
            "working_set_before_bge_bytes": before_bge,
            "working_set_after_bge_bytes": after_bge,
            "working_set_bge_delta_bytes": None if before_bge is None or after_bge is None
                                            else after_bge - before_bge,
            "rows": rows,
            "mcp_hits": sum(row["mcp_hit"] for row in rows),
            "tfidf_hits": sum(row["tfidf_hit"] for row in rows),
            "bge_hits": sum(row["bge_hit"] for row in rows),
            "tfidf_mcp_order_agreement": sum(row["tfidf_matches_mcp"] for row in rows),
            "bge_rescued": [row["id"] for row in rows if not row["tfidf_hit"] and row["bge_hit"]],
            "bge_lost": [row["id"] for row in rows if row["tfidf_hit"] and not row["bge_hit"]],
            "tfidf_recall_p50_ms": round(median(row["tfidf_recall_ms"] for row in rows), 1),
            "bge_recall_p50_ms": round(median(row["bge_recall_ms"] for row in rows), 1),
            "limits": "One LoCoMo conversation and category, already used in earlier retrieval tuning: not an independent holdout. Official evidence IDs are not exhaustive relevance labels and no final answers were generated. BGE is a Chinese model tested on English QA. Setup uses one process, warm in-memory vectors and BM25; this is not a full BGE SDK/MCP write or first-query latency measurement. Windows working-set delta is process-wide, not model-only peak RAM. Original dataset stays outside Git; no paid API, human review or production default change."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model-dir", type=Path, default=Path("models/bge-small-zh-v1.5"))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run(args.dataset, args.model_dir)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        args.json.write_text(output, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(output)
