"""High-match Chinese candidate ranking; deterministic synthetic corpus."""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall
from vibe_memory.embedding import TfidfProvider
from experiments.scale_visibility_benchmark import _summary


def run_scale(scale, samples=10):
    storage = VibeStorage(":memory:")
    query = "连接池超时修复"
    for i in range(scale):
        content = query if i == 0 else query + " " + "桌面背景颜色图片设置日常维护记录 " * 5
        storage.insert_atom(MemoryAtom(
            id=f"dense-{i}", agent_id="dense", session_id="old" if i == 0 else "background",
            content=content, summary=content,
            created_at=datetime(2026, 1 if i == 0 else 2, 1),
        ))
    provider, semantic_cache, bm25_cache = TfidfProvider(), {}, {}
    candidate_ms, recall_ms = [], []
    candidate_hits = recall_hits = 0
    try:
        for _ in range(samples):
            start = time.perf_counter()
            candidates = storage.get_recall_candidates("dense", query, 100)
            candidate_ms.append((time.perf_counter() - start) * 1000)
            candidate_hits += int("dense-0" in {atom.id for atom in candidates})
            start = time.perf_counter()
            result = recall(query, "dense", storage, mode="budget", top_k=5,
                            embedding_provider=provider, semantic_cache=semantic_cache,
                            bm25_cache=bm25_cache)
            recall_ms.append((time.perf_counter() - start) * 1000)
            recall_hits += int("dense-0" in {atom.id for atom in result["atoms"]})
        return {"atoms": scale, "samples": samples,
                "old_answer_candidate_hits": candidate_hits,
                "old_answer_top5_hits": recall_hits,
                "candidate_ms": _summary(candidate_ms),
                "recall_cold_ms": round(recall_ms[0], 3),
                "recall_warm_ms": _summary(recall_ms[1:])}
    finally:
        storage.conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, nargs="+", default=[1000, 10000])
    args = parser.parse_args()
    if min(args.scale) < 101:
        parser.error("Scales must exceed the 100-candidate limit")
    print(json.dumps({"dataset_version": "chinese-dense-v1", "storage": ":memory:",
                      "notes": "All memories contain the whole query; old exact answer vs long background matches; single repeated query; no graph; no tracemalloc; not real-session evidence",
                      "scales": [run_scale(scale) for scale in args.scale]}, indent=2))


if __name__ == "__main__":
    main()
