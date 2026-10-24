"""
Incremental Indexer Tests (M3)

Verifies:
1. Enqueue: candidates added to queue with dedup
2. Dedup: same pair only queued once, highest similarity kept
3. Backpressure: queue full → drop oldest or lowest
4. Flush: batch processing creates edges
5. Flush all: processes entire queue
6. Auto flush: on_store triggers flush after threshold
7. Should flush: queue >= batch_size
8. Compact: merge candidates pointing to same atom
9. Clear: drop entire queue
10. Stats: correct counters
11. Empty flush: no-op on empty queue
12. SDK integration: indexer in stats(), flush_index() method
13. SDK store: auto-enqueue cross-session candidates
14. SDK auto flush: triggered after N stores
"""

from contextlib import ExitStack
import pytest
import uuid
from datetime import datetime

from vibe_memory.indexer import IncrementalIndexer, BackpressureStrategy
from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle, DEFAULT_TENANT,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.sdk import VibeMemory


# ── Helpers ──

def _make_atom(id: str, agent: str, session: str, tags: list[str] = None) -> MemoryAtom:
    return MemoryAtom(
        id=id, agent_id=agent, session_id=session,
        content=f"Content {id}", summary=f"Summary {id}",
        tags=tags or ["routine"],
    )


# ── Tests ──

@pytest.fixture
def memory_factory():
    with ExitStack() as stack:
        def create(*args, **options):
            return stack.enter_context(VibeMemory(*args, **options))
        yield create


@pytest.fixture
def storage_factory():
    with ExitStack() as stack:
        def create(*args, **options):
            store = VibeStorage(*args, **options)
            stack.callback(store.conn.close)
            return store
        yield create


def test_enqueue(storage_factory):
    """Test: enqueue adds candidate to queue"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error", "api"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["error", "config"])

    success = idx.enqueue(a1, a2, 0.5)
    assert success is True
    assert idx.stats()["queue_size"] == 1
    assert idx.stats()["enqueued_count"] == 1



def test_enqueue_threshold_override_is_local(storage_factory):
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1")
    first = _make_atom("first", "agent-1", "s1", tags=["a", "b", "c", "left"])
    second = _make_atom("second", "agent-1", "s2", tags=["a", "b", "c", "right"])
    storage.insert_atom(first)
    storage.insert_atom(second)

    assert idx.enqueue(first, second, 0.6) is False
    assert idx.enqueue(first, second, 0.6, similarity_threshold=0.5) is True
    assert idx.stats()["edge_similarity_threshold"] == 0.7
    assert idx.flush() == 1
    assert {(edge.from_atom_id, edge.to_atom_id) for edge in storage.get_all_edges()} == {
        (first.id, second.id),
    }
    assert idx.enqueue(first, second, 0.6, similarity_threshold=None) is False
    assert idx.enqueue(first, second, 0.6, similarity_threshold=0.8) is False
    assert idx.enqueue(first, second, 0.6, similarity_threshold=1.0) is False
    assert idx.stats()["queue_size"] == 0


@pytest.mark.parametrize("threshold", [0.5, 0.0])
def test_enqueue_batch_honors_explicit_threshold(storage_factory, threshold):
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1")
    first = _make_atom("first", "agent-1", "s1", tags=["a", "b", "c", "left"])
    second = _make_atom("second", "agent-1", "s2", tags=["a", "b", "c", "right"])
    storage.insert_atom(first)
    storage.insert_atom(second)

    assert idx.enqueue_batch(first, [second], similarity_threshold=threshold) == 1
    assert idx.stats()["edge_similarity_threshold"] == 0.7
    assert idx.stats()["queue_size"] == 1
    assert idx.flush() == 1
    assert {(edge.from_atom_id, edge.to_atom_id) for edge in storage.get_all_edges()} == {
        (first.id, second.id),
    }
    assert idx.enqueue_batch(first, [second]) == 0
    assert idx.enqueue_batch(first, [second], similarity_threshold=None) == 0


@pytest.mark.parametrize("method", ["enqueue", "enqueue_batch"])
@pytest.mark.parametrize("threshold", [True, False, float("nan"), float("inf"),
                                       float("-inf"), -0.1, 1.1, "0.5", [], 0.5j])
def test_invalid_threshold_does_not_change_full_queue(storage_factory, method, threshold):
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", max_queue_size=1)
    first = _make_atom("first", "agent-1", "s1", tags=["error"])
    second = _make_atom("second", "agent-1", "s2", tags=["error"])
    third = _make_atom("third", "agent-1", "s3", tags=["config"])
    for atom in (first, second, third):
        storage.insert_atom(atom)
    assert idx.enqueue(first, second, 0.9) is True
    before = idx.stats()

    with pytest.raises(ValueError, match="similarity_threshold"):
        if method == "enqueue":
            idx.enqueue(first, third, 0.8, similarity_threshold=threshold)
        else:
            idx.enqueue_batch(first, [third], similarity_threshold=threshold)

    if method == "enqueue_batch":
        with pytest.raises(ValueError, match="similarity_threshold"):
            idx.enqueue_batch(first, [], similarity_threshold=threshold)
    assert idx.stats() == before
    assert idx.flush() == 1
    assert {(edge.from_atom_id, edge.to_atom_id) for edge in storage.get_all_edges()} == {
        (first.id, second.id),
    }


def test_threshold_override_preserves_real_scores_and_backpressure(storage_factory):
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", max_queue_size=1,
                             backpressure=BackpressureStrategy.DROP_LOWEST)
    first = _make_atom("first", "agent-1", "s1", tags=["error"])
    second = _make_atom("second", "agent-1", "s2", tags=["error"])
    third = _make_atom("third", "agent-1", "s3", tags=["error"])
    for atom in (first, second, third):
        storage.insert_atom(atom)

    assert idx.enqueue(first, second, 0.6, similarity_threshold=0.5) is True
    before = idx.stats()
    assert idx.enqueue(first, third, 0.4, similarity_threshold=0.5) is False
    assert idx.stats() == before
    assert idx.enqueue(first, third, 0.65, similarity_threshold=0.5) is True
    assert idx.stats()["queue_size"] == 1
    assert idx.stats()["dropped_count"] == 1
    assert idx.stats()["edge_similarity_threshold"] == 0.7
    assert idx.flush() == 1
    assert {(edge.from_atom_id, edge.to_atom_id) for edge in storage.get_all_edges()} == {
        (first.id, third.id),
    }


def test_enqueue_dedup(storage_factory):
    """Test: same pair only queued once"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["error"])

    idx.enqueue(a1, a2, 0.5)
    idx.enqueue(a1, a2, 0.7)  # same pair, higher similarity
    idx.enqueue(a2, a1, 0.3)  # reversed order, same pair

    assert idx.stats()["queue_size"] == 1
    # The higher similarity should be kept
    candidates = list(idx._queue.values())
    assert candidates[0].similarity == 0.7



