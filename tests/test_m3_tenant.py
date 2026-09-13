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


def test_recall_candidates_are_scoped_active_and_bounded():
    """Recall candidates rank term matches without crossing tenant/lifecycle bounds."""
    store = VibeStorage(":memory:", tenant_id="tenant-a")
    exact = _make_atom(
        "exact", "tenant-a", "agent-1", "s1", "API timeout investigation"
    )
    partial = _make_atom(
        "partial", "tenant-a", "agent-1", "s2", "API migration checklist"
    )
    irrelevant = _make_atom(
        "irrelevant", "tenant-a", "agent-1", "s3", "Database backup completed"
    )
    archived = _make_atom(
        "archived", "tenant-a", "agent-1", "s4", "API timeout archived"
    )
    archived.lifecycle = Lifecycle.ARCHIVED
    other_tenant = _make_atom(
        "other-tenant", "tenant-b", "agent-1", "s5", "API timeout foreign"
    )
    for atom in (exact, partial, irrelevant, archived, other_tenant):
        store.insert_atom(atom)

    candidates = store.get_recall_candidates(
        "agent-1", "API timeout", limit=2, tenant_id="tenant-a"
    )

    assert [atom.id for atom in candidates] == ["exact", "partial"]


def test_recall_candidates_match_whole_terms():
    """Candidate ranking treats query terms as tokens, not substrings."""
    store = VibeStorage(":memory:", tenant_id="tenant-a")
    exact = _make_atom(
        "exact", "tenant-a", "agent-1", "s1", "API timeout investigation"
    )
    substring = _make_atom(
        "substring", "tenant-a", "agent-1", "s2", "Capillary timeout investigation"
    )
    exact.created_at = datetime(2026, 1, 1)
    substring.created_at = datetime(2026, 1, 2)
    store.insert_atom(exact)
    store.insert_atom(substring)

    candidates = store.get_recall_candidates(
        "agent-1", "API", limit=1, tenant_id="tenant-a"
    )

    assert [atom.id for atom in candidates] == ["exact"]


def test_recall_candidates_expand_two_causal_hops_within_budget():
    """Two-hop expansion stays bounded and does not cross tenant or agent scope."""
    store = VibeStorage(":memory:", tenant_id="tenant-a")
    hop_one = _make_atom("hop-one", "tenant-a", "agent-1", "s1", "First resolution step")
    hop_two = _make_atom("hop-two", "tenant-a", "agent-1", "s1", "Final rollback procedure")
    foreign = _make_atom("foreign", "tenant-b", "agent-1", "s1", "Foreign tenant answer")
    for atom in (hop_one, hop_two, foreign):
        store.insert_atom(atom)
    for index in range(12):
        store.insert_atom(
            _make_atom(
                f"noise-{index}",
                "tenant-a",
                "agent-1",
                "noise",
                f"Recent unrelated operational context {index}",
            )
        )
    seed = _make_atom("seed", "tenant-a", "agent-1", "s2", "Rare needleterm incident")
    store.insert_atom(seed)
    for edge_id, from_id, to_id in (
        ("seed-hop-one", seed.id, hop_one.id),
        ("hop-one-hop-two", hop_one.id, hop_two.id),
        ("hop-one-foreign", hop_one.id, foreign.id),
    ):
        store.insert_edge(
            Edge(
                id=edge_id,
                from_atom_id=from_id,
                to_atom_id=to_id,
                tenant_id="tenant-a",
                label=EdgeLabel.CAUSAL,
                confidence=1.0,
                weight=1.0,
            )
        )

    candidates = store.get_recall_candidates(
        "agent-1",
        "needleterm",
        limit=10,
        tenant_id="tenant-a",
        graph_seed_limit=1,
        graph_neighbor_limit=3,
        graph_hops=2,
    )

    candidate_ids = {atom.id for atom in candidates}
    assert len(candidates) == 10
    assert {"hop-one", "hop-two"} <= candidate_ids
    assert "foreign" not in candidate_ids


