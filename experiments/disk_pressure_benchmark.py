"""Dense disk recall, SDK write-lock pressure, and held-reader WAL growth.

Fresh local temporary DB only; six-second holds are not endurance tests.
"""
import argparse
import json
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall
from vibe_memory.embedding import TfidfProvider
from experiments.scale_visibility_benchmark import _summary


QUERY = "连接池超时修复"


def dense_disk(path, scale, samples):
    storage = VibeStorage(path, journal_mode="wal")
    try:
        for i in range(scale):
            content = QUERY if i == 0 else QUERY + " " + "桌面背景颜色图片设置日常维护记录 " * 5
            storage.insert_atom(MemoryAtom(id=f"dense-{i}", agent_id="dense",
                                          session_id="old" if i == 0 else "background",
                                          content=content, summary=content,
                                          created_at=datetime(2026, 1 if i == 0 else 2, 1)))
    finally:
        storage.conn.close()
    # Reopen the file rather than benchmark the seeding connection.
    memory = VibeMemory("dense", path, embedding_backend="tfidf")
    provider, semantic_cache, bm25_cache = TfidfProvider(), {}, {}
    lower_ms, sdk_ms = [], []
    lower_hits = sdk_hits = 0
    try:
        for _ in range(samples):
            start = time.perf_counter()
            result = recall(QUERY, "dense", memory.storage, mode="budget", top_k=5,
                            embedding_provider=provider, semantic_cache=semantic_cache,
                            bm25_cache=bm25_cache)
            lower_ms.append((time.perf_counter() - start) * 1000)
            lower_hits += int(any(atom.id == "dense-0" for atom in result["atoms"]))
            start = time.perf_counter()
            result = memory.recall(QUERY, mode="budget", top_k=5)
            sdk_ms.append((time.perf_counter() - start) * 1000)
            sdk_hits += int(any(atom.id == "dense-0" for atom in result["atoms"]))
        return {"atoms": scale, "samples": samples, "lower_hits": lower_hits,
                "sdk_hits": sdk_hits, "lower_first_ms": round(lower_ms[0], 3),
                "sdk_first_ms": round(sdk_ms[0], 3), "lower_warm_ms": _summary(lower_ms[1:]),
                "sdk_warm_ms": _summary(sdk_ms[1:])}
    finally:
        memory.storage.conn.close()


def write_lock(path, hold_seconds):
    holder = VibeStorage(path, journal_mode="wal")
    holder.insert_atom(MemoryAtom(id="anchor", agent_id="lock", session_id="s",
                                 content=QUERY, summary=QUERY))
    ready, locked = threading.Event(), threading.Event()

    def request():
        memory = VibeMemory("lock", path, embedding_backend="tfidf")
        try:
            ready.set()
            if not locked.wait(timeout=10):
                raise TimeoutError("Lock handshake failed")
            provider = TfidfProvider()
            start = time.perf_counter()
            result = recall(QUERY, "lock", memory.storage, mode="budget", top_k=5,
                            embedding_provider=provider)
            lower_ms = (time.perf_counter() - start) * 1000
            lower_hit = any(atom.id == "anchor" for atom in result["atoms"])
            start = time.perf_counter()
            error_name = None
            try:
                memory.recall(QUERY, mode="budget", top_k=5)
            except sqlite3.OperationalError as error:
                if error.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                    raise
                error_name = "SQLITE_BUSY"
                memory.storage.conn.rollback()
            return {"lower_hit": lower_hit, "lower_ms": round(lower_ms, 3),
                    "sdk_error": error_name,
                    "sdk_elapsed_ms": round((time.perf_counter() - start) * 1000, 3)}
        finally:
            memory.storage.conn.close()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(request)
            if not ready.wait(timeout=10):
                future.result(timeout=1)
                raise TimeoutError("Reader initialization failed")
            holder.conn.execute("BEGIN IMMEDIATE")
            start = time.perf_counter()
            locked.set()
            try:
                time.sleep(hold_seconds)
            finally:
                holder.conn.rollback()
            report = future.result(timeout=10)
            report["hold_seconds"] = round(time.perf_counter() - start, 3)
            # Verify that the same file remains usable after contention ends.
            recovered = VibeMemory("lock", path, embedding_backend="tfidf")
            try:
                report["sdk_after_release_hit"] = any(
                    atom.id == "anchor" for atom in recovered.recall(QUERY)["atoms"])
            finally:
                recovered.storage.conn.close()
            return report
    finally:
        locked.set()
        holder.conn.close()


