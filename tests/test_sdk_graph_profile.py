"""Public graph-off profile uses real SDK/SQLite paths."""
import sqlite3

import pytest

from vibe_memory.sdk import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel


def test_graph_disabled_preserves_duplicates_and_skips_batch_edges(tmp_path):
    path = str(tmp_path / "simple.db")
    with VibeMemory("agent", db_path=path, embedding_backend="tfidf", graph_enabled=False) as memory:
        first = memory.store("Orders timeout is 60 seconds", session_id="one", tags=["orders"])
        second = memory.store("Orders timeout is 60 seconds", session_id="two", tags=["orders"])
        batch = memory.store_batch([
            {"role": "user", "content": "Help me fix API timeout"},
            {"role": "assistant", "content": "Looking at logs. Timeout is 30s, too short. Suggest 60s."},
            {"role": "user", "content": "OK, change it"},
            {"role": "assistant", "content": "Changed timeout from 30s to 60s. Restarting service."},
            {"role": "user", "content": "Test passed, all good"},
            {"role": "assistant", "content": "API timeout issue fixed."},
        ], session_id="batch")
        assert first.id != second.id
        assert memory.storage.get_atom(first.id) is not None
        assert memory.storage.get_atom(second.id) is not None
        assert len(batch) >= 2
        assert memory.storage.get_edges_by_agent("agent") == []
        assert memory.indexer.stats()["queue_size"] == 0
    with VibeMemory("agent", db_path=path, embedding_backend="tfidf", graph_enabled=False) as reopened:
        assert reopened.storage.get_atom(first.id).content == first.content
        assert reopened.storage.get_atom(second.id).content == second.content
        assert reopened.recall("Orders timeout", mode="budget")["failures"] == []


@pytest.mark.parametrize("mode", ["precision", "recall", "budget"])
@pytest.mark.parametrize("strict", [False, True])
def test_disabled_recall_ignores_existing_edges_and_keeps_strict_scope(mode, strict):
    with VibeMemory("agent", embedding_backend="tfidf", graph_enabled=False,
                    reinforcement_policy="confirmed_use") as memory:
        first = memory.store("Orders production timeout is 60 seconds", scope={"service": "orders"})
        second = memory.store("Orders export uses the production timeout", scope={"service": "orders"})
        memory.store("Orders timeout example in a different project", scope={"service": "other"})
        memory.link(first.id, second.id, EdgeLabel.CAUSAL)
        edge_reads = []

        def authorize(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ and table == "edges":
                edge_reads.append(column)
            return sqlite3.SQLITE_OK

        memory.storage.conn.set_authorizer(authorize)
        try:
            result = memory.recall("Orders production timeout", mode=mode,
                                   scope={"service": "orders"}, strict_scope=strict)
        finally:
            memory.storage.conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
        assert result["failures"] == []
        assert result["atoms"]
        if strict:
            assert all(atom.scope == {"service": "orders"} for atom in result["atoms"])
        assert result["strategies_used"] == ["semantic", "bm25", "temporal"]
        assert result["trace"] == []
        assert edge_reads == []


def test_disabled_profile_rejects_causal_bridge():
    with VibeMemory("agent", embedding_backend="tfidf", graph_enabled=False) as memory:
        with pytest.raises(ValueError, match="graph_enabled"):
            memory.recall("Orders timeout", causal_bridge=True)


@pytest.mark.parametrize("value", [None, "false", 0])
def test_graph_flag_must_be_boolean_before_opening_database(tmp_path, value):
    path = tmp_path / "invalid.db"
    with pytest.raises(ValueError, match="graph_enabled"):
        VibeMemory("agent", db_path=str(path), embedding_backend="tfidf", graph_enabled=value)
    assert not path.exists()