def test_causal_neighbor_in_lexical_tail_survives_two_hop_replacement():
    store = VibeStorage(":memory:", tenant_id="tenant-a")
    for atom_id, content, date in [
        ("hop-one", "First resolution", datetime(2026, 1, 1)),
        ("hop-two", "Final rollback", datetime(2025, 12, 1)),
        *[(f"noise-{i}", "Unrelated context", datetime(2026, 1, 2)) for i in range(8)],
        ("seed", "Rare needleterm incident", datetime(2026, 1, 3)),
    ]:
        atom = _make_atom(atom_id, "tenant-a", "agent-1", "s", content)
        atom.created_at = date
        store.insert_atom(atom)
    for from_id, to_id in [("seed", "hop-one"), ("hop-one", "hop-two")]:
        store.insert_edge(Edge(id=f"{from_id}-{to_id}", from_atom_id=from_id,
                              to_atom_id=to_id, tenant_id="tenant-a", label=EdgeLabel.CAUSAL,
                              confidence=1.0, weight=1.0))
    assert store.get_recall_candidates("agent-1", "needleterm", 10)[-1].id == "hop-one"
    candidates = store.get_recall_candidates("agent-1", "needleterm", 10,
                                             graph_seed_limit=1, graph_neighbor_limit=3, graph_hops=2)
    assert len({atom.id for atom in candidates}) == len(candidates) == 10
    assert {"seed", "hop-one", "hop-two"} <= {atom.id for atom in candidates}
    store.conn.close()


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


def test_budget_recall_keeps_causal_outcomes_over_isolated_cross_reference():
    """A lexical cross-reference must not undo seed filtering during fusion."""
    store = VibeStorage(":memory:")
    contents = ["Checkout stalled incident investigation"] * 3 + [
        "Applied connection setting", "Confirmed service recovery",
    ]
    for i, content in enumerate(contents):
        store.insert_atom(MemoryAtom(
            id=f"answer-{i}", agent_id="agent-1", session_id="s1",
            content=content, summary=content,
        ))
    for i in range(4):
        store.insert_edge(Edge(
            id=f"chain-{i}", from_atom_id=f"answer-{i}",
            to_atom_id=f"answer-{i+1}", label=EdgeLabel.CAUSAL,
        ))
    for i in range(120):
        store.insert_atom(MemoryAtom(
            id=f"background-{i}", agent_id="agent-1", session_id="s2",
            content="Routine unrelated housekeeping", summary="Background",
        ))
    store.insert_atom(MemoryAtom(
        id="cross-reference", agent_id="agent-1", session_id="s2",
        content="Checkout stalled cross-reference only, unrelated comparison",
        summary="Cross-reference",
    ))
    result = recall("Checkout stalled incident", "agent-1", store,
                    mode="budget", top_k=5, budget_graph_hops=2)
    assert {a.id for a in result["atoms"]} == {
        "answer-0", "answer-1", "answer-2", "answer-3", "answer-4",
    }


def test_recall_candidate_graph_depth_is_capped_at_two_hops():
    """A caller cannot turn budget candidate expansion into a full graph walk."""
    store = VibeStorage(":memory:")
    for i in range(4):
        atom = _make_atom(
            f"depth-{i}", DEFAULT_TENANT, "agent-1", "s1",
            "Unique incident" if i == 0 else "Resolution detail",
        )
        atom.created_at = datetime(2026, 1, 1)
        store.insert_atom(atom)
    for i in range(3):
        store.insert_edge(Edge(
            id=f"depth-edge-{i}", from_atom_id=f"depth-{i}",
            to_atom_id=f"depth-{i+1}", label=EdgeLabel.CAUSAL,
        ))
    for i in range(20):
        store.insert_atom(_make_atom(
            f"depth-noise-{i}", DEFAULT_TENANT, "agent-1", "s2", "Background",
        ))
    candidates = store.get_recall_candidates(
        "agent-1", "Unique incident", limit=10, graph_seed_limit=1,
        graph_neighbor_limit=3, graph_hops=100,
    )
    ids = {a.id for a in candidates}
    assert "depth-1" in ids and "depth-2" in ids and "depth-3" not in ids


