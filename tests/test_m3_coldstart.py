"""
Cold Start Tests (M3)

Verifies:
1. Phase detection: cold (<10), warmup (10-49), normal (50+)
2. Seed memory loading: from JSON, correct persistence
3. Bootstrap: one-time seed injection, idempotent
4. Threshold adjustment: cold uses lower similarity thresholds
5. Recall augmentation: cold/warmup adds seed atoms when results insufficient
6. Auto-exit: normal phase uses standard thresholds
7. SDK integration: cold start stats in stats(), bootstrap in SDK
8. Cache invalidation: store/forget invalidates atom count cache
"""

from contextlib import ExitStack
import pytest
import uuid
from datetime import datetime

from vibe_memory.coldstart import ColdStartManager, ColdPhase
from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle, DEFAULT_TENANT,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.sdk import VibeMemory


# ── Helpers ──

def _make_atom(id: str, agent: str, session: str, content: str = "test", tags: list[str] = None) -> MemoryAtom:
    return MemoryAtom(
        id=id, agent_id=agent, session_id=session,
        content=content, summary=f"Summary {id}",
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


def test_phase_cold(storage_factory):
    """Test: 0 atoms → cold phase"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(storage=storage, agent_id="agent-1")

    assert cm.phase == ColdPhase.COLD
    assert cm.is_cold is True
    assert cm.is_warmup is False
    assert cm.is_normal is False
    assert cm.atom_count == 0



def test_phase_warmup(storage_factory):
    """Test: 10 atoms → warmup phase"""
    storage = storage_factory(":memory:")
    for i in range(10):
        atom = _make_atom(f"a{i}", "agent-1", f"s{i}")
        storage.insert_atom(atom)

    cm = ColdStartManager(storage=storage, agent_id="agent-1")
    assert cm.phase == ColdPhase.WARMUP
    assert cm.is_warmup is True
    assert cm.atom_count == 10



def test_phase_normal(storage_factory):
    """Test: 50 atoms → normal phase"""
    storage = storage_factory(":memory:")
    for i in range(50):
        atom = _make_atom(f"a{i}", "agent-1", f"s{i}")
        storage.insert_atom(atom)

    cm = ColdStartManager(storage=storage, agent_id="agent-1")
    assert cm.phase == ColdPhase.NORMAL
    assert cm.is_normal is True
    assert cm.atom_count == 50



def test_threshold_adjustment(storage_factory):
    """Test: cold uses lower thresholds, normal uses standard"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(storage=storage, agent_id="agent-1")

    # Cold: 0 atoms
    assert cm.get_edge_similarity_threshold() == 0.5
    assert cm.get_merge_similarity_threshold() == 0.75

    # Warmup: 10 atoms
    for i in range(10):
        storage.insert_atom(_make_atom(f"a{i}", "agent-1", f"s{i}"))
    cm.invalidate_cache()
    assert cm.get_edge_similarity_threshold() == 0.6
    assert cm.get_merge_similarity_threshold() == 0.8

    # Normal: 50 atoms
    for i in range(10, 50):
        storage.insert_atom(_make_atom(f"a{i}", "agent-1", f"s{i}"))
    cm.invalidate_cache()
    assert cm.get_edge_similarity_threshold() == 0.7
    assert cm.get_merge_similarity_threshold() == 0.9



def test_seed_memory_loading(storage_factory):
    """Test: seed memory JSON is loaded correctly"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(
        storage=storage,
        agent_id="agent-1",
        seed_memory_path="vibe_memory/seed_memory.json",
    )

    seeds = cm.load_seed_memory()
    assert len(seeds) == 5
    assert all(s.agent_id == "__seed__" for s in seeds)
    assert all(s.source == "seed_memory" for s in seeds)
    assert all(s.weight == 0.5 for s in seeds)
    assert all(s.confidence == 0.8 for s in seeds)

    # Check tags are present
    all_tags = set()
    for s in seeds:
        all_tags.update(s.tags)
    assert "error" in all_tags
    assert "best-practice" in all_tags



def test_bootstrap_injects_seeds(storage_factory):
    """Test: bootstrap() persists seeds to agent, only once"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(
        storage=storage,
        agent_id="agent-1",
        seed_memory_path="vibe_memory/seed_memory.json",
    )

    # Before bootstrap: 0 atoms
    assert cm.atom_count == 0

    # Bootstrap
    stored = cm.bootstrap()
    assert len(stored) == 5
    assert all(a.agent_id == "agent-1" for a in stored)
    assert all(a.source == "seed_memory" for a in stored)

    cm.invalidate_cache()
    assert cm.atom_count == 5

    # Second bootstrap: idempotent
    stored2 = cm.bootstrap()
    assert len(stored2) == 0
    cm.invalidate_cache()
    assert cm.atom_count == 5  # no change



