"""Five-minute dense WAL-file mixed CRUD/SDK recall soak; fresh temp DB only."""
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
from experiments.disk_pressure_benchmark import QUERY
from experiments.scale_visibility_benchmark import _summary


def run(scale=100000, seconds=300):
    path = str(Path(tempfile.mkdtemp(prefix="vibe-disk-soak-")) / "test.db")
    storage = VibeStorage(path, journal_mode="wal")
    background = QUERY + " " + "桌面背景颜色图片设置日常维护记录 " * 5
    try:
        for i in range(scale):
            content = QUERY if i == 0 else background
            storage.insert_atom(MemoryAtom(id=f"dense-{i}", agent_id="dense", session_id="s",
                                          content=content, summary=content,
                                          created_at=datetime(2026, 1 if i == 0 else 2, 1)))
            if (i + 1) % 10000 == 0:
                print(f"Seeded {i + 1}/{scale}", flush=True)
        storage.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        barrier, stop = threading.Barrier(4), threading.Event()
        deadline = [0.0]

        def reader(worker):
            memory = VibeMemory("dense", path, embedding_backend="tfidf")
            times, hits, skipped = [], 0, 0
            try:
                barrier.wait(timeout=30)
                while time.perf_counter() < deadline[0] and not stop.is_set():
                    start = time.perf_counter()
                    result = memory.recall(QUERY, mode="budget", top_k=5)
                    times.append((time.perf_counter() - start) * 1000)
                    hits += int(any(atom.id == "dense-0" for atom in result["atoms"]))
                    skipped += int(result["reinforcement_skipped"])
                return {"worker": worker, "calls": len(times), "anchor_hits": hits,
                        "reinforcement_skipped_calls": skipped, "sdk_ms": _summary(times)}
            finally:
                memory.storage.conn.close()

        def writer():
            store = VibeStorage(path)
            times, cycles = [], 0
            try:
                barrier.wait(timeout=30)
                while time.perf_counter() < deadline[0] and not stop.is_set():
                    start = time.perf_counter()
                    atom = MemoryAtom(id=f"write-{cycles}", agent_id="dense", session_id="writer",
                                      content=background, summary=background)
                    store.insert_atom(atom)
                    atom.content = atom.summary = background + " 已更新"
                    store.update_atom(atom)
                    # Deliberate short writer pressure, not a core default change.
                    store.conn.execute("BEGIN IMMEDIATE")
                    store.conn.execute("UPDATE atoms SET weight=weight WHERE id=?", (atom.id,))
                    time.sleep(0.05)
                    store.conn.commit()
                    if cycles >= 128:
                        store.delete_atom(f"write-{cycles - 128}")
                    cycles += 1
                    times.append((time.perf_counter() - start) * 1000)
                return {"cycles": cycles, "inserts": cycles, "updates": cycles,
                        "deletes": max(0, cycles - 128), "deliberate_hold_ms": 50,
                        "cycle_ms": _summary(times)}
            finally:
                store.conn.close()

        wal_peak, checkpoints = 0, []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(reader, i) for i in range(2)] + [pool.submit(writer)]
            start = time.perf_counter()
            deadline[0] = start + seconds
            barrier.wait(timeout=30)
            try:
                while time.perf_counter() < deadline[0]:
                    stop.wait(min(10, max(0, deadline[0] - time.perf_counter())))
                    for future in futures:
                        if future.done():
                            future.result()  # Surface errors rather than count them as success.
                    wal_peak = max(wal_peak, Path(path + "-wal").stat().st_size)
                    checkpoints.append(list(storage.conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()))
                    print(f"Elapsed {time.perf_counter() - start:.1f}s; sampled WAL peak {wal_peak} bytes", flush=True)
                workers = [future.result(timeout=15) for future in futures]
            finally:
                stop.set()
        elapsed = time.perf_counter() - start
        count = workers[2]["cycles"]
        expected = {f"write-{i}" for i in range(max(0, count - 128), count)}
        atoms = storage.get_atoms_by_session("writer")
        consistent = {atom.id for atom in atoms} == expected and all(
            atom.content == background + " 已更新" and atom.summary == background + " 已更新"
            for atom in atoms)
        integrity = storage.conn.execute("PRAGMA integrity_check").fetchone()[0]
        for table in ("atoms_fts", "atoms_trigram"):
            storage.conn.execute(f"INSERT INTO {table}({table}, rank) VALUES ('integrity-check', 1)")
        storage.conn.rollback()
        truncated = list(storage.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        return {"dataset_version": "disk-soak-v1", "sqlite_version": sqlite3.sqlite_version,
                "initial_atoms": scale, "requested_seconds": seconds,
                "elapsed_seconds": round(elapsed, 3), "readers": workers[:2], "writer": workers[2],
                "wal_sampled_peak_bytes": wal_peak, "passive_checkpoint_samples": len(checkpoints),
                "last_passive_checkpoint": checkpoints[-1], "final_truncate": truncated,
                "wal_bytes_after_truncate": Path(path + "-wal").stat().st_size,
                "post_join_crud_consistent": consistent, "integrity_check": integrity,
                "fts_external_content_integrity": "ok",
                "notes": "Fresh WAL file; two independent SDK readers and one CRUD writer; "
                         "all records contain the whole repeated query; no graph, no held reader snapshot; "
                         "writer adds 50ms lock per cycle; default auto-checkpoint plus PASSIVE every 10s; "
                         "seeding excluded, barrier startup included, no retries; skipped flag may include partial reinforcement; "
                         "10s WAL sampling is not a hard maximum; local temp DB retained"}
    finally:
        storage.conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, default=100000)
    parser.add_argument("--seconds", type=float, default=300)
    args = parser.parse_args()
    if args.scale <= 100 or args.seconds <= 0:
        parser.error("Scale must exceed 100 and seconds must be positive")
    report = run(args.scale, args.seconds)
    print("REPORT=" + json.dumps(report), flush=True)
    passed = all(row["calls"] > 0 and row["calls"] == row["anchor_hits"] for row in report["readers"])
    passed = passed and report["writer"]["cycles"] > 0 and report["post_join_crud_consistent"]
    passed = passed and report["integrity_check"] == "ok" and report["final_truncate"] == [0, 0, 0]
    passed = passed and report["wal_bytes_after_truncate"] == 0
    sys.exit(0 if passed else 1)
