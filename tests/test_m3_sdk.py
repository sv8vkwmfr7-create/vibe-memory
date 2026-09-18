"""
SDK API Tests (M3)

Tests for VibeMemory unified entry class:
1. store() — single and batch
2. recall() — memory retrieval
3. link() — manual edge creation
4. migrate() — partition migration
5. forget() — memory deletion
6. update() — metadata update
7. history() — session history
8. stats() — statistics
"""

import uuid
import sqlite3
from datetime import datetime
import pytest

from vibe_memory.sdk import VibeMemory
from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle, DEFAULT_TENANT,
)


# ── Tests ──

def test_store_single():
    """Test store() single atom"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    atom = mem.store(
        content="Fixed API timeout error, changed from 30s to 60s",
        session_id="session-1",
        tags=["error", "config"],
    )

    assert atom.id is not None
    assert atom.agent_id == "test-agent"
    assert atom.session_id == "session-1"
    assert atom.tenant_id == "default"
    assert atom.tags == ["error", "config"]
    assert atom.lifecycle == Lifecycle.ACTIVE
    assert atom.weight == 1.0

    # Verify persistence
    retrieved = mem.storage.get_atom(atom.id)
    assert retrieved is not None
    assert retrieved.content == atom.content

    print("[PASS] store single test")


def test_store_scope_metadata_survives_restart_without_changing_tags(tmp_path):
    db_path = str(tmp_path / "scope.db")
    first = VibeMemory(agent_id="scope-agent", db_path=db_path,
                       embedding_backend="tfidf")
    atom = first.store(
        "Orders production export failed",
        tags=["incident"],
        scope={"service": "orders", "environment": "production",
               "operation": "export"},
        auto_build_edges=False,
        auto_episode=False,
    )
    first.storage.conn.close()

    reopened = VibeMemory(agent_id="scope-agent", db_path=db_path,
                          embedding_backend="tfidf")
    restored = reopened.storage.get_atom(atom.id)
    legacy = reopened.store(
        "Legacy call without scope",
        tags=["legacy"],
        auto_build_edges=False,
        auto_episode=False,
    )

    assert restored.scope == {
        "service": "orders",
        "environment": "production",
        "operation": "export",
    }
    assert restored.tags == ["incident"]
    assert restored.to_dict()["scope"] == restored.scope
    assert legacy.scope == {}


@pytest.mark.parametrize("scope", [
    {"servcie": "orders"},
    {"service": 7},
])
def test_store_rejects_invalid_scope_metadata(scope):
    mem = VibeMemory(agent_id="scope-agent", db_path=":memory:",
                     embedding_backend="tfidf")

    with pytest.raises(ValueError, match="scope"):
        mem.store("Invalid scope", scope=scope)


def test_existing_database_adds_scope_column_on_open(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    current = VibeMemory(agent_id="scope-agent", db_path=db_path,
                         embedding_backend="tfidf")
    current.storage.conn.close()
    with sqlite3.connect(db_path) as connection:
        connection.execute("ALTER TABLE atoms DROP COLUMN scope")

    reopened = VibeMemory(agent_id="scope-agent", db_path=db_path,
                          embedding_backend="tfidf")
    atom = reopened.store(
        "Legacy database accepts scope",
        scope={"service": "orders"},
        auto_build_edges=False,
        auto_episode=False,
    )

    assert reopened.storage.get_atom(atom.id).scope == {"service": "orders"}


def test_store_batch():
    """Test store_batch() from messages"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    messages = [
        {"role": "user", "content": "Help me fix API timeout"},
        {"role": "assistant", "content": "Looking at logs. Timeout is 30s, too short. Suggest 60s."},
        {"role": "user", "content": "OK, change it"},
        {"role": "assistant", "content": "Changed timeout from 30s to 60s. Restarting service."},
        {"role": "user", "content": "Test passed, all good"},
        {"role": "assistant", "content": "API timeout issue fixed."},
    ]

    atoms = mem.store_batch(messages, session_id="batch-1")
    assert len(atoms) >= 2  # surprise-based ingest skips routines

    # All should have same session
    for a in atoms:
        assert a.session_id == "batch-1"
        assert a.agent_id == "test-agent"

    # Edges should be auto-built
    stats = mem.stats()
    assert stats["total_edges"] >= 1

    print("[PASS] store batch test")


