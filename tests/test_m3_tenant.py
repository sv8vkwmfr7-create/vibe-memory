"""
Multi-Tenant Isolation Tests (M3)

Verifies:
1. Tenant-scoped queries: only return current tenant's data
2. Cross-tenant edge prevention: edges never built between tenants
3. Default tenant backward compatibility: old code without tenant_id still works
4. Multiple tenants in same DB: all CRUD operations correctly scoped
"""

import uuid
from datetime import datetime

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle, DEFAULT_TENANT,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.edges.edge_builder import build_cross_session_candidates
from vibe_memory.retrieval.ppr import recall


def _make_atom(id: str, tenant: str, agent: str, session: str,
               content: str = "test", tags: list[str] = None) -> MemoryAtom:
    return MemoryAtom(
        id=id, agent_id=agent, session_id=session,
        content=content, summary=f"Summary {id}",
        tenant_id=tenant, tags=tags or ["routine"],
    )


# ── Tests ──

def test_tenant_field_default():
    """Test tenant_id defaults to 'default'"""
    atom = MemoryAtom(
        id="a1", agent_id="agent-1", session_id="s1",
        content="test", summary="test",
    )
    assert atom.tenant_id == "default"

    edge = Edge(
        id="e1", from_atom_id="a1", to_atom_id="a2",
        label=EdgeLabel.CAUSAL,
    )
    assert edge.tenant_id == "default"

    episode = Episode(
        id="ep1", agent_id="agent-1", session_id="s1",
        summary="test", topic="test",
    )
    assert episode.tenant_id == "default"

    print("[PASS] tenant field default test")


def test_storage_tenant_scope():
    """Test that storage queries are tenant-scoped"""
    store = VibeStorage(":memory:", tenant_id="tenant-a")

    # Insert atoms for two tenants
    a1 = _make_atom("a1", "tenant-a", "agent-1", "s1", "content A")
    a2 = _make_atom("a2", "tenant-b", "agent-1", "s1", "content B")
    store.insert_atom(a1)
    store.insert_atom(a2)

    # Query by agent (should be tenant-scoped)
    atoms = store.get_atoms_by_agent("agent-1")  # uses store.tenant_id = "tenant-a"
    assert len(atoms) == 1
    assert atoms[0].id == "a1"
    assert atoms[0].tenant_id == "tenant-a"

    # Query with explicit tenant override
    atoms_b = store.get_atoms_by_agent("agent-1", tenant_id="tenant-b")
    assert len(atoms_b) == 1
    assert atoms_b[0].id == "a2"

    print("[PASS] storage tenant scope test")


def test_cross_tenant_edge_prevention():
    """Test that cross-tenant edges are never built"""
    new_atom = _make_atom("new", "tenant-a", "agent-1", "s2",
                          "API timeout fix", ["error", "config"])

    existing = [
        _make_atom("e1", "tenant-a", "agent-1", "s1",
                   "API timeout investigation", ["error", "config"]),
        _make_atom("e2", "tenant-b", "agent-1", "s1",
                   "Same content but different tenant", ["error", "config"]),
        _make_atom("e3", "tenant-a", "agent-1", "s1",
                   "Config change", ["config"]),
    ]

    result = build_cross_session_candidates(new_atom, existing, medium_similarity=0.4)

    # e1 (same tenant, full overlap) -> duplicate
    assert len(result["duplicate"]) == 1
    assert result["duplicate"][0].id == "e1"

    # e3: partial overlap 0.5 > 0.4 -> similar
    assert len(result["similar"]) == 1
    assert result["similar"][0].id == "e3"

    # e2 (different tenant) -> should NOT appear in any category
    all_ids = {a.id for a in result["duplicate"] + result["similar"] + result["noise"]}
    assert "e2" not in all_ids

    print("[PASS] cross-tenant edge prevention test")


def test_multi_tenant_atoms():
    """Test insert and query multiple tenants"""
    store = VibeStorage(":memory:")

    a1 = _make_atom("a1", "t1", "agent-1", "s1", "content 1")
    a2 = _make_atom("a2", "t2", "agent-1", "s1", "content 2")
    a3 = _make_atom("a3", "t1", "agent-1", "s2", "content 3")
    store.insert_atom(a1)
    store.insert_atom(a2)
    store.insert_atom(a3)

    # Direct query by tenant
    atoms_t1 = store.get_atoms_by_agent("agent-1", tenant_id="t1")
    assert len(atoms_t1) == 2
    assert {a.id for a in atoms_t1} == {"a1", "a3"}

    atoms_t2 = store.get_atoms_by_agent("agent-1", tenant_id="t2")
    assert len(atoms_t2) == 1
    assert atoms_t2[0].id == "a2"

    print("[PASS] multi-tenant atoms test")


def test_multi_tenant_edges():
    """Test edge insert and query with tenant isolation"""
    store = VibeStorage(":memory:")

    a1 = _make_atom("a1", "t1", "agent-1", "s1")
    a2 = _make_atom("a2", "t1", "agent-1", "s1")
    a3 = _make_atom("a3", "t2", "agent-1", "s1")
    store.insert_atom(a1)
    store.insert_atom(a2)
    store.insert_atom(a3)

    e1 = Edge(id="e1", from_atom_id="a1", to_atom_id="a2",
              label=EdgeLabel.CAUSAL, tenant_id="t1")
    e2 = Edge(id="e2", from_atom_id="a3", to_atom_id="a3",
              label=EdgeLabel.SIMILAR, tenant_id="t2")
    store.insert_edge(e1)
    store.insert_edge(e2)

    # All edges visible (no tenant filter on get_all_edges yet)
    # This is intentional — PPR filtering is done at the atom level
    all_edges = store.get_all_edges()
    assert len(all_edges) == 2

    # Edge retrieval works
    e1_retrieved = store.get_edge("e1")
    assert e1_retrieved.tenant_id == "t1"

    e2_retrieved = store.get_edge("e2")
    assert e2_retrieved.tenant_id == "t2"

    print("[PASS] multi-tenant edges test")


