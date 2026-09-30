import sqlite3
from datetime import datetime

import pytest

from vibe_memory import VibeMemory
from vibe_memory.edges.edge_builder import merge_atoms
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel, EdgeStatus
from vibe_memory.storage.sqlite_store import VibeStorage


@pytest.fixture
def storage():
    store = VibeStorage(":memory:", tenant_id="t")
    for name in ("a", "b", "x", "y"):
        store.insert_atom(MemoryAtom(id=name, agent_id="agent", session_id=name, tenant_id="t", content=name, summary=name))
    yield store
    store.conn.close()


def edge(store, eid, source, target, **kwargs):
    result = Edge(id=eid, from_atom_id=source, to_atom_id=target, tenant_id="t", label=EdgeLabel.CAUSAL, **kwargs)
    store.insert_edge(result)
    return result


@pytest.mark.parametrize("foreign_keys", [False, True])
def test_delete_removes_all_incident_edges_only(storage, foreign_keys):
    edge(storage, "incoming", "x", "a", status=EdgeStatus.PENDING_REVIEW)
    edge(storage, "outgoing", "a", "b", status=EdgeStatus.STALE)
    edge(storage, "unrelated", "x", "y")
    storage.conn.execute(f"PRAGMA foreign_keys={int(foreign_keys)}")
    storage.delete_atom("a")
    assert storage.get_atom("a") is None
    assert [r[0] for r in storage.conn.execute("SELECT id FROM edges")] == ["unrelated"]


