import sqlite3
import time

import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage


def test_recall_returns_quickly_under_write_lock_and_reinforces_after_release(tmp_path):
    path = str(tmp_path / "memory.db")
    holder = VibeStorage(path, journal_mode="wal")
    holder.insert_atom(MemoryAtom(id="anchor", agent_id="test", session_id="s",
                                 content="连接池超时修复", summary="连接池超时修复"))
    memory = VibeMemory("test", path, embedding_backend="tfidf")
    try:
        before = memory.storage.get_atom("anchor").access_count
        holder.conn.execute("BEGIN IMMEDIATE")
        start = time.perf_counter()
        result = memory.recall("连接池超时修复", mode="budget", top_k=5)
        assert result["reinforcement_skipped"] is True
        assert time.perf_counter() - start < 1
        assert any(atom.id == "anchor" and atom.access_count == before for atom in result["atoms"])
        assert memory.storage.get_atom("anchor").access_count == before
        assert not memory.storage.conn.in_transaction
        assert memory.storage.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        holder.conn.rollback()
        assert memory.recall("连接池超时修复", mode="budget", top_k=5)["reinforcement_skipped"] is False
        assert memory.storage.get_atom("anchor").access_count > before
    finally:
        holder.conn.close()
        memory.storage.conn.close()


def test_recall_does_not_hide_non_lock_database_errors():
    memory = VibeMemory("test", embedding_backend="tfidf")
    memory.store("连接池超时修复", session_id="s")
    try:
        memory.storage.conn.execute("PRAGMA query_only=ON")
        with pytest.raises(sqlite3.OperationalError) as failure:
            memory.recall("连接池超时修复", mode="budget", top_k=5)
        assert failure.value.sqlite_errorcode == sqlite3.SQLITE_READONLY
        assert memory.storage.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        memory.storage.conn.close()


def test_recall_preserves_callers_open_transaction():
    memory = VibeMemory("test", embedding_backend="tfidf")
    atom = memory.store("连接池超时修复", session_id="s")
    try:
        memory.storage.conn.execute("BEGIN")
        memory.storage.conn.execute("UPDATE atoms SET summary=? WHERE id=?", ("待提交备注", atom.id))
        result = memory.recall("连接池超时修复")
        assert result["reinforcement_skipped"] is True
        assert any(item.id == atom.id for item in result["atoms"])
        assert memory.storage.conn.in_transaction
        assert memory.storage.get_atom(atom.id).summary == "待提交备注"
        memory.storage.conn.rollback()
        assert memory.storage.get_atom(atom.id).summary != "待提交备注"
    finally:
        memory.storage.conn.close()
