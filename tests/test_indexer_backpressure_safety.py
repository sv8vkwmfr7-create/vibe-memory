import pytest

from vibe_memory.indexer import IncrementalIndexer, BackpressureStrategy
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage


@pytest.fixture
def store():
    storage = VibeStorage(":memory:")
    yield storage
    storage.conn.close()


def atom(name):
    return MemoryAtom(id=name, agent_id="agent", session_id=name, content=name, summary=name)


@pytest.mark.parametrize("strategy", [BackpressureStrategy.DROP_OLDEST, BackpressureStrategy.DROP_LOWEST])
def test_successful_replacement_reports_acceptance_and_one_drop(store, strategy):
    idx = IncrementalIndexer(store, "agent", max_queue_size=1, backpressure=strategy)
    a, b, c = atom("a"), atom("b"), atom("c")
    assert idx.enqueue(a, b, 0.8)
    assert idx.enqueue(a, c, 0.9)
    stats = idx.stats()
    assert (stats["queue_size"], stats["enqueued_count"], stats["dropped_count"]) == (1, 2, 1)
    assert next(iter(idx._queue.values())).existing_atom.id == "c"


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_invalid_capacity_is_rejected(store, capacity):
    with pytest.raises(ValueError):
        IncrementalIndexer(store, "agent", max_queue_size=capacity)


def test_unknown_strategy_is_rejected(store):
    with pytest.raises(ValueError):
        IncrementalIndexer(store, "agent", backpressure="typo")


@pytest.mark.parametrize("strategy, score", [(BackpressureStrategy.DROP_LOWEST, 0.8), (BackpressureStrategy.DROP_LOWEST, 0.9), (BackpressureStrategy.BLOCK, 1.0)])
def test_rejected_full_queue_offer_counts_one_loss_without_acceptance(store, strategy, score):
    idx = IncrementalIndexer(store, "agent", max_queue_size=1, backpressure=strategy)
    a, b, c = atom("a"), atom("b"), atom("c")
    assert idx.enqueue(a, b, 0.9)
    assert not idx.enqueue(a, c, score)
    stats = idx.stats()
    assert (stats["enqueued_count"], stats["dropped_count"], stats["queue_size"]) == (1, 1, 1)
    assert next(iter(idx._queue.values())).existing_atom.id == "b"


def test_duplicate_and_below_threshold_do_not_evict_or_change_counts(store):
    idx = IncrementalIndexer(store, "agent", max_queue_size=1)
    a, b, c = atom("a"), atom("b"), atom("c")
    idx.enqueue(a, b, 0.8)
    assert idx.enqueue(b, a, 0.9)
    assert not idx.enqueue(a, c, 0.1)
    stats = idx.stats()
    assert (stats["enqueued_count"], stats["dropped_count"], stats["queue_size"]) == (1, 0, 1)
    assert next(iter(idx._queue.values())).similarity == 0.9


def test_batch_counts_replacement_admissions(store, monkeypatch):
    import vibe_memory.indexer as indexer_module
    idx = IncrementalIndexer(store, "agent", max_queue_size=1)
    a, b, c, d = (atom(name) for name in "abcd")
    for item in (a, b, c, d):
        item.tags = ["topic"]
    idx.enqueue(a, b, 0.8)
    monkeypatch.setattr(indexer_module, "build_cross_session_candidates", lambda *args, **kwargs: {"similar": [c, d]})
    assert idx.enqueue_batch(a, [c, d]) == 2
    stats = idx.stats()
    assert (stats["enqueued_count"], stats["dropped_count"], stats["queue_size"]) == (3, 2, 1)


def test_accounting_after_replacement_rejection_consumption_clear_and_reset(store):
    idx = IncrementalIndexer(store, "agent", max_queue_size=2, backpressure=BackpressureStrategy.DROP_LOWEST)
    a, b, c, d, e = (atom(name) for name in "abcde")
    # Endpoints need not be present: flush consumes stale work without creating an edge.
    idx.enqueue(a, b, 0.8)
    idx.enqueue(a, c, 0.9)
    assert idx.enqueue(a, d, 1.0)
    assert not idx.enqueue(a, e, 0.7)
    assert idx.flush(max_batch=1) == 0
    assert idx.clear_queue() == 1
    stats = idx.stats()
    assert (stats["enqueued_count"], stats["processed_count"], stats["dropped_count"], stats["queue_size"]) == (3, 1, 3, 0)
    # dropped includes one never-admitted full-queue offer, not only dequeued work.
    assert stats["enqueued_count"] + 1 == stats["processed_count"] + stats["dropped_count"] + stats["queue_size"]
    idx.reset()
    stats = idx.stats()
    assert all(stats[key] == 0 for key in ("enqueued_count", "processed_count", "dropped_count", "queue_size"))


def test_compaction_counts_each_removed_candidate_once(store):
    idx = IncrementalIndexer(store, "agent")
    a, b, c = atom("a"), atom("b"), atom("c")
    idx.enqueue(a, c, 0.8)
    idx.enqueue(b, c, 0.9)
    assert idx.compact_queue() == 1
    assert idx.compact_queue() == 0
    stats = idx.stats()
    assert (stats["enqueued_count"], stats["dropped_count"], stats["queue_size"]) == (2, 1, 1)