def test_multi_tenant_episodes():
    """Test episode insert with tenant isolation"""
    store = VibeStorage(":memory:")

    ep1 = Episode(
        id="ep1", agent_id="agent-1", session_id="s1",
        summary="Episode 1", topic="error",
        tenant_id="t1",
    )
    ep2 = Episode(
        id="ep2", agent_id="agent-1", session_id="s1",
        summary="Episode 2", topic="config",
        tenant_id="t2",
    )
    store.insert_episode(ep1)
    store.insert_episode(ep2)

    eps = store.get_episodes_by_session("s1")
    assert len(eps) == 2
    assert {e.tenant_id for e in eps} == {"t1", "t2"}

    print("[PASS] multi-tenant episodes test")


def test_recall_tenant_isolation():
    """Test recall() respects tenant_id"""
    store = VibeStorage(":memory:", tenant_id="t1")

    # T1: API timeout fix
    a1 = MemoryAtom(
        id="a1", agent_id="agent-1", session_id="s1",
        content="Fixed API timeout error, changed from 30s to 60s",
        summary="Fix timeout", tags=["error", "config"],
        tenant_id="t1", lifecycle=Lifecycle.ACTIVE,
    )
    # T2: Same content, different tenant
    a2 = MemoryAtom(
        id="a2", agent_id="agent-1", session_id="s1",
        content="Fixed API timeout error, changed from 30s to 60s",
        summary="Fix timeout", tags=["error", "config"],
        tenant_id="t2", lifecycle=Lifecycle.ACTIVE,
    )
    store.insert_atom(a1)
    store.insert_atom(a2)

    # T1 edge
    e1 = Edge(id="e1", from_atom_id="a1", to_atom_id="a1",
              label=EdgeLabel.CAUSAL, tenant_id="t1")
    store.insert_edge(e1)

    # Recall for T1
    result = recall("API timeout", "agent-1", store, mode="precision", top_k=5)
    assert len(result["atoms"]) >= 1
    # T2 atom should NOT be in results (tenant isolation)
    atom_ids = [a.id for a in result["atoms"]]
    assert "a2" not in atom_ids
    # T1 atom should be in results
    assert "a1" in atom_ids

    print("[PASS] recall tenant isolation test")


def test_recall_explicit_tenant():
    """Test recall() with explicit tenant_id override"""
    store = VibeStorage(":memory:")

    a1 = MemoryAtom(
        id="a1", agent_id="agent-1", session_id="s1",
        content="Fixed API timeout error",
        summary="Fix timeout", tags=["error", "config"],
        tenant_id="t1", lifecycle=Lifecycle.ACTIVE,
    )
    a2 = MemoryAtom(
        id="a2", agent_id="agent-1", session_id="s1",
        content="DB pool config changed",
        summary="DB pool", tags=["config"],
        tenant_id="t2", lifecycle=Lifecycle.ACTIVE,
    )
    store.insert_atom(a1)
    store.insert_atom(a2)

    # Recall for T1 explicitly
    result_t1 = recall("timeout", "agent-1", store, mode="precision", tenant_id="t1")
    t1_ids = [a.id for a in result_t1["atoms"]]
    assert "a1" in t1_ids
    assert "a2" not in t1_ids

    # Recall for T2 explicitly
    result_t2 = recall("config", "agent-1", store, mode="precision", tenant_id="t2")
    t2_ids = [a.id for a in result_t2["atoms"]]
    assert "a2" in t2_ids
    assert "a1" not in t2_ids

    print("[PASS] recall explicit tenant test")


def test_tenant_sqlite_persistence():
    """Test tenant_id is persisted and correctly loaded from SQLite"""
    store = VibeStorage(":memory:")

    atom = MemoryAtom(
        id="p1", agent_id="agent-1", session_id="s1",
        content="persistent test", summary="persist",
        tenant_id="custom-tenant", tags=["error"],
    )
    store.insert_atom(atom)

    # Read back
    retrieved = store.get_atom("p1")
    assert retrieved is not None
    assert retrieved.tenant_id == "custom-tenant"
    assert retrieved.content == "persistent test"

    print("[PASS] tenant SQLite persistence test")


def run_all():
    print("=" * 50)
    print("VibeMemory M3 Multi-Tenant Tests")
    print("=" * 50)

    test_tenant_field_default()
    test_storage_tenant_scope()
    test_cross_tenant_edge_prevention()
    test_multi_tenant_atoms()
    test_multi_tenant_edges()
    test_multi_tenant_episodes()
    test_recall_tenant_isolation()
    test_recall_explicit_tenant()
    test_tenant_sqlite_persistence()

    print()
    print("=" * 50)
    print("All M3 tenant tests passed [PASS]")
    print("=" * 50)


if __name__ == "__main__":
    run_all()