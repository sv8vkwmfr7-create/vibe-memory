"""Isolate legacy full-row vs atomic metadata-batch reinforcement WAL writes."""
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage
from experiments.disk_pressure_benchmark import QUERY
from experiments.scale_visibility_benchmark import _summary


def run_mode(mode):
    path = str(Path(tempfile.mkdtemp(prefix="vibe-reinforcement-write-")) / "test.db")
    store = VibeStorage(path, journal_mode="wal")
    try:
        for i in range(1000):
            content = QUERY + " 桌面背景颜色图片设置日常维护记录" * 5
            store.insert_atom(MemoryAtom(id=f"atom-{i}", agent_id="test", session_id="s",
                                        content=content, summary=content))
        ids = [f"atom-{i}" for i in range(5)]
        store.conn.execute("PRAGMA wal_autocheckpoint=0")
        store.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        times = []
        for _ in range(100):
            start = time.perf_counter()
            if mode == "legacy_full_row":
                for atom_id in ids:
                    atom = store.get_atom(atom_id)
                    atom.reinforce()
                    store.update_atom(atom)
            else:
                store.reinforce_atoms(ids, "test")
            times.append((time.perf_counter() - start) * 1000)
        wal_bytes = Path(path + "-wal").stat().st_size
        counts_ok = all(store.get_atom(atom_id).access_count == 100 for atom_id in ids)
        for table in ("atoms_fts", "atoms_trigram"):
            store.conn.execute(f"INSERT INTO {table}({table}, rank) VALUES ('integrity-check', 1)")
        store.conn.rollback()
        return {"mode": mode, "batches": 100, "atoms_per_batch": 5,
                "wal_bytes": wal_bytes, "batch_ms": _summary(times),
                "access_counts_correct": counts_ok, "fts_integrity": "ok"}
    finally:
        store.conn.close()


if __name__ == "__main__":
    rows = [run_mode(mode) for mode in ("legacy_full_row", "atomic_metadata_batch")]
    print("REPORT=" + json.dumps({"dataset_version": "reinforcement-write-v1", "modes": rows,
          "notes": "1000 seed atoms; no competing locks; 100 five-atom reinforcement batches; "
                   "legacy reference recreates old full-row update path; test-only auto-checkpoint disabled; "
                   "WAL measured before FTS checks; temp DBs retained; not mixed-workload WAL bound"}), flush=True)
    sys.exit(0 if all(row["access_counts_correct"] for row in rows) and rows[1]["wal_bytes"] < rows[0]["wal_bytes"] else 1)