def test_recall():
    """Test recall() memory retrieval"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    mem.store("Fixed API timeout error", session_id="s1", tags=["error", "config"])
    mem.store("Changed timeout to 60s", session_id="s1", tags=["config"])
    mem.store("DB pool config updated", session_id="s2", tags=["config"])

    # Precision mode
    result = mem.recall("API timeout", mode="precision")
    assert "atoms" in result
    assert "trace" in result
    assert result["mode"] == "precision"
    assert len(result["atoms"]) >= 1

    # Recall mode
    result_r = mem.recall("API timeout", mode="recall")
    assert result_r["mode"] == "recall"

    # Budget mode
    result_b = mem.recall("timeout", mode="budget")
    assert result_b["mode"] == "budget"

    print("[PASS] recall test")


def test_budget_recall_uses_bounded_storage_candidates(monkeypatch):
    """Budget recall avoids the full-agent hydration path."""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    for index in range(200):
        mem.store(
            f"Routine operational context {index}",
            auto_build_edges=False,
            auto_episode=False,
        )
    target = mem.store(
        "Rare needleterm incident resolution",
        auto_build_edges=False,
        auto_episode=False,
    )

    candidate_sizes = []
    original_candidates = mem.storage.get_recall_candidates

    def tracked_candidates(*args, **kwargs):
        candidates = original_candidates(*args, **kwargs)
        candidate_sizes.append(len(candidates))
        return candidates

    def reject_full_hydration(*args, **kwargs):
        raise AssertionError("budget recall must not hydrate every agent atom")

    monkeypatch.setattr(mem.storage, "get_recall_candidates", tracked_candidates)
    monkeypatch.setattr(mem.storage, "get_atoms_by_agent", reject_full_hydration)

    result = mem.recall("needleterm", mode="budget", top_k=5)

    assert any(atom.id == target.id for atom in result["atoms"])
    assert candidate_sizes == [100]


def test_budget_recall_hydrates_causal_neighbor_within_candidate_limit(monkeypatch):
    """Budget recall keeps a graph-only answer inside its bounded candidate pool."""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    answer = mem.store(
        "Rollback the deployment and restore the previous configuration",
        auto_build_edges=False,
        auto_episode=False,
    )
    for index in range(120):
        mem.store(
            f"Recent unrelated operational context {index}",
            auto_build_edges=False,
            auto_episode=False,
        )
    seeds = [
        mem.store(
            f"Rare needleterm incident signal {index}",
            auto_build_edges=False,
            auto_episode=False,
        )
        for index in range(3)
    ]
    for seed in seeds:
        mem.link(seed.id, answer.id, label=EdgeLabel.CAUSAL)

    candidate_sizes = []
    original_candidates = mem.storage.get_recall_candidates

    def tracked_candidates(*args, **kwargs):
        candidates = original_candidates(*args, **kwargs)
        candidate_sizes.append(len(candidates))
        return candidates

    monkeypatch.setattr(mem.storage, "get_recall_candidates", tracked_candidates)

    result = mem.recall("needleterm", mode="budget", top_k=5)

    assert any(atom.id == answer.id for atom in result["atoms"])
    assert candidate_sizes == [100]


def test_recall_semantic_cache_invalidates_on_update():
    """Test: SDK semantic document cache refreshes when atom version changes."""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    atom = mem.store("API timeout needs investigation", auto_build_edges=False, auto_episode=False)

    first = mem.recall("API timeout", mode="budget", top_k=5)
    assert any(item.id == atom.id for item in first["atoms"])
    first_key = mem._semantic_cache["key"]

    updated = mem.update(atom.id, content="Database configuration needs review")
    assert updated is not None
    second = mem.recall("database configuration", mode="budget", top_k=5)

    assert any(item.id == atom.id for item in second["atoms"])
    assert mem._semantic_cache["key"] != first_key
    print("[PASS] semantic cache invalidation test")


def test_budget_recall_skips_duplicate_tfidf_rerank():
    """Budget recall relies on fused ranks without a second semantic pass."""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    for index in range(200):
        mem.store(
            f"Routine operational context {index}",
            auto_build_edges=False,
            auto_episode=False,
        )
    target = mem.store(
        "Rare needleterm incident resolution",
        auto_build_edges=False,
        auto_episode=False,
    )

    encoded_batch_sizes = []
    original_encode = mem.embedding.encode

    def tracked_encode(texts):
        encoded_batch_sizes.append(len(texts))
        return original_encode(texts)

    mem.embedding.encode = tracked_encode
    result = mem.recall("needleterm", mode="budget", top_k=5)

    assert any(atom.id == target.id for atom in result["atoms"])
    assert encoded_batch_sizes == []


def test_recall_reuses_bm25_index_until_content_changes(monkeypatch):
    """Test: repeated recalls reuse BM25, while content updates rebuild it."""
    from vibe_memory.retrieval.strategies import BM25Strategy

    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")
    target = mem.store(
        "API timeout incident resolution",
        auto_build_edges=False,
        auto_episode=False,
    )
    mem.store("Database migration checklist", auto_build_edges=False, auto_episode=False)

    fit_calls = 0
    original_fit = BM25Strategy.fit

    def tracked_fit(strategy, documents):
        nonlocal fit_calls
        fit_calls += 1
        return original_fit(strategy, documents)

    monkeypatch.setattr(BM25Strategy, "fit", tracked_fit)

    first = mem.recall("API timeout", mode="budget", top_k=5)
    second = mem.recall("API timeout", mode="budget", top_k=5)
    assert any(atom.id == target.id for atom in first["atoms"])
    assert any(atom.id == target.id for atom in second["atoms"])
    assert fit_calls == 1

    mem.update(target.id, content="Rare zephyrmarker incident resolution")
    updated = mem.recall("zephyrmarker", mode="budget", top_k=5)
    assert any(atom.id == target.id for atom in updated["atoms"])
    assert fit_calls == 2


def test_link():
    """Test link() manual edge creation"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    a1 = mem.store("API timeout error", session_id="s1", tags=["error"])
    a2 = mem.store("Changed timeout to 60s", session_id="s1", tags=["config"])

    edge = mem.link(a1.id, a2.id, label=EdgeLabel.CAUSAL, confidence=0.9)
    assert edge is not None
    assert edge.from_atom_id == a1.id
    assert edge.to_atom_id == a2.id
    assert edge.label == EdgeLabel.CAUSAL
    assert edge.confidence == 0.9
    assert edge.tenant_id == "default"

    # Cross-tenant link should be rejected
    mem2 = VibeMemory(agent_id="test-agent", db_path=":memory:", tenant_id="other")
    a3 = mem2.store("Other content", session_id="s3", tags=["query"])
    edge2 = mem.link(a1.id, a3.id)  # a1 in 'default', a3 in 'other'
    assert edge2 is None

    print("[PASS] link test")


