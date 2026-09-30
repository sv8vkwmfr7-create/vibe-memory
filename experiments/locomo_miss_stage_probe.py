"""Locate official-evidence losses before or after lexical Top-5 on one LoCoMo sample."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

from experiments.locomo_answer_pilot import select_cases
from experiments.locomo_retrieval import build_corpus
from vibe_memory.doctor import MCPProcess
from vibe_memory.embedding.provider import TfidfProvider
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


def loss_stage(gold: set[str], semantic: set[str], bm25: set[str], final: set[str]) -> str:
    if gold & final:
        return "hit"
    if gold & (semantic | bm25):
        return "after_lexical_top5"
    return "before_lexical_top5"


def best_rank(gold: set[str], ranked: list[str]) -> int | None:
    return next((index for index, source_id in enumerate(ranked, 1) if source_id in gold), None)


def run(dataset: Path) -> dict:
    raw = dataset.read_bytes()
    sample = json.loads(raw)[0]
    cases = select_cases(sample, 11)
    corpus, _ = build_corpus(sample)
    with TemporaryDirectory(prefix="vibe-locomo-stage-") as directory:
        db_path = str(Path(directory) / "memory.db")
        source_ids = {}
        client = MCPProcess(db_path, sample["sample_id"], 30, sys.executable)
        try:
            client.request("initialize")
            for atom in corpus["atoms"]:
                stored = client.call_tool("vibe_store", {"content": atom["content"],
                                                         "session_id": atom["session_id"]})
                source_ids[stored["id"][:8]] = atom["id"]
        finally:
            client.close()
        sleep(0.2)

        storage = VibeStorage(db_path)
        try:
            atoms = storage.get_atoms_by_agent(sample["sample_id"])
            assert len(atoms) == len(corpus["atoms"])
            documents = [atom.content for atom in atoms]
            by_source = {source_ids[atom.id[:8]]: atom for atom in atoms}
            tfidf = TfidfProvider()
            tfidf.fit(documents)
            bm25 = BM25Strategy()
            bm25.fit(documents)
            rows = []
            client = MCPProcess(db_path, sample["sample_id"], 30, sys.executable)
            try:
                client.request("initialize")
                for case in cases:
                    query = case["question"]
                    semantic_indices, _ = tfidf.search(query, top_k=5)
                    semantic = {source_ids[atoms[i].id[:8]] for i in semantic_indices}
                    lexical = {source_ids[atoms[i].id[:8]] for i, _ in bm25.search(query, top_k=5)}
                    result = client.call_tool("vibe_recall", {"query": query,
                                                              "mode": "precision", "top_k": 5})
                    final = {source_ids[item["id"]] for item in result["memories"]}
                    expanded = client.call_tool("vibe_recall", {"query": query,
                                                                "mode": "precision", "top_k": 20})
                    expanded_ids = {source_ids[item["id"]] for item in expanded["memories"]}
                    gold = set(case["evidence"])
                    all_semantic_indices, all_similarities = tfidf.search(query, top_k=len(atoms))
                    semantic_ranked = [source_ids[atoms[i].id[:8]] for i, score in
                                       zip(all_semantic_indices, all_similarities) if score > 0]
                    bm25_ranked = [source_ids[atoms[i].id[:8]] for i, _ in
                                   bm25.search(query, top_k=len(atoms))]
                    query_terms = set(bm25._tokenize(query))
                    gold_terms = {term for source_id in gold for term in
                                  bm25._tokenize(by_source[source_id].content)}
                    rows.append({"id": case["id"],
                                 "stage": loss_stage(gold, semantic, lexical, final),
                                 "semantic_hit": bool(gold & semantic),
                                 "bm25_hit": bool(gold & lexical),
                                 "final_hit": bool(gold & final),
                                 "top20_hit": bool(gold & expanded_ids),
                                 "best_semantic_rank": best_rank(gold, semantic_ranked),
                                 "best_bm25_rank": best_rank(gold, bm25_ranked),
                                 "query_gold_term_overlap": len(query_terms & gold_terms)})
            finally:
                client.close()
        finally:
            storage.conn.close()
    return {"source_sha256": hashlib.sha256(raw).hexdigest(),
            "sample_id": sample["sample_id"], "stored_turns": len(corpus["atoms"]),
            "mode": "unchanged MCP precision Top-5, report-only Top-20 comparison; TF-IDF/BM25 ranks read from same DB",
            "rows": rows,
            "counts": {stage: sum(row["stage"] == stage for row in rows)
                       for stage in ("hit", "before_lexical_top5", "after_lexical_top5")},
            "top20_hits": sum(row["top20_hit"] for row in rows),
            "limits": "Official evidence IDs are not exhaustive relevance labels. Semantic/BM25 are first-stage diagnostics, not independent candidate pools; graph, temporal, fusion and rerank may also affect final Top-5. One previously tuned sample, no production change."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--require-all", action="store_true", help="Exit nonzero unless every official evidence set hits MCP Top-5")
    args = parser.parse_args()
    report = run(args.dataset)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        args.json.write_text(output, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(output)
    if args.require_all and report["counts"]["hit"] != len(report["rows"]):
        raise SystemExit(1)