def test_enqueue_below_threshold(storage_factory):
    """Test: similarity below threshold is rejected"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.5)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["weather"])

    success = idx.enqueue(a1, a2, 0.3)
    assert success is False
    assert idx.stats()["queue_size"] == 0



def test_backpressure_drop_oldest(storage_factory):
    """Test: queue full → drop_oldest removes oldest entry"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(
        storage=storage, agent_id="agent-1",
        max_queue_size=3, backpressure=BackpressureStrategy.DROP_OLDEST,
        edge_similarity_threshold=0.0,
    )

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["config"])
    a3 = _make_atom("a3", "agent-1", "s3", tags=["api"])
    a4 = _make_atom("a4", "agent-1", "s4", tags=["error"])
    a5 = _make_atom("a5", "agent-1", "s5", tags=["config"])

    idx.enqueue(a1, a2, 0.6)
    idx.enqueue(a1, a3, 0.7)
    idx.enqueue(a1, a4, 0.8)
    # Queue full, drop oldest then insert
    idx.enqueue(a1, a5, 0.5)

    assert idx.stats()["queue_size"] == 3
    assert idx.stats()["dropped_count"] >= 1



def test_backpressure_drop_lowest(storage_factory):
    """Test: queue full → drop_lowest removes lowest similarity"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(
        storage=storage, agent_id="agent-1",
        max_queue_size=3, backpressure=BackpressureStrategy.DROP_LOWEST,
        edge_similarity_threshold=0.0,
    )

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["config"])
    a3 = _make_atom("a3", "agent-1", "s3", tags=["api"])
    a4 = _make_atom("a4", "agent-1", "s4", tags=["error"])

    idx.enqueue(a1, a2, 0.3)  # lowest, will be dropped
    idx.enqueue(a1, a3, 0.5)
    idx.enqueue(a1, a4, 0.7)
    # New candidate with higher similarity
    idx.enqueue(a2, a3, 0.6)  # higher than 0.3, drop 0.3

    assert idx.stats()["queue_size"] == 3
    # 0.3 should be gone
    sims = [c.similarity for c in idx._queue.values()]
    assert 0.3 not in sims



def test_flush_creates_edges(storage_factory):
    """Test: flush processes queue and creates edges"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error", "api", "timeout"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["error", "config", "timeout"])
    a3 = _make_atom("a3", "agent-1", "s3", tags=["error", "query"])

    storage.insert_atom(a1)
    storage.insert_atom(a2)
    storage.insert_atom(a3)

    idx.enqueue(a1, a2, 0.6)
    idx.enqueue(a1, a3, 0.5)

    edges_created = idx.flush()
    assert edges_created >= 1
    assert idx.stats()["processed_count"] == 2
    assert idx.stats()["edges_created"] >= 1

    # Flushed items removed from queue
    assert idx.stats()["queue_size"] == 0