def test_bootstrap_no_seed_path(storage_factory):
    """Test: bootstrap without seed path does nothing"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(storage=storage, agent_id="agent-1")

    stored = cm.bootstrap()
    assert len(stored) == 0
    assert cm.atom_count == 0



def test_recall_augmentation_cold(storage_factory):
    """Test: cold phase augments empty results with seed atoms"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(
        storage=storage,
        agent_id="agent-1",
        seed_memory_path="vibe_memory/seed_memory.json",
    )
    cm.load_seed_memory()

    # Empty PPR result
    ppr_result = {"atoms": [], "trace": [], "mode": "precision"}

    augmented = cm.augment_recall("error configuration", ppr_result)
    assert len(augmented["atoms"]) >= 1
    assert augmented["augmented"] is True
    assert augmented["seed_count"] >= 1



def test_recall_augmentation_normal_skips(storage_factory):
    """Test: normal phase does NOT augment"""
    storage = storage_factory(":memory:")
    for i in range(50):
        storage.insert_atom(_make_atom(f"a{i}", "agent-1", f"s{i}"))

    cm = ColdStartManager(
        storage=storage,
        agent_id="agent-1",
        seed_memory_path="vibe_memory/seed_memory.json",
    )
    cm.load_seed_memory()

    ppr_result = {"atoms": [], "trace": [], "mode": "precision"}
    augmented = cm.augment_recall("error", ppr_result)
    assert augmented["atoms"] == []
    assert "augmented" not in augmented



