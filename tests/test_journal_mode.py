import pytest

from vibe_memory import VibeMemory
from vibe_memory.storage.sqlite_store import VibeStorage


def test_sdk_wal_reopen_preserves_memory_and_mode(tmp_path):
    path = str(tmp_path / "memory.db")
    memory = VibeMemory("journal-test", path, embedding_backend="tfidf", journal_mode="wal")
    memory.store("连接池超时修复", session_id="session")
    assert memory.storage.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    memory.storage.conn.close()
    reopened = VibeMemory("journal-test", path, embedding_backend="tfidf")
    try:
        assert reopened.storage.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert reopened.recall("连接池超时修复")
    finally:
        reopened.storage.conn.close()


def test_default_disk_and_explicit_delete(tmp_path):
    path = str(tmp_path / "memory.db")
    default = VibeStorage(path)
    assert default.conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    default.conn.close()
    wal = VibeStorage(path, journal_mode="wal")
    wal.conn.close()
    restored = VibeStorage(path, journal_mode="delete")
    assert restored.conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    restored.conn.close()


@pytest.mark.parametrize("mode", ["invalid", "WAL", "wal; DROP TABLE atoms", 123])
def test_invalid_mode_does_not_create_database(tmp_path, mode):
    path = tmp_path / "invalid.db"
    with pytest.raises(ValueError, match="journal_mode"):
        VibeStorage(str(path), journal_mode=mode)
    assert not path.exists()


def test_memory_default_works_and_wal_is_not_silently_downgraded():
    default = VibeStorage()
    assert default.conn.execute("PRAGMA journal_mode").fetchone()[0] == "memory"
    default.conn.close()
    with pytest.raises(ValueError, match="Cannot enable journal_mode"):
        VibeStorage(journal_mode="wal")