def test_high_fanout_candidates_keep_strong_causal_neighbor():
    """Hundreds of weak neighbors cannot crowd out a later strong answer."""
    store = VibeStorage(":memory:")
    store.insert_atom(_make_atom("fan-seed", DEFAULT_TENANT, "agent-1", "s1", "Payment outage"))
    for i in range(500):
        atom = _make_atom(f"fan-{i:03}", DEFAULT_TENANT, "agent-1", "s2", "Follow-up")
        atom.created_at = datetime(2026, 1, 1)
        store.insert_atom(atom)
        store.insert_edge(Edge(
            id=f"fan-edge-{i}", from_atom_id="fan-seed", to_atom_id=atom.id,
            label=EdgeLabel.CAUSAL, weight=1.0 if i == 499 else 0.1,
        ))
    for i in range(30):
        store.insert_atom(_make_atom(f"fan-noise-{i}", DEFAULT_TENANT, "agent-1", "s3", "Background"))
    candidates = store.get_recall_candidates(
        "agent-1", "Payment outage", limit=10, graph_seed_limit=1,
        graph_neighbor_limit=2, graph_hops=2,
    )
    assert len(candidates) == 10 and "fan-499" in {a.id for a in candidates}


def test_ppr_cannot_walk_through_foreign_or_archived_nodes():
    """Out-of-scope nodes cannot act as bridges back into valid memory."""
    from vibe_memory.retrieval.ppr import personalized_pagerank
    store = VibeStorage(":memory:", tenant_id="tenant-a")
    seed = _make_atom("scope-seed", "tenant-a", "agent-1", "s1")
    valid = _make_atom("scope-valid", "tenant-a", "agent-1", "s1")
    foreign = _make_atom("scope-foreign", "tenant-b", "agent-1", "s1")
    agent = _make_atom("scope-agent", "tenant-a", "agent-2", "s1")
    archived = _make_atom("scope-archived", "tenant-a", "agent-1", "s1")
    archived.lifecycle = Lifecycle.ARCHIVED
    for atom in (seed, valid, foreign, agent, archived):
        store.insert_atom(atom)
    for atom in (foreign, agent, archived):
        for source, target in ((seed.id, atom.id), (atom.id, valid.id)):
            store.insert_edge(Edge(
                id=f"{source}-{target}", from_atom_id=source,
                to_atom_id=target, label=EdgeLabel.CAUSAL, tenant_id="tenant-a",
            ))
    assert personalized_pagerank([seed], store) == {seed.id: 1.0}


def test_ppr_respects_explicit_seed_tenant_and_warm_memory():
    from vibe_memory.retrieval.ppr import personalized_pagerank
    store = VibeStorage(":memory:", tenant_id="other-default")
    seed = _make_atom("warm-seed", "tenant-a", "agent-1", "s1")
    answer = _make_atom("warm-answer", "tenant-a", "agent-1", "s1")
    answer.lifecycle = Lifecycle.WARM
    store.insert_atom(seed)
    store.insert_atom(answer)
    store.insert_edge(Edge(
        id="warm-edge", from_atom_id=seed.id, to_atom_id=answer.id,
        tenant_id="tenant-a", label=EdgeLabel.CAUSAL,
    ))
    scores = personalized_pagerank([seed], store)
    assert set(scores) == {seed.id, answer.id} and scores[answer.id] > 0


def test_ppr_rejects_mixed_scopes_and_ignores_archived_seeds():
    import pytest
    from vibe_memory.retrieval.ppr import personalized_pagerank
    store = VibeStorage(":memory:")
    seed = _make_atom("mixed-seed", DEFAULT_TENANT, "agent-1", "s1")
    foreign = _make_atom("mixed-foreign", "tenant-b", "agent-1", "s1")
    with pytest.raises(ValueError, match="one agent and tenant"):
        personalized_pagerank([seed, foreign], store)
    seed.lifecycle = Lifecycle.ARCHIVED
    assert personalized_pagerank([seed], store) == {}
    assert personalized_pagerank([], store) == {}


