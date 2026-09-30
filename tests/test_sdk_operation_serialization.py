import sqlite3
import threading
from time import monotonic
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import pytest

from vibe_memory import VibeMemory
from vibe_memory.maintenance import WALMaintenance


@pytest.mark.parametrize("with_maintenance", [False, True])
def test_shared_sdk_write_does_not_use_recalls_temporary_zero_timeout(
        tmp_path, monkeypatch, with_maintenance):
    paused, release, writing = threading.Event(), threading.Event(), threading.Event()
    real_connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            cursor = super().execute(sql, *args, **kwargs)
            # Instrument the real database boundary after SQLite releases its mutex.
            if sql == "PRAGMA busy_timeout=0" and not paused.is_set():
                paused.set()
                assert release.wait(5)
            return cursor

    def connect(*args, **kwargs):
        return real_connect(*args, factory=ObservedConnection, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)
    path = str(tmp_path / "shared.db")
    maintenance = WALMaintenance(path) if with_maintenance else None
    memory = VibeMemory("test", path, embedding_backend="tfidf", journal_mode="wal",
                        wal_maintenance=maintenance)
    holder = real_connect(path)
    original = memory.store("original timeout configuration", auto_build_edges=False,
                            auto_episode=False)

    def store():
        writing.set()
        return memory.store("new timeout configuration", auto_build_edges=False,
                            auto_episode=False)

    try:
        holder.execute("BEGIN IMMEDIATE")
        with ThreadPoolExecutor(max_workers=2) as pool:
            recalling = pool.submit(memory.recall, "timeout configuration")
            try:
                assert paused.wait(3)
                storing = pool.submit(store)
                assert writing.wait(3)
                with pytest.raises(FutureTimeoutError):
                    storing.result(timeout=0.2)
            finally:
                holder.rollback()
                release.set()
            assert any(atom.id == original.id for atom in recalling.result(timeout=3)["atoms"])
            stored = storing.result(timeout=3)
        assert {atom.id for atom in memory.history()} == {original.id, stored.id}
        assert memory.storage.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        holder.close()
        memory.storage.conn.close()


def test_exception_releases_instance_lock_and_nested_inject_completes():
    memory = VibeMemory("test", embedding_backend="tfidf")
    try:
        memory.store("timeout recovery", auto_build_edges=False, auto_episode=False)
        memory.storage.conn.execute("PRAGMA query_only=ON")
        try:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                memory.recall("timeout recovery")
        finally:
            memory.storage.conn.execute("PRAGMA query_only=OFF")
        assert memory.storage.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        with ThreadPoolExecutor(max_workers=1) as pool:
            stored = pool.submit(memory.store, "recovered write", auto_build_edges=False,
                                 auto_episode=False).result(timeout=3)
            injection = pool.submit(memory.inject, "recovered write").result(timeout=3)
        assert stored.id in {atom.id for atom in memory.history()}
        assert injection
    finally:
        memory.storage.conn.close()


def test_admitted_nested_call_can_drain_while_new_call_waits_for_checkpoint(tmp_path):
    path = str(tmp_path / "gate-order.db")
    maintenance = WALMaintenance(path)
    memory = VibeMemory("test", path, embedding_backend="tfidf", journal_mode="wal",
                        wal_maintenance=maintenance)
    admitted, call_nested, newcomer_started = (threading.Event() for _ in range(3))

    def admitted_call():
        with maintenance.operation():
            admitted.set()
            assert call_nested.wait(5)
            return memory.history()

    def newcomer():
        newcomer_started.set()
        return memory.history()

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            draining = pool.submit(admitted_call)
            try:
                assert admitted.wait(3)
                checkpoint = pool.submit(maintenance.checkpoint, drain_timeout=3)
                deadline = monotonic() + 2
                while maintenance.checkpoint(drain_timeout=0)["status"] != "maintenance_busy":
                    assert monotonic() < deadline
                    threading.Event().wait(0.005)
                waiting = pool.submit(newcomer)
                assert newcomer_started.wait(3)
                with pytest.raises(FutureTimeoutError):
                    waiting.result(timeout=0.2)
            finally:
                call_nested.set()
            assert draining.result(timeout=1) == []
            assert checkpoint.result(timeout=3)["status"] == "truncated"
            assert waiting.result(timeout=3) == []
    finally:
        memory.storage.conn.close()
