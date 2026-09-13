import threading
import sqlite3
import time
import pytest
from concurrent.futures import ThreadPoolExecutor

from vibe_memory import VibeMemory, WALMaintenance


def test_explicit_maintenance_truncates_without_losing_recall(tmp_path):
    path = str(tmp_path / "memory.db")
    maintenance = WALMaintenance(path)
    memory = VibeMemory("test", path, embedding_backend="tfidf",
                        journal_mode="wal", wal_maintenance=maintenance)
    try:
        atom = memory.store("连接池超时修复", session_id="s", auto_build_edges=False,
                            auto_episode=False)
        report = maintenance.checkpoint()
        assert report["status"] == "truncated"
        assert report["checkpoint"] == [0, 0, 0]
        assert report["wal_bytes_after"] == 0
        assert any(row.id == atom.id for row in memory.recall("连接池超时修复")["atoms"])
    finally:
        memory.storage.conn.close()


def test_sdk_recall_waits_for_maintenance_and_nested_inject_completes(tmp_path):
    path = str(tmp_path / "memory.db")
    maintenance = WALMaintenance(path)
    memory = VibeMemory("test", path, embedding_backend="tfidf",
                        journal_mode="wal", wal_maintenance=maintenance)
    atom = memory.store("连接池超时修复", auto_build_edges=False, auto_episode=False)
    holding, release = threading.Event(), threading.Event()

    def hold_operation():
        with maintenance.operation():
            holding.set()
            assert release.wait(5)

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            held = pool.submit(hold_operation)
            assert holding.wait(3)
            maintaining = pool.submit(maintenance.checkpoint, drain_timeout=2)
            try:
                deadline = time.monotonic() + 1
                while maintenance.checkpoint(drain_timeout=0)["status"] != "maintenance_busy":
                    assert time.monotonic() < deadline
                    time.sleep(0.001)
                recalling = pool.submit(memory.recall, "连接池超时修复")
                time.sleep(0.03)
                assert not recalling.done()
            finally:
                release.set()
                held.result(timeout=3)
            assert maintaining.result(timeout=3)["status"] == "truncated"
            assert any(row.id == atom.id for row in recalling.result(timeout=3)["atoms"])
        with maintenance.operation():
            assert isinstance(memory.inject("连接池超时修复"), str)
    finally:
        memory.storage.conn.close()


def test_maintenance_waits_for_sdk_write_already_in_progress(tmp_path):
    path = str(tmp_path / "memory.db")
    maintenance = WALMaintenance(path)
    memory = VibeMemory("test", path, embedding_backend="tfidf",
                        journal_mode="wal", wal_maintenance=maintenance)
    holder = sqlite3.connect(path)
    inserting = threading.Event()
    # SQLite's public trace signals entry into the real blocked write.
    memory.storage.conn.set_trace_callback(
        lambda sql: inserting.set() if sql.startswith("INSERT INTO atoms (") else None)
    try:
        holder.execute("BEGIN IMMEDIATE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(memory.store, "连接池超时修复", auto_build_edges=False,
                                 auto_episode=False)
            try:
                assert inserting.wait(3)
                assert maintenance.checkpoint(drain_timeout=0.01)["status"] == "drain_timeout"
            finally:
                holder.rollback()
                atom = future.result(timeout=5)
        assert any(row.id == atom.id for row in memory.history())
        assert maintenance.checkpoint()["status"] == "truncated"
    finally:
        holder.close()
        memory.storage.conn.close()


def test_busy_operation_times_out_and_admission_recovers(tmp_path):
    path = str(tmp_path / "memory.db")
    maintenance = WALMaintenance(path)
    memory = VibeMemory("test", path, embedding_backend="tfidf",
                        journal_mode="wal", wal_maintenance=maintenance)
    active, release = threading.Event(), threading.Event()

    def transaction():
        with maintenance.operation():
            active.set()
            assert release.wait(5)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(transaction)
            assert active.wait(5)
            try:
                assert maintenance.checkpoint(drain_timeout=0.01)["status"] == "drain_timeout"
                atom = memory.store("连接池超时修复", auto_build_edges=False, auto_episode=False)
                assert memory.history()[0].id == atom.id
            finally:
                release.set()
                future.result(timeout=5)
        assert maintenance.checkpoint()["status"] == "truncated"
    finally:
        memory.storage.conn.close()