def reader_growth(path, hold_seconds, writes=200):
    writer = VibeStorage(path, journal_mode="wal")
    reader = VibeStorage(path)
    try:
        writer.insert_atom(MemoryAtom(id="anchor", agent_id="growth", session_id="s",
                                     content=QUERY, summary=QUERY))
        writer.conn.execute("PRAGMA wal_autocheckpoint=0")
        writer.conn.execute("PRAGMA busy_timeout=0")
        writer.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        reader.conn.execute("BEGIN")
        assert reader.get_atom("anchor") is not None
        start = time.perf_counter()
        before = Path(path + "-wal").stat().st_size
        for i in range(writes):
            writer.insert_atom(MemoryAtom(id=f"growth-{i}", agent_id="growth", session_id="s",
                                         content="后台维护记录", summary="后台维护记录"))
        time.sleep(max(0, hold_seconds - (time.perf_counter() - start)))
        pinned = list(writer.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        after = Path(path + "-wal").stat().st_size
        hidden = reader.get_atom(f"growth-{writes - 1}") is None
        held = time.perf_counter() - start
        reader.conn.rollback()
        released = list(writer.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        visible = reader.get_atom(f"growth-{writes - 1}") is not None
        integrity = writer.conn.execute("PRAGMA integrity_check").fetchone()[0]
        return {"writes": writes, "hold_seconds": round(held, 3), "wal_bytes_before": before,
                "wal_bytes_pinned": after, "checkpoint_pinned": pinned,
                "checkpoint_released": released,
                "wal_bytes_released": Path(path + "-wal").stat().st_size,
                "snapshot_hides_new_atom": hidden, "after_release_visible": visible,
                "integrity_check": integrity}
    finally:
        reader.conn.close()
        writer.conn.close()


def run(scales, samples=10, hold_seconds=6):
    directory = Path(tempfile.mkdtemp(prefix="vibe-disk-pressure-"))
    return {"dataset_version": "disk-pressure-v1", "sqlite_version": sqlite3.sqlite_version,
            "journal_mode": "wal", "dense": [dense_disk(str(directory / f"dense-{n}.db"), n, samples)
                                                for n in scales],
            "write_lock": write_lock(str(directory / "write-lock.db"), hold_seconds),
            "reader_growth": reader_growth(str(directory / "reader-growth.db"), hold_seconds),
            "notes": "Synthetic repeated whole-query matches, no graph; first calls are not OS-cold; "
                     "lower recall precedes SDK recall and warms DB; SDK reinforces hits with writes; "
                     "held-reader test disables auto-checkpoint only on its writer; "
                     "temp DBs retained; seconds-long holds, not endurance or power-loss proof"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, nargs="+", default=[1000, 10000])
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()
    if min(args.scale) <= 100 or args.samples < 2:
        parser.error("Scales must exceed 100; samples must be at least 2")
    report = run(args.scale, args.samples)
    print(json.dumps(report, indent=2))
    passed = all(row["lower_hits"] == args.samples and row["sdk_hits"] == args.samples
                 for row in report["dense"])
    lock, growth = report["write_lock"], report["reader_growth"]
    passed = passed and lock["lower_hit"] and lock["sdk_error"] == "SQLITE_BUSY" and lock["sdk_after_release_hit"]
    passed = passed and growth["checkpoint_pinned"][0] == 1 and growth["checkpoint_released"] == [0, 0, 0]
    passed = passed and growth["wal_bytes_pinned"] > growth["wal_bytes_before"] and growth["wal_bytes_released"] == 0
    passed = passed and growth["snapshot_hides_new_atom"] and growth["after_release_visible"] and growth["integrity_check"] == "ok"
    sys.exit(0 if passed else 1)
