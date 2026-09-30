import sqlite3
import sys

import pytest

from vibe_memory.maintenance import is_sqlite_lock_error


def test_real_sqlite_busy_and_readonly_classification_on_current_runtime(tmp_path):
    path = str(tmp_path / "runtime.db")
    holder = sqlite3.connect(path, timeout=0)
    contender = sqlite3.connect(path, timeout=0)
    try:
        holder.execute("CREATE TABLE marker (value)")
        holder.commit()
        holder.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError) as busy:
            contender.execute("INSERT INTO marker VALUES (1)")
        assert is_sqlite_lock_error(busy.value)
        if sys.version_info < (3, 11):
            assert not hasattr(busy.value, "sqlite_errorcode")
            assert not hasattr(sqlite3, "SQLITE_BUSY")
        else:
            assert busy.value.sqlite_errorcode & 0xFF == sqlite3.SQLITE_BUSY
        contender.rollback()
        holder.rollback()
        contender.execute("PRAGMA query_only=ON")
        with pytest.raises(sqlite3.OperationalError) as readonly:
            contender.execute("INSERT INTO marker VALUES (2)")
        assert "readonly" in str(readonly.value).lower()
        assert not is_sqlite_lock_error(readonly.value)
        if sys.version_info < (3, 11):
            assert not hasattr(readonly.value, "sqlite_errorcode")
        else:
            assert readonly.value.sqlite_errorcode == sqlite3.SQLITE_READONLY
    finally:
        holder.close()
        contender.close()