def test_new_sdk_instance_waits_but_default_instance_does_not(tmp_path):
    path = str(tmp_path / "memory.db")
    maintenance = WALMaintenance(path)
    default = VibeMemory("test", path, embedding_backend="tfidf", journal_mode="wal")
    atom = default.store("连接池超时修复", auto_build_edges=False, auto_episode=False)
    holding, release = threading.Event(), threading.Event()

    def hold_operation():
        with maintenance.operation():
            holding.set()
            assert release.wait(5)

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            held = pool.submit(hold_operation)
            assert holding.wait(3)
            maintaining = pool.submit(maintenance.checkpoint, drain_timeout=2)
            try:
                deadline = time.monotonic() + 1
                while maintenance.checkpoint(drain_timeout=0)["status"] != "maintenance_busy":
                    assert time.monotonic() < deadline
                    time.sleep(0.001)
                creating = pool.submit(VibeMemory, "test", path, embedding_backend="tfidf",
                                       wal_maintenance=maintenance)
                time.sleep(0.25)
                assert not creating.done()
                assert default.history()[0].id == atom.id
            finally:
                release.set()
                held.result(timeout=3)
                created = creating.result(timeout=3)
                created.storage.conn.close()
            assert maintaining.result(timeout=3)["status"] == "truncated"
    finally:
        default.storage.conn.close()


def test_external_reader_keeps_snapshot_and_busy_does_not_block_later_sdk_calls(tmp_path):
    path = str(tmp_path / "memory.db")
    maintenance = WALMaintenance(path)
    memory = VibeMemory("test", path, embedding_backend="tfidf",
                        journal_mode="wal", wal_maintenance=maintenance)
    reader = sqlite3.connect(path)
    try:
        atom = memory.store("连接池超时修复", auto_build_edges=False, auto_episode=False)
        assert maintenance.checkpoint()["status"] == "truncated"
        reader.execute("BEGIN")
        assert reader.execute("SELECT content FROM atoms WHERE id=?", (atom.id,)).fetchone()[0] == "连接池超时修复"
        memory.update(atom.id, content="连接池超时修复 已更新")
        assert maintenance.checkpoint()["status"] == "busy"
        assert reader.in_transaction
        assert reader.execute("SELECT content FROM atoms WHERE id=?", (atom.id,)).fetchone()[0] == "连接池超时修复"
        assert memory.history()[0].content == "连接池超时修复 已更新"
        reader.rollback()
        assert maintenance.checkpoint()["status"] == "truncated"
    finally:
        reader.close()
        memory.storage.conn.close()


def test_invalid_database_and_maintenance_errors_restore_admission(tmp_path):
    path = str(tmp_path / "delete.db")
    maintenance = WALMaintenance(path)
    with pytest.raises(ValueError):
        VibeMemory("test", str(tmp_path / "other.db"), wal_maintenance=maintenance)
    assert not (tmp_path / "other.db").exists()
    memory = VibeMemory("test", path, embedding_backend="tfidf", wal_maintenance=maintenance)
    try:
        with pytest.raises(ValueError, match="WAL database"):
            maintenance.checkpoint()
        atom = memory.store("连接池超时修复", auto_build_edges=False, auto_episode=False)
        assert memory.history()[0].id == atom.id
        with maintenance.operation():
            with pytest.raises(RuntimeError, match="admitted operation"):
                maintenance.checkpoint()
            assert memory.history()[0].id == atom.id
    finally:
        memory.storage.conn.close()


def test_nonexistent_database_is_not_created_by_maintenance(tmp_path):
    path = tmp_path / "missing.db"
    maintenance = WALMaintenance(str(path))
    with pytest.raises(sqlite3.OperationalError):
        maintenance.checkpoint()
    assert not path.exists()
    with maintenance.operation():
        pass  # Errors must not leave admission permanently paused.


def test_external_exclusive_lock_is_reported_busy_and_recovers(tmp_path):
    path = str(tmp_path / "locked.db")
    maintenance = WALMaintenance(path)
    holder = sqlite3.connect(path)
    try:
        holder.execute("PRAGMA journal_mode=WAL")
        holder.execute("PRAGMA locking_mode=EXCLUSIVE")
        holder.execute("CREATE TABLE marker (value)")
        holder.execute("INSERT INTO marker VALUES (1)")
        holder.commit()
        assert maintenance.checkpoint()["status"] == "busy"
    finally:
        holder.close()
    assert maintenance.checkpoint()["status"] == "truncated"
