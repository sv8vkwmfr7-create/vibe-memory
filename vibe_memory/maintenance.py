"""Explicit, process-local WAL maintenance; never starts a background thread."""
import sqlite3
import math
import threading
from contextlib import contextmanager, nullcontext
from functools import wraps
from pathlib import Path
from time import perf_counter


def is_sqlite_lock_error(error: sqlite3.OperationalError) -> bool:
    """Prefer primary SQLite codes; Python 3.10 lacks code attributes/constants."""
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        return code & 0xFF in (5, 6)  # SQLITE_BUSY / SQLITE_LOCKED, including extended codes.
    return str(error).partition(":")[0] in {
        "database is locked", "database table is locked", "database schema is locked",
    }


class WALMaintenance:
    """Share one controller among all SDK instances using the same file."""

    def __init__(self, db_path: str):
        if not db_path or db_path == ":memory:" or str(db_path).startswith("file:"):
            raise ValueError("WAL maintenance requires an ordinary file path")
        self.db_path = Path(db_path).resolve()
        self._condition = threading.Condition()
        self._local = threading.local()
        self._active = 0
        self._paused = False

    def validate_path(self, db_path: str) -> None:
        if db_path == ":memory:" or Path(db_path).resolve() != self.db_path:
            raise ValueError("SDK and maintenance controller must use the same database file")

    @contextmanager
    def operation(self):
        """Include an entire caller-managed transaction or compound operation."""
        depth = getattr(self._local, "depth", 0)
        if depth == 0:
            with self._condition:
                self._condition.wait_for(lambda: not self._paused)
                self._active += 1
        self._local.depth = depth + 1
        try:
            yield
        finally:
            self._local.depth = depth
            if depth == 0:
                with self._condition:
                    self._active -= 1
                    self._condition.notify_all()

    def checkpoint(self, *, drain_timeout: float = 1.0) -> dict:
        """Drain admitted operations, then TRUNCATE without waiting for external locks.

        drain_timeout limits draining, not SQLite I/O or total request pause.
        Never call from inside operation(); this would wait on the caller itself.
        """
        if not math.isfinite(drain_timeout) or drain_timeout < 0:
            raise ValueError("drain_timeout must be finite and non-negative")
        if getattr(self._local, "depth", 0):
            raise RuntimeError("Cannot checkpoint inside an admitted operation")
        start = perf_counter()
        with self._condition:
            if self._paused:
                return self._report("maintenance_busy", start)
            self._paused = True
        try:
            with self._condition:
                if not self._condition.wait_for(lambda: self._active == 0, timeout=drain_timeout):
                    return self._report("drain_timeout", start)
            conn = sqlite3.connect(self.db_path.as_uri() + "?mode=rw", uri=True, timeout=0)
            try:
                if conn.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                    raise ValueError("WAL maintenance requires an existing WAL database")
                result = list(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
                return self._report("truncated" if result[0] == 0 else "busy", start, result)
            finally:
                conn.close()
        except sqlite3.OperationalError as error:
            if not is_sqlite_lock_error(error):
                raise
            return self._report("busy", start)
        finally:
            with self._condition:
                self._paused = False
                self._condition.notify_all()

    def _report(self, status, start, checkpoint=None):
        wal = Path(str(self.db_path) + "-wal")
        return {"status": status, "checkpoint": checkpoint,
                "wal_bytes_after": wal.stat().st_size if wal.exists() else 0,
                "elapsed_ms": round((perf_counter() - start) * 1000, 3)}


def coordinated(method):
    """Admit operations before serializing a shared SDK connection."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        maintenance = self.wal_maintenance
        with maintenance.operation() if maintenance is not None else nullcontext():
            with self._operation_lock:
                if self._closed:
                    raise RuntimeError("VibeMemory is closed")
                return method(self, *args, **kwargs)
    return wrapped
