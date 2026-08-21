"""
Tests: data structures + semantic chunking + same-session edges + storage layer

L1 prototype integration test suite.
"""

import uuid
from datetime import datetime

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle,
)
from vibe_memory.chunking.chunker import chunk_session, should_ingest
from vibe_memory.edges.edge_builder import (
    build_same_session_edges,
    build_cross_session_candidates,
    classify_cross_session_edge,
    merge_atoms,
)
from vibe_memory.storage.sqlite_store import VibeStorage


def test_memory_atom():
    """Test MemoryAtom data structure"""
    atom = MemoryAtom(
        id=str(uuid.uuid4()),
        agent_id="agent-1",
        session_id="session-1",
        content="Fixed API timeout issue, changed timeout from 30s to 60s",
        summary="Fixed API timeout",
        tags=["error", "config"],
        context_before="[user]: API timeout error",
        context_after="[user]: OK, working now",
    )

    assert atom.weight == 1.0
    assert atom.decay_rate == 0.95
    assert atom.lifecycle == Lifecycle.ACTIVE
    assert atom.type == GraphPartition.SESSION

    # Test decay
    atom.last_accessed = datetime(2026, 8, 1)
    atom.decay()
    assert atom.weight < 1.0

    # Test reinforce
    atom.reinforce()
    assert atom.weight <= 1.0
    assert atom.access_count == 1

    # Test feedback learning
    atom.learn_from_feedback(was_adopted=True)
    assert atom.adopted_count == 1
    assert atom.decay_rate > 0.95  # adopted, slower decay

    atom.learn_from_feedback(was_adopted=False)
    assert atom.ignored_count == 1

    print("[PASS] MemoryAtom test")


def test_chunking():
    """Test semantic chunking"""
    messages = [
        {"role": "user", "content": "Help me troubleshoot API timeout"},
        {"role": "assistant", "content": "Looking at logs. Timeout is 30s, too short. Suggest 60s."},
        {"role": "user", "content": "OK, change it"},
        {"role": "assistant", "content": "Changed timeout from 30s to 60s. Restarting service. Testing now."},
        {"role": "user", "content": "Test passed, all good"},
        {"role": "assistant", "content": "API timeout issue fixed."},
    ]

    atoms = chunk_session(messages, "agent-1", "session-1")

    assert len(atoms) == 3  # 3 assistant replies
    # First msg has 'timeout' and 'suggest' -> error + config
    assert "error" in atoms[0].tags
    assert "config" in atoms[0].tags
    # Second msg has 'changed' -> config
    assert "config" in atoms[1].tags
    # Third msg is routine
    assert len(atoms[2].tags) >= 1

    print("[PASS] chunking test")


def test_surprise_ingest():
    """Test surprise-based ingest decision"""
    # Error -> should ingest
    assert should_ingest("API timeout error", None) is True

    # Routine -> should NOT ingest
    assert should_ingest("OK, got it", None) is False

    # User correction -> should ingest
    assert should_ingest("No, that's not the issue", None) is True

    print("[PASS] surprise-based ingest test")


def test_same_session_edges():
    """Test same-session edge building"""
    atoms = [
        MemoryAtom(
            id="a1", agent_id="agent-1", session_id="s1",
            content="Identified timeout issue in the API",
            summary="Timeout issue", tags=["error", "config"],
        ),
        MemoryAtom(
            id="a2", agent_id="agent-1", session_id="s1",
            content="Reviewed DB connection pool settings",
            summary="Pool settings", tags=["config"],
        ),
        MemoryAtom(
            id="a3", agent_id="agent-1", session_id="s1",
            content="Checked weather forecast",
            summary="Weather query", tags=["query"],
        ),
    ]

    edges = build_same_session_edges(atoms)

    assert len(edges) == 2  # 2 adjacent pairs

    # a1->a2: shared tag "config" -> SIMILAR
    assert edges[0].label == EdgeLabel.SIMILAR
    assert edges[0].confidence == 0.7

    # a2->a3: no shared tags -> ADJACENT (weak)
    assert edges[1].label == EdgeLabel.ADJACENT
    assert edges[1].confidence == 0.3

    print("[PASS] same-session edges test")