def test_recall_augmentation_sufficient_results(storage_factory):
    """Test: sufficient results skip augmentation"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(
        storage=storage,
        agent_id="agent-1",
        seed_memory_path="vibe_memory/seed_memory.json",
    )
    cm.load_seed_memory()

    # 5 atoms already in result (cold needs 5 min)
    existing = [_make_atom(f"a{i}", "agent-1", f"s{i}") for i in range(5)]
    ppr_result = {"atoms": existing, "trace": [], "mode": "precision"}

    augmented = cm.augment_recall("test", ppr_result)
    assert "augmented" not in augmented
    assert len(augmented["atoms"]) == 5



def test_cache_invalidation(storage_factory):
    """Test: insert_atom invalidates cache"""
    storage = storage_factory(":memory:")
    cm = ColdStartManager(storage=storage, agent_id="agent-1")

    assert cm.atom_count == 0

    storage.insert_atom(_make_atom("a1", "agent-1", "s1"))
    assert cm.atom_count == 0  # cached

    cm.invalidate_cache()
    assert cm.atom_count == 1  # refreshed



def test_atom_count_uses_count_query(monkeypatch, storage_factory):
    """Test: cold-start phase counting does not hydrate every atom."""
    storage = storage_factory(":memory:")
    for index in range(3):
        storage.insert_atom(_make_atom(f"a{index}", "agent-1", f"s{index}"))
    other_tenant = _make_atom("other", "agent-1", "other-session")
    other_tenant.tenant_id = "tenant-b"
    storage.insert_atom(other_tenant)

    def fail_if_hydrated(*args, **kwargs):
        raise AssertionError("atom_count should use SQL COUNT(*)")

    monkeypatch.setattr(storage, "get_atoms_by_agent", fail_if_hydrated)
    cm = ColdStartManager(storage=storage, agent_id="agent-1")

    assert cm.atom_count == 3


def test_sdk_cold_start_integration(memory_factory):
    """Test: SDK integrates cold start manager"""
    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    # Check cold start phase in stats
    stats = mem.stats()
    assert "cold_start" in stats
    assert stats["cold_start"]["cold_start_phase"] == "cold"
    assert stats["cold_start"]["cold_start_atom_count"] == 0
    assert stats["cold_start"]["bootstrapped"] is False



def test_sdk_bootstrap_integration(memory_factory):
    """Test: SDK bootstrap works with seed memory"""
    mem = memory_factory(
        agent_id="test-agent",
        db_path=":memory:",
        embedding_backend="tfidf",
    )
    mem.cold_start.seed_memory_path = "vibe_memory/seed_memory.json"

    stored = mem.cold_start.bootstrap()
    assert len(stored) == 5

    stats = mem.stats()
    assert stats["cold_start"]["bootstrapped"] is True
    assert stats["cold_start"]["seed_memory_loaded"] is True
    assert stats["cold_start"]["seed_memory_count"] == 5
    assert stats["total_atoms"] == 5



def test_sdk_phase_transition(memory_factory):
    """Test: SDK phase transitions as atoms are stored"""

    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    # Cold phase: 0 atoms
    assert mem.cold_start.phase == ColdPhase.COLD

    # Store 10 atoms → warmup
    for i in range(10):
        mem.store(f"Test content {i}", session_id=f"s{i}", auto_build_edges=False)
    assert mem.cold_start.phase == ColdPhase.WARMUP

    # Store 40 more → normal
    for i in range(10, 50):
        mem.store(f"Test content {i}", session_id=f"s{i}", auto_build_edges=False)
    assert mem.cold_start.phase == ColdPhase.NORMAL



@pytest.mark.parametrize(
    ("atom_count", "phase", "common", "left", "right", "expected_edges"),
    [
        (2, "cold", 0, 1, 1, 0),
        (2, "cold", 1, 1, 1, 0),
        (2, "cold", 2, 1, 1, 1),
        (2, "cold", 3, 1, 1, 1),
        (10, "warmup", 2, 1, 1, 0),
        (10, "warmup", 3, 1, 1, 1),
        (50, "normal", 3, 1, 1, 0),
        (50, "normal", 7, 0, 3, 1),
    ],
)
def test_auto_build_edges_cold_thresholds(
    memory_factory, atom_count, phase, common, left, right, expected_edges,
):
    """SDK phase thresholds admit applicable cross-session candidates, not noise."""
    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    for i in range(atom_count - 2):
        mem.store(f"Unrelated filler {i}", session_id=f"filler-{i}",
                  tags=[f"unrelated-{i}"], auto_build_edges=False, auto_episode=False)
    shared = [f"shared-{i}" for i in range(common)]
    first = mem.store("Separate API observation", session_id="first",
                      tags=shared + [f"left-{i}" for i in range(left)], auto_episode=False)
    second = mem.store("Different API observation", session_id="second",
                       tags=shared + [f"right-{i}" for i in range(right)], auto_episode=False)

    assert mem.stats()["cold_start"]["cold_start_phase"] == phase
    assert mem.stats()["indexer"]["enqueued_count"] == expected_edges
    assert mem.stats()["indexer"]["edge_similarity_threshold"] == 0.7
    mem.flush_index()
    assert mem.stats()["indexer"]["processed_count"] == expected_edges
    assert mem.stats()["indexer"]["edges_created"] == expected_edges
    assert mem.stats()["indexer"]["queue_size"] == 0
    expected = {(second.id, first.id)} if expected_edges else set()
    assert {(edge.from_atom_id, edge.to_atom_id) for edge in mem.storage.get_all_edges()} == expected
    assert mem.storage.get_atom(first.id).content == "Separate API observation"
    assert mem.storage.get_atom(second.id).content == "Different API observation"



def test_stats_phase_field(memory_factory):
    """Test: stats() cold_start field is complete"""
    mem = memory_factory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    mem.cold_start.seed_memory_path = "vibe_memory/seed_memory.json"
    mem.cold_start.load_seed_memory()

    stats = mem.stats()
    cs = stats["cold_start"]

    assert "cold_start_phase" in cs
    assert "cold_start_atom_count" in cs
    assert "cold_threshold" in cs
    assert "warmup_threshold" in cs
    assert "seed_memory_loaded" in cs
    assert "seed_memory_count" in cs
    assert "bootstrapped" in cs
    assert "edge_similarity_threshold" in cs
    assert "merge_similarity_threshold" in cs

    assert cs["cold_threshold"] == 10
    assert cs["warmup_threshold"] == 50
    assert cs["seed_memory_count"] == 5