def test_flush_all(storage_factory):
    """Test: flush_all processes entire queue"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(
        storage=storage, agent_id="agent-1",
        batch_size=2, edge_similarity_threshold=0.0,
    )

    for i in range(5):
        atom = _make_atom(f"a{i}", "agent-1", f"s{i}", tags=["error", "config"])
        storage.insert_atom(atom)

    a0 = storage.get_atom("a0")
    for i in range(1, 5):
        ai = storage.get_atom(f"a{i}")
        idx.enqueue(a0, ai, 0.5)

    assert idx.stats()["queue_size"] == 4

    total = idx.flush_all()
    assert idx.stats()["queue_size"] == 0
    assert total >= 0  # may create edges depending on sim



def test_flush_empty_queue(storage_factory):
    """Test: flush on empty queue is no-op"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1")

    edges = idx.flush()
    assert edges == 0



def test_auto_flush_on_store(storage_factory):
    """Test: on_store triggers flush after threshold"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(
        storage=storage, agent_id="agent-1",
        edge_similarity_threshold=0.0,
    )
    idx._auto_flush_threshold = 3  # small threshold for test

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error", "api"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["error", "config"])
    storage.insert_atom(a1)
    storage.insert_atom(a2)

    idx.enqueue(a1, a2, 0.6)

    # First 2 stores: no flush
    result = idx.on_store()
    assert result is None
    result = idx.on_store()
    assert result is None

    # 3rd store: triggers flush
    result = idx.on_store()
    assert result is not None
    assert idx.stats()["flush_count"] >= 1



def test_should_flush(storage_factory):
    """Test: should_flush when queue >= batch_size"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", batch_size=3, edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["config"])
    a3 = _make_atom("a3", "agent-1", "s3", tags=["api"])

    assert idx.should_flush() is False

    idx.enqueue(a1, a2, 0.5)
    assert idx.should_flush() is False

    idx.enqueue(a1, a3, 0.5)
    assert idx.should_flush() is False

    # Need 3 for batch_size=3
    a4 = _make_atom("a4", "agent-1", "s4", tags=["error"])
    idx.enqueue(a2, a3, 0.5)
    assert idx.should_flush() is True



def test_compact_queue(storage_factory):
    """Test: compact merges candidates pointing to same atom"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["config"])

    # Multiple candidates pointing to a2
    a3 = _make_atom("a3", "agent-1", "s3", tags=["error"])
    a4 = _make_atom("a4", "agent-1", "s4", tags=["error"])
    a5 = _make_atom("a5", "agent-1", "s5", tags=["error"])

    idx.enqueue(a1, a2, 0.5)
    idx.enqueue(a3, a2, 0.3)  # same a2, lower
    idx.enqueue(a4, a2, 0.7)  # same a2, higher
    idx.enqueue(a5, a2, 0.4)  # same a2, lower

    assert idx.stats()["queue_size"] == 4

    dropped = idx.compact_queue()
    assert dropped == 3  # kept only the highest (0.7)

    remaining = list(idx._queue.values())
    assert len(remaining) == 1
    assert remaining[0].similarity == 0.7



def test_clear_queue(storage_factory):
    """Test: clear drops everything"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["config"])
    a3 = _make_atom("a3", "agent-1", "s3", tags=["api"])

    idx.enqueue(a1, a2, 0.5)
    idx.enqueue(a1, a3, 0.6)

    dropped = idx.clear_queue()
    assert dropped == 2
    assert idx.stats()["queue_size"] == 0
    assert idx.stats()["dropped_count"] == 2



def test_stats(storage_factory):
    """Test: stats returns correct counters"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(
        storage=storage, agent_id="agent-1",
        batch_size=5, max_queue_size=100, edge_similarity_threshold=0.3,
    )

    stats = idx.stats()
    assert stats["queue_size"] == 0
    assert stats["max_queue_size"] == 100
    assert stats["batch_size"] == 5
    assert stats["edge_similarity_threshold"] == 0.3
    assert stats["backpressure"] == "drop_oldest"
    assert stats["has_llm"] is False
    assert stats["auto_flush_threshold"] == 20



def test_reset(storage_factory):
    """Test: reset clears all counters"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error"])
    a2 = _make_atom("a2", "agent-1", "s2", tags=["config"])
    idx.enqueue(a1, a2, 0.5)

    assert idx.stats()["enqueued_count"] == 1

    idx.reset()
    assert idx.stats()["enqueued_count"] == 0
    assert idx.stats()["queue_size"] == 0