def test_delete_rolls_back_edges_when_atom_delete_fails(storage):
    edge(storage, "keep", "a", "x")
    storage.conn.execute("CREATE TRIGGER deny_delete BEFORE DELETE ON atoms BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        storage.delete_atom("a")
    assert storage.get_atom("a") and storage.get_edge("keep")
    assert not storage.conn.in_transaction


def replacement(store):
    return merge_atoms(store.get_atom("a"), store.get_atom("b"))


def test_merge_rewires_both_directions_and_preserves_metadata(storage):
    storage.conn.execute("PRAGMA foreign_keys=ON")
    original = edge(storage, "old", "a", "x", weight=0.3, created_at=datetime(2020, 1, 1), status=EdgeStatus.STALE)
    edge(storage, "in", "y", "b")
    edge(storage, "internal", "a", "b")
    merged = replacement(storage)
    storage.merge_atoms(merged, "a", "b")
    assert storage.get_atom(merged.id)
    assert storage.get_atom("a") is storage.get_atom("b") is None
    migrated = storage.get_edge("old")
    assert migrated.from_atom_id == merged.id and migrated.to_atom_id == "x"
    assert (migrated.weight, migrated.created_at, migrated.status) == (original.weight, original.created_at, original.status)
    assert storage.get_edge("in").to_atom_id == merged.id
    assert storage.get_edge("internal") is None
    assert not storage.conn.execute("PRAGMA foreign_key_check").fetchall()


def test_merge_duplicate_pairs_keep_oldest_edge(storage):
    edge(storage, "first", "a", "x", created_at=datetime(2020, 1, 1), weight=0.2)
    edge(storage, "second", "b", "x", created_at=datetime(2021, 1, 1), weight=0.8)
    merged = replacement(storage)
    storage.merge_atoms(merged, "a", "b")
    assert storage.get_edge("first").weight == 0.2
    assert storage.get_edge("second") is None


def test_merge_conflicting_labels_preserves_originals(storage):
    edge(storage, "one", "a", "x")
    storage.insert_edge(Edge(id="two", from_atom_id="b", to_atom_id="x", tenant_id="t", label=EdgeLabel.REVISION))
    merged = replacement(storage)
    with pytest.raises(ValueError):
        storage.merge_atoms(merged, "a", "b")
    assert storage.get_atom("a") and storage.get_atom("b")
    assert storage.get_atom(merged.id) is None
    assert storage.get_edge("one") and storage.get_edge("two")


def test_merge_rollback_restores_every_row(storage):
    edge(storage, "keep", "a", "x")
    storage.conn.execute("CREATE TRIGGER deny_merge BEFORE DELETE ON atoms BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    merged = replacement(storage)
    with pytest.raises(sqlite3.IntegrityError):
        storage.merge_atoms(merged, "a", "b")
    assert storage.get_atom("a") and storage.get_atom("b")
    assert storage.get_atom(merged.id) is None
    assert storage.get_edge("keep").from_atom_id == "a"
    assert not storage.conn.in_transaction


def test_sdk_auto_merge_returns_existing_result_and_keeps_relations(monkeypatch):
    mem = VibeMemory(agent_id="agent", tenant_id="t", embedding_backend="tfidf")
    try:
        previous = mem.store("first", auto_build_edges=False, auto_episode=False)
        neighbor = mem.store("neighbor", auto_build_edges=False, auto_episode=False)
        mem.link(previous.id, neighbor.id)
        monkeypatch.setattr("vibe_memory.sdk.build_cross_session_candidates", lambda *args, **kwargs: {"duplicate": [previous], "similar": []})
        result = mem.store("second", auto_episode=False)
        assert mem.storage.get_atom(result.id) is not None
        assert mem.storage.get_atom(previous.id) is None
        assert mem.storage.get_outgoing_edges(result.id)[0].to_atom_id == neighbor.id
    finally:
        mem.storage.conn.close()


@pytest.mark.parametrize("field,value", [("tenant_id", "foreign"), ("agent_id", "foreign"), ("scope", {"service": "other"})])
def test_merge_rejects_foreign_or_incompatible_parent(storage, field, value):
    merged = replacement(storage)
    if field == "scope":
        parent = storage.get_atom("b")
        parent.scope = value
        storage.update_atom(parent)
    else:
        storage.conn.execute(f"UPDATE atoms SET {field}=? WHERE id='b'", (value,))
        storage.conn.commit()
    with pytest.raises(ValueError):
        storage.merge_atoms(merged, "a", "b")
    assert storage.get_atom("a") and storage.get_atom("b")
    assert storage.get_atom(merged.id) is None


@pytest.mark.parametrize("operation", ["delete", "merge"])
def test_operations_do_not_commit_or_rollback_callers_transaction(storage, operation):
    merged = replacement(storage)
    storage.conn.execute("UPDATE atoms SET summary='pending' WHERE id='x'")
    with pytest.raises(ValueError):
        storage.delete_atom("a") if operation == "delete" else storage.merge_atoms(merged, "a", "b")
    assert storage.conn.in_transaction
    assert storage.get_atom("x").summary == "pending"
    storage.conn.rollback()
    assert storage.get_atom("x").summary == "x"


def test_merge_malformed_incident_edge_is_not_rewired(storage):
    edge(storage, "broken", "a", "missing")
    merged = replacement(storage)
    with pytest.raises(ValueError):
        storage.merge_atoms(merged, "a", "b")
    assert storage.get_edge("broken").from_atom_id == "a"
    assert storage.get_atom("a") and storage.get_atom("b")


def test_sdk_conflict_skips_merge_without_losing_relations(monkeypatch):
    mem = VibeMemory(agent_id="agent", tenant_id="t", embedding_backend="tfidf")
    try:
        previous = mem.store("first", auto_build_edges=False, auto_episode=False)
        neighbor = mem.store("neighbor", auto_build_edges=False, auto_episode=False)
        mem.link(previous.id, neighbor.id, label=EdgeLabel.CAUSAL)
        def candidates(new_atom, *args, **kwargs):
            mem.link(new_atom.id, neighbor.id, label=EdgeLabel.REVISION)
            return {"duplicate": [previous], "similar": []}
        monkeypatch.setattr("vibe_memory.sdk.build_cross_session_candidates", candidates)
        result = mem.store("second", auto_episode=False)
        assert mem.storage.get_atom(result.id) and mem.storage.get_atom(previous.id)
        assert len(mem.storage.get_edges_by_agent("agent")) == 2
    finally:
        mem.storage.conn.close()