def test_cross_session_candidates():
    """Test cross-session KNN pre-screening"""
    new_atom = MemoryAtom(
        id="new", agent_id="agent-1", session_id="s2",
        content="Fixed API timeout", summary="Fix timeout",
        tags=["error", "config"],
    )

    existing = [
        MemoryAtom(
            id="e1", agent_id="agent-1", session_id="s1",
            content="API timeout investigation", summary="Investigating timeout",
            tags=["error", "config"],
        ),
        MemoryAtom(
            id="e2", agent_id="agent-1", session_id="s1",
            content="Changed config", summary="Change config",
            tags=["config"],
        ),
        MemoryAtom(
            id="e3", agent_id="agent-1", session_id="s1",
            content="Check weather", summary="Weather query",
            tags=["query"],
        ),
    ]

    result = build_cross_session_candidates(new_atom, existing, medium_similarity=0.4)

    # e1: full tag overlap (ratio=1.0) -> duplicate
    assert len(result["duplicate"]) == 1
    assert result["duplicate"][0].id == "e1"

    # e2: partial overlap (ratio=0.5 > 0.4) -> similar
    assert len(result["similar"]) == 1
    assert result["similar"][0].id == "e2"

    # e3: no overlap (ratio=0.0) -> noise
    assert len(result["noise"]) == 1
    assert result["noise"][0].id == "e3"

    print("[PASS] cross-session KNN test")


def test_merge_atoms():
    """Test atom merging"""
    a = MemoryAtom(
        id="a", agent_id="agent-1", session_id="s1",
        content="Fixed timeout", summary="Fix timeout",
        tags=["error", "config"], weight=0.8, decay_rate=0.95,
    )
    b = MemoryAtom(
        id="b", agent_id="agent-1", session_id="s1",
        content="timeout changed to 60s", summary="Change timeout",
        tags=["config"], weight=0.9, decay_rate=0.93,
    )

    merged = merge_atoms(a, b)

    assert merged.weight == 0.9  # max
    assert merged.decay_rate == 0.95  # max
    assert len(merged.tags) == 2  # deduped
    assert "error" in merged.tags and "config" in merged.tags
    assert merged.previous_version_id == "a"
    assert merged.version == 2  # max(1, 1) + 1

    print("[PASS] atom merge test")


def test_storage():
    """Test SQLite storage layer"""
    store = VibeStorage(":memory:")

    # Insert atom
    atom = MemoryAtom(
        id="a1", agent_id="agent-1", session_id="s1",
        content="Fixed API timeout", summary="Fix timeout",
        tags=["error", "config"],
    )
    store.insert_atom(atom)

    # Read
    retrieved = store.get_atom("a1")
    assert retrieved is not None
    assert retrieved.content == "Fixed API timeout"
    assert retrieved.tags == ["error", "config"]

    # Update
    retrieved.reinforce()
    store.update_atom(retrieved)
    updated = store.get_atom("a1")
    assert updated.access_count == 1

    # Insert edge
    edge = Edge(
        id="e1", from_atom_id="a1", to_atom_id="a1",
        label=EdgeLabel.CAUSAL, confidence=0.9,
    )
    store.insert_edge(edge)
    assert store.get_edge("e1") is not None

    # Query by session
    atoms = store.get_atoms_by_session("s1")
    assert len(atoms) == 1

    print("[PASS] SQLite storage test")


def run_all():
    print("=" * 50)
    print("VibeMemory L1 Prototype Tests")
    print("=" * 50)

    test_memory_atom()
    test_chunking()
    test_surprise_ingest()
    test_same_session_edges()
    test_cross_session_candidates()
    test_merge_atoms()
    test_storage()

    print()
    print("=" * 50)
    print("All tests passed [PASS]")
    print("=" * 50)


if __name__ == "__main__":
    run_all()