def test_sdk_indexer_in_stats(memory_factory):
    """Test: SDK stats() includes indexer section"""
    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    stats = mem.stats()
    assert "indexer" in stats
    idx_stats = stats["indexer"]
    assert "queue_size" in idx_stats
    assert "enqueued_count" in idx_stats
    assert "edges_created" in idx_stats
    assert "backpressure" in idx_stats



def test_sdk_store_enqueues_candidates(memory_factory):
    """Test: SDK store() enqueues cross-session candidates"""
    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    # Store in session 1
    mem.store("API timeout error occurred", session_id="s1",
              tags=["error", "api", "timeout", "config", "runtime", "observation"])

    # Store in session 2 — should create cross-session candidate
    mem.store("Changed timeout from 30s to 60s", session_id="s2",
              tags=["error", "api", "timeout", "config", "runtime", "change"])

    stats = mem.stats()
    idx = stats["indexer"]
    assert idx["enqueued_count"] == 1
    assert idx["queue_size"] == 1
    assert idx["processed_count"] == 0
    assert idx["edges_created"] == 0
    assert mem.storage.get_all_edges() == []



def test_sdk_flush_index(memory_factory):
    """Test: SDK flush_index() processes queue"""
    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    # Five shared tags out of seven propose one non-duplicate candidate.
    first = mem.store("API timeout error occurred", session_id="s1",
                      tags=["error", "api", "timeout", "config", "runtime", "observation"])
    second = mem.store("DB connection pool config", session_id="s2",
                       tags=["error", "api", "timeout", "config", "runtime", "change"])
    mem.store("Timeout fix applied to API", session_id="s3", tags=["error", "fix", "timeout", "api"])
    mem.store("Config validation for API", session_id="s4", tags=["config", "validation", "api", "error"])

    assert mem.stats()["indexer"]["queue_size"] == 1
    assert mem.storage.get_all_edges() == []

    # Flush the indexer
    created = mem.flush_index()
    assert created == 1

    # The queued relation is persisted, not merely removed from the queue.
    stats = mem.stats()
    idx = stats["indexer"]
    assert idx["enqueued_count"] == 1
    assert idx["queue_size"] == 0
    assert idx["processed_count"] == 1
    assert idx["edges_created"] == 1
    edges = mem.storage.get_all_edges()
    assert [(edge.from_atom_id, edge.to_atom_id) for edge in edges] == [(second.id, first.id)]
    assert edges[0].label == EdgeLabel.SIMILAR



def test_sdk_auto_flush(memory_factory):
    """Test: SDK auto-flushes after enough stores"""
    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    threshold = mem.stats()["indexer"]["auto_flush_threshold"]
    first = mem.store("API timeout error occurred", session_id="s0",
                      tags=["error", "api", "timeout", "config", "runtime", "observation"])
    second = mem.store("Changed timeout from 30s to 60s", session_id="s1",
                       tags=["error", "api", "timeout", "config", "runtime", "change"])

    # Unrelated stores advance the public threshold without adding candidates.
    for i in range(2, threshold - 1):
        mem.store(f"Unrelated note {i}", session_id=f"s{i}", tags=[f"unrelated-{i}"])

    before = mem.stats()["indexer"]
    assert before["store_since_last_flush"] == threshold - 1
    assert before["queue_size"] == 1
    assert before["processed_count"] == 0
    assert before["flush_count"] == 0
    assert mem.storage.get_all_edges() == []

    mem.store("Unrelated threshold boundary note", session_id=f"s{threshold - 1}",
              tags=["threshold-boundary"])

    after = mem.stats()["indexer"]
    assert after["enqueued_count"] == 1
    assert after["processed_count"] == 1
    assert after["edges_created"] == 1
    assert after["queue_size"] == 0
    assert after["flush_count"] == 1
    assert after["store_since_last_flush"] == 0
    edges = mem.storage.get_all_edges()
    assert [(edge.from_atom_id, edge.to_atom_id) for edge in edges] == [(second.id, first.id)]
    assert edges[0].label == EdgeLabel.SIMILAR



def test_enqueue_batch(storage_factory):
    """Test: enqueue_batch processes multiple candidates"""
    storage = storage_factory(":memory:")
    idx = IncrementalIndexer(storage=storage, agent_id="agent-1", edge_similarity_threshold=0.0)

    a1 = _make_atom("a1", "agent-1", "s1", tags=["error", "api", "timeout"])

    existing = [
        _make_atom("a2", "agent-1", "s2", tags=["error", "config"]),
        _make_atom("a3", "agent-1", "s3", tags=["error", "api"]),
        _make_atom("a4", "agent-1", "s4", tags=["weather", "query"]),
    ]

    count = idx.enqueue_batch(a1, existing, similarity_threshold=0.0)
    # a2 and a3 should be similar enough (tag overlap), a4 not
    assert count >= 1