def test_migrate():
    """Test migrate() partition migration"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    a1 = mem.store("Important API docs", session_id="s1", tags=["api", "reference"])

    # Migrate to document
    success = mem.migrate(a1.id, GraphPartition.DOCUMENT)
    assert success is True

    retrieved = mem.storage.get_atom(a1.id)
    assert retrieved.type == GraphPartition.DOCUMENT

    # Migrate to parametric
    success = mem.migrate(a1.id, GraphPartition.PARAMETRIC)
    assert success is True
    retrieved = mem.storage.get_atom(a1.id)
    assert retrieved.type == GraphPartition.PARAMETRIC
    assert retrieved.decay_rate == 0.99  # almost permanent

    # Cross-tenant should fail
    mem2 = VibeMemory(agent_id="test-agent", db_path=":memory:", tenant_id="other")
    success = mem2.migrate(a1.id, GraphPartition.SESSION)
    assert success is False

    print("[PASS] migrate test")


def test_forget():
    """Test forget() memory deletion"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    a1 = mem.store("Temporary note", session_id="s1", tags=["routine"])
    a2 = mem.store("Important note", session_id="s1", tags=["decision"])

    # Forget a1
    success = mem.forget(a1.id)
    assert success is True
    assert mem.storage.get_atom(a1.id) is None

    # a2 should still exist
    assert mem.storage.get_atom(a2.id) is not None

    # Cross-tenant forget should fail
    mem2 = VibeMemory(agent_id="test-agent", db_path=":memory:", tenant_id="other")
    success = mem2.forget(a2.id)
    assert success is False

    print("[PASS] forget test")


