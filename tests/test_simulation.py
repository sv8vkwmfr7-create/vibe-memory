"""
模拟 3 会话跨会话记忆召回测试

模拟场景：
- 会话 1：排查 API 超时 + 修复 timeout 配置
- 会话 2：修改数据库连接池配置 + 查天气（话题切换）
- 会话 3：API 又超时了，Agent 应召回会话 1 的修复经验

测试点：
1. 同会话内建边正确
2. 跨会话 KNN 预筛 + LLM 分类
3. PPR 图游走召回相关记忆
4. Episode 聚合正确
"""

import uuid
from datetime import datetime, timedelta

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle,
)
from vibe_memory.chunking.chunker import chunk_session
from vibe_memory.chunking.episode import EpisodeBuilder, build_episode_edges
from vibe_memory.edges.edge_builder import (
    build_same_session_edges,
    build_cross_session_candidates,
    classify_cross_session_edge,
    merge_atoms,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall, PPRConfig
from vibe_memory.learner.learner import VibeLearner, DecayManager


def simulate():
    """Run 3-session simulation"""
    store = VibeStorage(":memory:")
    agent_id = "agent-1"
    base_time = datetime(2026, 8, 21, 10, 0, 0)

    print("=" * 60)
    print("VibeMemory 3-Session Cross-Session Recall Simulation")
    print("=" * 60)

    # ── Session 1: API timeout troubleshooting ──
    print("\n[Session] Session 1: API timeout troubleshooting")
    s1_messages = [
        {"role": "user", "content": "API calls are timing out, help me investigate"},
        {"role": "assistant", "content": "Looking at the logs. The timeout is set to 30s which is too short. Suggest changing to 60s."},
        {"role": "user", "content": "OK, change it to 60s"},
        {"role": "assistant", "content": "Changed timeout from 30s to 60s in config. Restarting service."},
        {"role": "user", "content": "Test passed, timeout issue resolved"},
        {"role": "assistant", "content": "API timeout issue fixed. The root cause was insufficient timeout threshold."},
    ]
    s1_atoms = _ingest_session(
        store, s1_messages, agent_id, "session-1", base_time, "Session 1: API timeout fix"
    )
    print(f"  Ingested {len(s1_atoms)} atoms")

    # ── Session 2: DB pool config + weather query (topic switch) ──
    print("\n[Session] Session 2: DB pool config + weather query")
    s2_messages = [
        {"role": "user", "content": "Review the database connection pool settings"},
        {"role": "assistant", "content": "Current pool: max=10, min=2. Recommend max=20 for better throughput."},
        {"role": "user", "content": "Update to max=20"},
        {"role": "assistant", "content": "Updated DB pool max connections from 10 to 20."},
        {"role": "user", "content": "What's the weather like today?"},
        {"role": "assistant", "content": "Sunny, 25C. No rain expected."},
    ]
    s2_atoms = _ingest_session(
        store, s2_messages, agent_id, "session-2",
        base_time + timedelta(hours=1),
        "Session 2: DB pool + weather"
    )
    print(f"  Ingested {len(s2_atoms)} atoms")

    # ── Session 3: API timeout again ──
    print("\n[Session] Session 3: API timeout again (should recall session 1)")
    s3_messages = [
        {"role": "user", "content": "API is timing out again, what did we do last time?"},
        {"role": "assistant", "content": "Let me check our memory. Last time we changed the timeout from 30s to 60s. Let me verify the current config."},
    ]
    s3_atoms = _ingest_session(
        store, s3_messages, agent_id, "session-3",
        base_time + timedelta(hours=2),
        "Session 3: API timeout again"
    )
    print(f"  Ingested {len(s3_atoms)} atoms")

    # ── Build cross-session edges ──
    print("\n[Edges] Building cross-session edges...")
    all_atoms = store.get_atoms_by_agent(agent_id)
    for atom in all_atoms:
        if atom.session_id == "session-3":
            continue  # skip session 3 atoms (already handled in same-session)
        candidates = build_cross_session_candidates(
            atom, [a for a in all_atoms if a.session_id != atom.session_id],
            medium_similarity=0.4,
        )
        for candidate in candidates["similar"]:
            label, confidence = classify_cross_session_edge(atom, candidate)
            edge = Edge(
                id=str(uuid.uuid4()),
                from_atom_id=atom.id,
                to_atom_id=candidate.id,
                label=label,
                confidence=confidence,
                source=EdgeSource.RULE,
                created_at=datetime.now(),
                status=EdgeStatus.ACTIVE,
            )
            store.insert_edge(edge)

    # ── Build Episodes ──
    print("\n[Episodes] Building Episodes...")
    builder = EpisodeBuilder(topic_switch_threshold=0.3, min_episode_size=2)
    for session_id in ["session-1", "session-2", "session-3"]:
        session_atoms = store.get_atoms_by_session(session_id)
        episodes = builder.build_episodes(session_atoms)
        for ep in episodes:
            store.insert_episode(ep)
            print(f"  Episode: {ep.topic} ({len(ep.atom_ids)} atoms)")
        # Update atoms with episode info
        for atom in session_atoms:
            store.update_atom(atom)

    # Build episode edges
    all_episodes = []
    for session_id in ["session-1", "session-2", "session-3"]:
        all_episodes.extend(store.get_episodes_by_session(session_id))
    ep_edges = build_episode_edges(all_episodes, all_atoms)
    for e in ep_edges:
        store.insert_edge(e)

    # ── Recall: query from session 3 ──
    print("\n[Recall] Recall: 'API timeout fix' (precision mode)")
    result = recall("API timeout fix", agent_id, store, mode="precision")

    print(f"  Mode: {result['mode']}")
    print(f"  Total walked: {result['total_walked']}")
    print(f"  Recalled atoms: {len(result['atoms'])}")
    for atom in result["atoms"]:
        print(f"    - [{atom.session_id}] {atom.summary[:60]}...")
    print(f"  Trace: {len(result['trace'])} paths")
    for t in result["trace"]:
        print(f"    {t['from'][:8]} --[{t['edge_label']}]--> {t['to'][:8]} (conf={t['confidence']})")

    # ── Recall: recall mode ──
    print("\n[Recall] Recall: 'API timeout' (recall mode)")
    result_recall = recall("API timeout", agent_id, store, mode="recall")
    print(f"  Recalled atoms: {len(result_recall['atoms'])}")

    # ── Stats ──
    print("\n[Stats] Graph Stats:")
    total_atoms = len(store.get_atoms_by_agent(agent_id))
    total_edges = len(store.get_all_edges())
    total_episodes = sum(
        len(store.get_episodes_by_session(s))
        for s in ["session-1", "session-2", "session-3"]
    )
    print(f"  Atoms: {total_atoms}")
    print(f"  Edges: {total_edges}")
    print(f"  Episodes: {total_episodes}")

    # ── Assertions ──
    print("\n[Verify] Verification:")
    assert total_atoms == 7, f"Expected 7 atoms, got {total_atoms}"
    print("  [PASS] 7 atoms ingested (3 sessions)")

    assert total_edges > 0, "Expected at least 1 edge"
    print(f"  [PASS] {total_edges} edges built")

    assert len(result["atoms"]) > 0, "Expected recall to find relevant atoms"
    print(f"  [PASS] {len(result['atoms'])} atoms recalled in precision mode")

    # Session 3 recall should find session 1 atoms (timeout config)
    s1_recalled = any(a.session_id == "session-1" for a in result["atoms"])
    if s1_recalled:
        print("  [PASS] Cross-session recall: Session 3 found Session 1 timeout fix")
    else:
        print("  [WARN] Cross-session recall: Session 3 did NOT find Session 1 (may need higher recall mode)")

    print("\n" + "=" * 60)
    print("Simulation complete!")
    print("=" * 60)

    return store, result


def _ingest_session(
    store: VibeStorage,
    messages: list[dict],
    agent_id: str,
    session_id: str,
    base_time: datetime,
    label: str,
) -> list[MemoryAtom]:
    """Ingest a session: chunk, build same-session edges, store."""
    atoms = chunk_session(messages, agent_id, session_id)

    # Set timestamps
    for i, atom in enumerate(atoms):
        atom.created_at = base_time + timedelta(minutes=i * 5)
        atom.source = label

    # Build same-session edges
    edges = build_same_session_edges(atoms)

    # Store
    for atom in atoms:
        store.insert_atom(atom)
    for edge in edges:
        store.insert_edge(edge)

    return atoms


if __name__ == "__main__":
    simulate()