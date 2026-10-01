import math
import sqlite3

import pytest

from vibe_memory import VibeMemory, WALMaintenance
from vibe_memory.learner.learner import VibeLearner
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.maintenance import is_sqlite_lock_error


@pytest.mark.parametrize("score", [-10000, -1000, -2, 0, 2, 1000, 10000])
def test_decay_sigmoid_stays_bounded_and_matches_normal_scores(score):
    learner = VibeLearner()
    learner.weights["bias"] = score
    atom = MemoryAtom(id="a", agent_id="agent", session_id="s", content="text", summary="text")
    rate = learner.predict_decay_rate(atom)
    assert math.isfinite(rate)
    assert learner.cfg.min_decay_rate <= rate <= learner.cfg.max_decay_rate
    if abs(score) <= 2:
        expected = learner.cfg.min_decay_rate + (learner.cfg.max_decay_rate - learner.cfg.min_decay_rate) / (1 + math.exp(-score))
        assert rate == pytest.approx(expected)
    elif score < 0:
        assert rate == learner.cfg.min_decay_rate
    else:
        assert rate == learner.cfg.max_decay_rate


@pytest.mark.parametrize("message", ["database is locked", "database table is locked: atoms", "database schema is locked: main"])
def test_recall_skips_legacy_lock_error_and_restores_timeout(monkeypatch, message):
    memory = VibeMemory("agent", embedding_backend="tfidf")
    atom = memory.store("连接池使用二十个连接", auto_build_edges=False, auto_episode=False)
    error = sqlite3.OperationalError(message)
    assert not hasattr(error, "sqlite_errorcode")
    try:
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr(memory.storage, "reinforce_atoms", fail)
        result = memory.recall("连接池")
        assert result["reinforcement_skipped"]
        assert any(item.id == atom.id for item in result["atoms"])
        assert memory.storage.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert not memory.storage.conn.in_transaction
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize("message", ["attempt to write a readonly database", "no such table: atoms", "disk I/O error"])
def test_legacy_non_lock_errors_are_not_hidden(monkeypatch, message):
    memory = VibeMemory("agent", embedding_backend="tfidf")
    memory.store("连接池使用二十个连接", auto_build_edges=False, auto_episode=False)
    error = sqlite3.OperationalError(message)
    try:
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr(memory.storage, "reinforce_atoms", fail)
        with pytest.raises(sqlite3.OperationalError) as failure:
            memory.recall("连接池")
        assert failure.value is error
        assert memory.storage.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        memory.storage.conn.close()


def test_checkpoint_handles_legacy_lock_errors_and_recovers_admission(tmp_path, monkeypatch):
    maintenance = WALMaintenance(str(tmp_path / "memory.db"))
    error = sqlite3.OperationalError("database is locked")
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(sqlite3, "connect", fail)
    monkeypatch.delattr(sqlite3, "SQLITE_BUSY", raising=False)
    monkeypatch.delattr(sqlite3, "SQLITE_LOCKED", raising=False)
    assert maintenance.checkpoint()["status"] == "busy"
    assert maintenance._paused is False
    with maintenance.operation():
        assert maintenance._active == 1


@pytest.mark.parametrize("code,expected", [(5, True), (6, True), (517, True), (262, True), (1, False), (8, False)])
def test_numeric_error_codes_take_priority_over_message(code, expected):
    error = sqlite3.OperationalError("database is locked" if not expected else "unrelated text")
    error.sqlite_errorcode = code
    assert is_sqlite_lock_error(error) is expected


@pytest.mark.parametrize("message", ["no such table: atoms", "disk I/O error", "database is lockedness"])
def test_checkpoint_does_not_hide_other_legacy_errors(tmp_path, monkeypatch, message):
    maintenance = WALMaintenance(str(tmp_path / "memory.db"))
    error = sqlite3.OperationalError(message)
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(sqlite3, "connect", fail)
    with pytest.raises(sqlite3.OperationalError) as failure:
        maintenance.checkpoint()
    assert failure.value is error
    assert maintenance._paused is False
