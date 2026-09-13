"""Disk SQLite, independent connections, two writers and two recall readers."""
import argparse
import json
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall
from vibe_memory.embedding import TfidfProvider
from experiments.scale_visibility_benchmark import _summary


def run(seed_count=10000, writes=200, reads=200, journal_mode="delete"):
    directory = tempfile.mkdtemp(prefix="vibe-disk-concurrency-")
    path = str(Path(directory) / "test.db")
    if journal_mode not in ("delete", "wal"):
        raise ValueError("Expected delete or wal journal mode")
    storage = VibeStorage(path, journal_mode=journal_mode)
    storage.insert_atom(MemoryAtom(id="anchor", agent_id="test", session_id="old",
                                  content="连接池超时修复", summary="连接池超时修复"))
    for i in range(seed_count):
        storage.insert_atom(MemoryAtom(id=f"seed-{i}", agent_id="test", session_id="background",
                                      content="桌面背景维护", summary="桌面背景维护"))
    journal = storage.conn.execute("PRAGMA journal_mode").fetchone()[0]
    storage.conn.close()
    barrier = threading.Barrier(4)

    def writer(worker):
        store = VibeStorage(path)
        latencies, errors = [], []
        barrier.wait(timeout=30)
        for i in range(writes):
            start = time.perf_counter()
            try:
                atom = MemoryAtom(id=f"write-{worker}-{i}", agent_id="test", session_id="writer",
                                  content="验证码采集", summary="验证码采集")
                store.insert_atom(atom)
                if i % 2 == 0:
                    atom.content = atom.summary = "连接资源释放"
                    store.update_atom(atom)
                if i % 5 == 0:
                    store.delete_atom(atom.id)
                latencies.append((time.perf_counter() - start) * 1000)
            except Exception as error:
                store.conn.rollback()
                errors.append(type(error).__name__ + ": " + str(error))
        store.conn.close()
        return {"worker": worker, "completed": len(latencies), "errors": errors,
                "crud_cycle_ms": _summary(latencies)}

    def reader(worker):
        store = VibeStorage(path)
        provider, semantic_cache, bm25_cache = TfidfProvider(), {}, {}
        times, hits, errors = [], 0, []
        barrier.wait(timeout=30)
        for _ in range(reads):
            start = time.perf_counter()
            try:
                result = recall("连接池超时修复", "test", store, mode="budget", top_k=5,
                                embedding_provider=provider, semantic_cache=semantic_cache,
                                bm25_cache=bm25_cache)
                hits += int("anchor" in {atom.id for atom in result["atoms"]})
                times.append((time.perf_counter() - start) * 1000)
            except Exception as error:
                store.conn.rollback()
                errors.append(type(error).__name__ + ": " + str(error))
        store.conn.close()
        return {"worker": worker, "completed": len(times), "anchor_hits": hits,
                "errors": errors, "recall_ms": _summary(times)}

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(writer, i) for i in range(2)] + [pool.submit(reader, i) for i in range(2)]
        workers = [future.result() for future in futures]
    elapsed = time.perf_counter() - start
    fresh = VibeStorage(path)
    expected_new, expected_old, deleted = set(), set(), set()
    for worker in range(2):
        for i in range(writes):
            atom_id = f"write-{worker}-{i}"
            (deleted if i % 5 == 0 else expected_new if i % 2 == 0 else expected_old).add(atom_id)
    # Exact expected cardinality avoids unmatched recency backfill hiding
    # missing or stale matching rows in the indexed candidate path.
    new_ids = {a.id for a in fresh.get_recall_candidates("test", "连接资源释放", len(expected_new))}
    old_ids = {a.id for a in fresh.get_recall_candidates("test", "验证码采集", len(expected_old))}
    visible = all(fresh.get_atom(atom_id) is None for atom_id in deleted)
    consistent = new_ids == expected_new and old_ids == expected_old and visible
    integrity = fresh.conn.execute("PRAGMA integrity_check").fetchone()[0]
    for table in ("atoms_fts", "atoms_trigram"):
        fresh.conn.execute(f"INSERT INTO {table}({table}, rank) VALUES ('integrity-check', 1)")
    fresh.conn.rollback()
    fresh.conn.close()
    return {"dataset_version": "disk-concurrency-v1", "temporary_database": path,
            "journal_mode": journal, "seed_atoms": seed_count, "writes_per_worker": writes,
            "reads_per_worker": reads, "elapsed_seconds": round(elapsed, 3),
            "writers": workers[:2], "readers": workers[2:],
            "post_join_crud_consistent": consistent, "integrity_check": integrity,
            "fts_external_content_integrity": "ok",
            "notes": "Independent connection per thread; synthetic selective query; reader/writer overlap begins at barrier; post-join checks are not an atomic cross-connection read-your-writes guarantee; temp DB retained"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=10000)
    parser.add_argument("--writes", type=int, default=200)
    parser.add_argument("--reads", type=int, default=200)
    parser.add_argument("--journal", choices=["delete", "wal"], default="delete")
    args = parser.parse_args()
    if min(args.seed, args.writes, args.reads) < 1:
        parser.error("Counts must be positive")
    report = run(args.seed, args.writes, args.reads, args.journal)
    print(json.dumps(report, indent=2))
    passed = report["post_join_crud_consistent"] and report["integrity_check"] == "ok"
    passed = passed and all(not row["errors"] for row in report["writers"] + report["readers"])
    passed = passed and all(row["anchor_hits"] == args.reads for row in report["readers"])
    sys.exit(0 if passed else 1)
