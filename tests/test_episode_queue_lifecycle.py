import sqlite3

import pytest

from vibe_memory.models.memory_atom import MemoryAtom, Episode, Edge, EdgeLabel
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.edges.edge_builder import merge_atoms
from vibe_memory.indexer import IncrementalIndexer


@pytest.fixture
def store():
    storage = VibeStorage(":memory:")
    for name in ("a", "b", "x", "y"):
        storage.insert_atom(MemoryAtom(id=name, agent_id="agent", session_id=name, content=name, summary=name))
    yield storage
    storage.conn.close()


def episode(store, eid, members):
    store.insert_episode(Episode(id=eid, agent_id="agent", session_id="same", summary="old summary", topic="topic", atom_ids=members))
    for member in members:
        atom = store.get_atom(member)
        atom.episode_id = eid
        store.update_atom(atom)


def test_delete_invalidates_affected_episode_and_survivor_pointers(store):
    episode(store, "affected", ["a", "b"])
    episode(store, "unrelated", ["x", "y"])
    store.delete_atom("a")
    assert [ep.id for ep in store.get_episodes_by_session("same")] == ["unrelated"]
    assert store.get_atom("b").episode_id is None
    assert store.get_atom("x").episode_id == "unrelated"


def test_merge_invalidates_both_parent_episodes(store):
    episode(store, "first", ["a", "x"])
    episode(store, "second", ["b", "y"])
    merged = merge_atoms(store.get_atom("a"), store.get_atom("b"))
    store.merge_atoms(merged, "a", "b")
    assert store.get_episodes_by_session("same") == []
    assert store.get_atom("x").episode_id is store.get_atom("y").episode_id is None


def test_failed_delete_restores_episode_and_pointers(store):
    episode(store, "restore", ["a", "b"])
    store.conn.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON atoms BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.delete_atom("a")
    assert store.get_episodes_by_session("same")[0].id == "restore"
    assert store.get_atom("b").episode_id == "restore"


def test_failed_merge_restores_episode_and_pointers(store):
    episode(store, "restore", ["a", "x"])
    store.conn.execute("CREATE TRIGGER fail_merge BEFORE DELETE ON atoms BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
    merged = merge_atoms(store.get_atom("a"), store.get_atom("b"))
    with pytest.raises(sqlite3.IntegrityError):
        store.merge_atoms(merged, "a", "b")
    assert store.get_episodes_by_session("same")[0].id == "restore"
    assert store.get_atom("x").episode_id == "restore"
    assert store.get_atom(merged.id) is None


def test_episode_invalidation_does_not_touch_other_owner(store):
    episode(store, "owned", ["a", "b"])
    store.insert_episode(Episode(id="foreign", tenant_id="foreign", agent_id="other", session_id="same", summary="keep", topic="topic", atom_ids=["x"]))
    store.delete_atom("a")
    assert [ep.id for ep in store.get_episodes_by_session("same")] == ["foreign"]


def indexer(store, callback=None):
    return IncrementalIndexer(store, "agent", batch_size=1, llm_classify=callback)


@pytest.mark.parametrize("mutation", ["delete", "merge", "foreign"])
def test_stale_or_foreign_queue_endpoint_never_creates_edge(store, mutation):
    called = []
    idx = indexer(store, lambda *args: (called.append(args) or (EdgeLabel.SIMILAR, 0.9)))
    idx.enqueue(store.get_atom("a"), store.get_atom("x"), 0.9)
    if mutation == "delete":
        store.delete_atom("a")
    elif mutation == "merge":
        store.merge_atoms(merge_atoms(store.get_atom("a"), store.get_atom("b")), "a", "b")
    else:
        store.conn.execute("UPDATE atoms SET agent_id='foreign' WHERE id='a'")
        store.conn.commit()
    assert idx.flush_all() == 0
    assert called == []
    assert store.conn.execute("SELECT count(*) FROM edges").fetchone()[0] == 0
    assert idx.stats()["queue_size"] == 0


def test_classifier_uses_live_not_queued_content(store):
    seen = []
    idx = indexer(store, lambda a, b: (seen.append(a.content) or (EdgeLabel.SIMILAR, 0.9)))
    idx.enqueue(store.get_atom("a"), store.get_atom("b"), 0.9)
    current = store.get_atom("a")
    current.content = "updated"
    store.update_atom(current)
    assert idx.flush_all() == 1
    assert seen == ["updated"]


def test_callback_deletion_cannot_resurrect_edge(store):
    def classify(a, b):
        store.delete_atom(a.id)
        return EdgeLabel.SIMILAR, 0.9
    idx = indexer(store, classify)
    idx.enqueue(store.get_atom("a"), store.get_atom("b"), 0.9)
    assert idx.flush_all() == 0
    assert store.conn.execute("SELECT count(*) FROM edges").fetchone()[0] == 0


def test_callback_update_does_not_persist_obsolete_classification(store):
    def classify(a, b):
        current = store.get_atom(a.id)
        current.content = "changed during classification"
        store.update_atom(current)
        return EdgeLabel.SIMILAR, 0.9
    idx = indexer(store, classify)
    idx.enqueue(store.get_atom("a"), store.get_atom("b"), 0.9)
    assert idx.flush_all() == 0
    assert store.conn.execute("SELECT count(*) FROM edges").fetchone()[0] == 0


def test_zero_edge_batch_does_not_stop_flush_all(store):
    idx = indexer(store, lambda a, b: (EdgeLabel.SIMILAR, 0.1 if a.id == "a" else 0.9))
    idx.enqueue(store.get_atom("a"), store.get_atom("x"), 0.9)
    idx.enqueue(store.get_atom("b"), store.get_atom("y"), 0.8)
    assert idx.flush_all() == 1
    assert idx.stats()["processed_count"] == 2 and idx.stats()["queue_size"] == 0


def test_low_score_does_not_evict_full_queue(store):
    idx = indexer(store)
    idx.max_queue_size = 1
    idx.enqueue(store.get_atom("a"), store.get_atom("b"), 0.9)
    key = next(iter(idx._queue))
    assert not idx.enqueue(store.get_atom("x"), store.get_atom("y"), 0.1)
    assert list(idx._queue) == [key]


def test_atomic_edge_insert_rejects_changed_endpoint(store):
    first, second = store.get_atom("a"), store.get_atom("b")
    edge = Edge(id="guarded", from_atom_id="a", to_atom_id="b", label=EdgeLabel.SIMILAR)
    changed = store.get_atom("a")
    changed.content = "changed before final transaction"
    store.update_atom(changed)
    assert not store.insert_edge_if_current(edge, first, second)
    assert store.get_edge("guarded") is None
    assert not store.conn.in_transaction
    assert store.insert_edge_if_current(edge, changed, second)


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_batch_limit_is_rejected(store, limit):
    idx = indexer(store)
    with pytest.raises(ValueError):
        idx.flush(max_batch=limit)
