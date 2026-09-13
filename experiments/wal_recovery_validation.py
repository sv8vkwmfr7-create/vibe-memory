"""Deterministic WAL snapshot/checkpoint and child-process crash validation.

Only fresh temporary databases; no SDK transaction API is added.
"""
import json
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory import VibeMemory


def validate_transactions(path):
    writer = VibeStorage(path, journal_mode="wal")
    reader = VibeStorage(path)
    competitor = VibeStorage(path)
    try:
        writer.conn.execute("PRAGMA wal_autocheckpoint=0")
        competitor.conn.execute("PRAGMA busy_timeout=0")
        writer.insert_atom(MemoryAtom(id="anchor", agent_id="test", session_id="s",
                                     content="原始快照", summary="原始快照"))
        writer.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        reader.conn.execute("BEGIN")
        assert reader.get_atom("anchor").content == "原始快照"
        writer.conn.execute("BEGIN IMMEDIATE")
        writer.conn.execute("UPDATE atoms SET content=?, summary=? WHERE id=?",
                            ("事务提交修复", "事务提交修复", "anchor"))
        hidden = competitor.get_atom("anchor").content == "原始快照"
        blocked = False
        try:
            competitor.insert_atom(MemoryAtom(id="contender", agent_id="test",
                                              session_id="s", content="竞争写入", summary="竞争写入"))
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise
            blocked = True
        finally:
            competitor.conn.rollback()
        writer.conn.commit()
        retained = reader.get_atom("anchor").content == "原始快照"
        competitor.conn.execute("PRAGMA busy_timeout=0")
        pinned = list(competitor.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        reader.conn.rollback()
        visible = reader.get_atom("anchor").content == "事务提交修复"
        released = list(competitor.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        # The failed competing write must not leave a committed atom behind.
        assert competitor.get_atom("contender") is None
        return {"uncommitted_hidden": hidden, "competing_writer_blocked": blocked,
                "snapshot_retained": retained, "committed_visible_after_snapshot": visible,
                "checkpoint_pinned": pinned, "checkpoint_released": released}
    finally:
        for storage in (reader, competitor, writer):
            storage.conn.close()


def crash_writer(path):
    storage = VibeStorage(path, journal_mode="wal")
    storage.conn.execute("PRAGMA wal_autocheckpoint=0")
    storage.insert_atom(MemoryAtom(id="committed", agent_id="test", session_id="s",
                                  content="事务提交修复", summary="事务提交修复"))
    storage.conn.execute("BEGIN IMMEDIATE")
    storage.conn.execute("UPDATE atoms SET content=?, summary=? WHERE id=?",
                         ("未提交损坏", "未提交损坏", "committed"))
    print("READY", flush=True)
    # Parent kills this process only after the commit and pending update exist.
    sys.stdin.read()
    storage.conn.rollback()
    storage.conn.close()


def validate_crash(path):
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child", path],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            ready = pool.submit(process.stdout.readline).result(timeout=15).strip()
            if ready != "READY":
                raise RuntimeError("Crash child failed before readiness: " + process.stderr.read())
            process.kill()
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            for pipe in (process.stdin, process.stdout, process.stderr):
                pipe.close()
    wal_bytes = Path(path + "-wal").stat().st_size
    memory = VibeMemory("test", path, embedding_backend="tfidf")
    try:
        atom = memory.storage.get_atom("committed")
        preserved = atom is not None and atom.content == "事务提交修复"
        discarded = atom is not None and atom.summary != "未提交损坏" and atom.content != "未提交损坏"
        integrity = memory.storage.conn.execute("PRAGMA integrity_check").fetchone()[0]
        for table in ("atoms_fts", "atoms_trigram"):
            memory.storage.conn.execute(f"INSERT INTO {table}({table}, rank) VALUES ('integrity-check', 1)")
        memory.storage.conn.rollback()
        recalled = any(atom.id == "committed" and atom.content == "事务提交修复"
                       for atom in memory.recall("事务提交修复")["atoms"])
        return {"child_killed": process.returncode != 0, "wal_bytes_before_reopen": wal_bytes,
                "committed_preserved": preserved, "uncommitted_discarded": discarded,
                "committed_recalled": recalled, "integrity_check": integrity,
                "fts_external_content_integrity": "ok"}
    finally:
        memory.storage.conn.close()


def run():
    directory = Path(tempfile.mkdtemp(prefix="vibe-wal-recovery-"))
    return {"dataset_version": "wal-recovery-v1", "sqlite_version": sqlite3.sqlite_version,
            "transactions": validate_transactions(str(directory / "transactions.db")),
            "crash": validate_crash(str(directory / "crash.db")),
            "notes": "Fresh local temp DBs retained; held transactions not duration benchmarks; "
                     "process termination after acknowledged commit, not power loss or torn I/O; "
                     "busy_timeout=0 and wal_autocheckpoint=0 only in test-owned connections"}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        crash_writer(sys.argv[2])
    else:
        report = run()
        print(json.dumps(report, indent=2))
        tx, crash = report["transactions"], report["crash"]
        passed = all(tx[key] for key in ("uncommitted_hidden", "competing_writer_blocked",
                     "snapshot_retained", "committed_visible_after_snapshot"))
        passed = passed and tx["checkpoint_pinned"][0] == 1 and tx["checkpoint_released"] == [0, 0, 0]
        passed = passed and all(crash[key] for key in ("child_killed", "committed_preserved",
                     "uncommitted_discarded", "committed_recalled"))
        passed = passed and crash["wal_bytes_before_reopen"] > 0 and crash["integrity_check"] == "ok"
        sys.exit(0 if passed else 1)