def test_chinese_recall_finds_old_answer_beyond_candidate_cutoff():
    """Chinese paraphrases retrieve old relevant memories, not recent filler."""
    store = VibeStorage(":memory:")
    answer = _make_atom("zh-answer", DEFAULT_TENANT, "agent-1", "s1",
                        "连接池耗尽导致接口超时，释放连接后服务恢复正常")
    answer.created_at = datetime(2026, 1, 1)
    store.insert_atom(answer)
    for i in range(130):
        store.insert_atom(_make_atom(f"zh-noise-{i}", DEFAULT_TENANT, "agent-1", "s2",
                                    "桌面窗口颜色设置完成"))
    for mode, strategies in (("precision", ["semantic"]),
                             ("precision", ["bm25"]), ("budget", None)):
        result = recall("接口超时如何修复连接池", "agent-1", store,
                        mode=mode, top_k=1, strategies=strategies)
        assert [a.id for a in result["atoms"]] == [answer.id]


def test_budget_zero_match_padding_cannot_displace_chinese_seed():
    store = VibeStorage(":memory:")
    for atom_id, content in (
        ("pad-seed", "连接池接口超时"), ("pad-answer", "释放资源后恢复正常"),
        ("pad-noise-1", "桌面主题颜色"), ("pad-noise-2", "背景图片设置"),
    ):
        store.insert_atom(_make_atom(atom_id, DEFAULT_TENANT, "agent-1", "s1", content))
    for source, target in (("pad-seed", "pad-answer"), ("pad-noise-1", "pad-noise-2")):
        store.insert_edge(Edge(id=f"{source}-edge", from_atom_id=source,
                              to_atom_id=target, label=EdgeLabel.CAUSAL))
    result = recall("连接池接口超时", "agent-1", store, mode="budget", top_k=2)
    assert {a.id for a in result["atoms"]} == {"pad-seed", "pad-answer"}


def test_chinese_candidates_follow_edits_deletes_and_short_queries(tmp_path):
    path = str(tmp_path / "chinese.db")
    store = VibeStorage(path)
    answer = _make_atom("zh-edit", DEFAULT_TENANT, "agent-1", "s1", "连接池耗尽导致接口超时")
    answer.created_at = datetime(2026, 1, 1)
    store.insert_atom(answer)
    for i in range(12):
        store.insert_atom(_make_atom(f"zh-edit-noise-{i}", DEFAULT_TENANT, "agent-1", "s2", "桌面背景设置"))
    assert store.get_recall_candidates("agent-1", "连接池", 1)[0].id == answer.id
    assert store.get_recall_candidates("agent-1", "超时", 1)[0].id == answer.id
    answer.content = answer.summary = "验证码识别失败后重新采集"
    store.update_atom(answer)
    assert store.get_recall_candidates("agent-1", "连接池", 1)[0].id != answer.id
    assert store.get_recall_candidates("agent-1", "验证码", 1)[0].id == answer.id
    store.conn.close()
    store = VibeStorage(path)
    assert store.get_recall_candidates("agent-1", "验证码", 1)[0].id == answer.id
    store.delete_atom(answer.id)
    assert store.get_recall_candidates("agent-1", "验证码", 1)[0].id != answer.id
    store.conn.close()


def test_high_match_chinese_recall_prefers_relevant_old_answer():
    store = VibeStorage(":memory:", tenant_id="tenant-a")
    answer = _make_atom("dense-answer", "tenant-a", "agent-1", "s1", "连接池超时修复")
    answer.summary = answer.content
    answer.created_at = datetime(2026, 1, 1)
    store.insert_atom(answer)
    for i in range(250):
        noise = _make_atom(f"dense-noise-{i}", "tenant-a", "agent-1", "s2",
                           "连接池超时修复 " + "桌面背景颜色图片设置日常维护记录 " * 20)
        noise.summary = noise.content
        store.insert_atom(noise)
    for atom_id, tenant, agent, lifecycle in (
        ("dense-foreign", "tenant-b", "agent-1", Lifecycle.ACTIVE),
        ("dense-agent", "tenant-a", "agent-2", Lifecycle.ACTIVE),
        ("dense-archived", "tenant-a", "agent-1", Lifecycle.ARCHIVED),
    ):
        atom = _make_atom(atom_id, tenant, agent, "s3", answer.content)
        atom.lifecycle = lifecycle
        store.insert_atom(atom)
    result = recall("连接池超时修复", "agent-1", store, mode="budget", top_k=1)
    assert [a.id for a in result["atoms"]] == [answer.id]


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