def test_update():
    """Test update() metadata update"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    a1 = mem.store("Original content", session_id="s1", tags=["query"])

    # Update fields
    updated = mem.update(a1.id, content="Updated content", tags=["decision"], confidence=0.5)
    assert updated is not None
    assert updated.content == "Updated content"
    assert updated.tags == ["decision"]
    assert updated.confidence == 0.5
    assert updated.version == 2  # version bumped

    # Cross-tenant update should fail
    mem2 = VibeMemory(agent_id="test-agent", db_path=":memory:", tenant_id="other")
    result = mem2.update(a1.id, content="hacked")
    assert result is None

    print("[PASS] update test")


def test_history():
    """Test history() session history"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    mem.store("First message", session_id="s1", tags=["query"])
    mem.store("Second message", session_id="s1", tags=["config"])
    mem.store("Third message", session_id="s2", tags=["error"])

    # Session s1 history
    h1 = mem.history(session_id="s1")
    assert len(h1) == 2
    assert all(a.session_id == "s1" for a in h1)

    # All history
    h_all = mem.history()
    assert len(h_all) == 3

    # Limit
    h_limited = mem.history(limit=2)
    assert len(h_limited) == 2

    print("[PASS] history test")


def test_stats():
    """Test stats() statistics"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    mem.store("API timeout error", session_id="s1", tags=["error", "config"], auto_build_edges=False)
    mem.store("DB pool config updated", session_id="s2", tags=["config"], auto_build_edges=False)
    mem.store("Weather query test", session_id="s3", tags=["query"], auto_build_edges=False)

    mem.recall("API timeout")

    stats = mem.stats()
    assert stats["agent_id"] == "test-agent"
    assert stats["tenant_id"] == "default"
    assert stats["total_atoms"] == 3
    assert stats["active_atoms"] == 3
    assert stats["store_count"] == 3
    assert stats["recall_count"] == 1
    assert "embedding_backend" in stats
    assert "partitions" in stats
    assert stats["partitions"]["session"] == 3

    print("[PASS] stats test")


def test_sdk_tenant_isolation():
    """Test full SDK tenant isolation"""
    mem_a = VibeMemory(agent_id="agent-1", db_path=":memory:", tenant_id="tenant-a", embedding_backend="tfidf")
    mem_b = VibeMemory(agent_id="agent-1", db_path=":memory:", tenant_id="tenant-b", embedding_backend="tfidf")

    a1 = mem_a.store("Tenant A content", session_id="s1", tags=["config"])
    b1 = mem_b.store("Tenant B content", session_id="s1", tags=["config"])

    # Each tenant only sees its own atoms
    assert mem_a.stats()["total_atoms"] == 1  # Same in-memory DB, but tenant-scoped query
    assert mem_b.stats()["total_atoms"] == 1

    # Cross-tenant link should fail
    edge = mem_a.link(a1.id, b1.id)
    assert edge is None

    print("[PASS] SDK tenant isolation test")


def test_sdk_auto_edges():
    """Test auto edge building in store()"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:", embedding_backend="tfidf")

    mem.store("API timeout error", session_id="s1", tags=["error", "config"])
    mem.store("Changed timeout to 60s", session_id="s1", tags=["config"])

    # Auto edges should be built within same session
    stats = mem.stats()
    assert stats["total_edges"] >= 1

    print("[PASS] SDK auto edges test")


def run_all():
    print("=" * 50)
    print("VibeMemory M3 SDK API Tests")
    print("=" * 50)

    test_store_single()
    test_store_batch()
    test_recall()
    test_link()
    test_migrate()
    test_forget()
    test_update()
    test_history()
    test_stats()
    test_sdk_tenant_isolation()
    test_sdk_auto_edges()

    print()
    print("=" * 50)
    print("All SDK API tests passed [PASS]")
    print("=" * 50)


if __name__ == "__main__":
    run_all()
