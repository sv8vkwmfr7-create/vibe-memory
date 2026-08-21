"""
RAG vs VibeMemory 召回对比实验

对比：
1. 纯向量 Top-K 检索（模拟 RAG）
2. VibeMemory PPR 图检索

评估指标：
- 召回相关分片数量
- 跨会话召回能力
- 噪声抑制（无关分片占比）
"""

from datetime import datetime, timedelta
import uuid

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, EdgeLabel, EdgeSource, EdgeStatus,
)
from vibe_memory.chunking.chunker import chunk_session
from vibe_memory.edges.edge_builder import (
    build_same_session_edges,
    build_cross_session_candidates,
    classify_cross_session_edge,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import recall, fallback_vector_topk


def compare():
    """
    Run RAG (vector top-k) vs VibeMemory (PPR) comparison.

    Same 3-session scenario as simulation:
    Session 1: API timeout fix
    Session 2: DB pool + weather
    Session 3: API timeout again

    Query: "API timeout" should find Session 1 atoms.
    """
    store = VibeStorage(":memory:")
    agent_id = "agent-1"
    base_time = datetime(2026, 8, 21, 10, 0, 0)

    print("=" * 60)
    print("RAG vs VibeMemory Recall Comparison")
    print("=" * 60)

    # ── Setup: same 3 sessions ──
    s1_messages = [
        {"role": "user", "content": "API calls are timing out, help me investigate"},
        {"role": "assistant", "content": "Looking at the logs. The timeout is set to 30s which is too short. Suggest changing to 60s."},
        {"role": "user", "content": "OK, change it to 60s"},
        {"role": "assistant", "content": "Changed timeout from 30s to 60s in config. Restarting service."},
        {"role": "user", "content": "Test passed, timeout issue resolved"},
        {"role": "assistant", "content": "API timeout issue fixed. The root cause was insufficient timeout threshold."},
    ]
    s1_atoms = _ingest(store, s1_messages, agent_id, "session-1", base_time)

    s2_messages = [
        {"role": "user", "content": "Review the database connection pool settings"},
        {"role": "assistant", "content": "Current pool: max=10, min=2. Recommend max=20 for better throughput."},
        {"role": "user", "content": "Update to max=20"},
        {"role": "assistant", "content": "Updated DB pool max connections from 10 to 20."},
        {"role": "user", "content": "What's the weather like today?"},
        {"role": "assistant", "content": "Sunny, 25C. No rain expected."},
    ]
    s2_atoms = _ingest(store, s2_messages, agent_id, "session-2", base_time + timedelta(hours=1))

    s3_messages = [
        {"role": "user", "content": "API is timing out again, what did we do last time?"},
        {"role": "assistant", "content": "Let me check our memory. Last time we changed the timeout from 30s to 60s."},
    ]
    s3_atoms = _ingest(store, s3_messages, agent_id, "session-3", base_time + timedelta(hours=2))

    # Build cross-session edges
    all_atoms = store.get_atoms_by_agent(agent_id)
    for atom in all_atoms:
        if atom.session_id == "session-3":
            continue
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

    # ── Experiment 1: RAG (vector top-k) ──
    print("\n" + "-" * 40)
    print("1. RAG (Vector Top-K)")
    print("-" * 40)

    rag_results = fallback_vector_topk("API timeout", agent_id, store, top_k=5)
    print(f"  Top-5 results:")
    rag_sessions = set()
    for atom in rag_results:
        rag_sessions.add(atom.session_id)
        print(f"    [{atom.session_id}] {atom.summary[:60]}...")

    rag_s1_hits = sum(1 for a in rag_results if a.session_id == "session-1")
    rag_s3_hits = sum(1 for a in rag_results if a.session_id == "session-3")
    rag_noise = sum(1 for a in rag_results if a.session_id == "session-2")
    print(f"  Session 1 hits: {rag_s1_hits}")
    print(f"  Session 3 hits: {rag_s3_hits}")
    print(f"  Session 2 noise: {rag_noise}")

    # ── Experiment 2: VibeMemory PPR ──
    print("\n" + "-" * 40)
    print("2. VibeMemory (PPR Graph Walk)")
    print("-" * 40)

    vibe_result = recall("API timeout", agent_id, store, mode="precision")
    print(f"  Mode: precision")
    print(f"  Total walked: {vibe_result['total_walked']}")
    print(f"  Top results:")
    vibe_sessions = set()
    for atom in vibe_result["atoms"]:
        vibe_sessions.add(atom.session_id)
        print(f"    [{atom.session_id}] {atom.summary[:60]}...")

    vibe_s1_hits = sum(1 for a in vibe_result["atoms"] if a.session_id == "session-1")
    vibe_s3_hits = sum(1 for a in vibe_result["atoms"] if a.session_id == "session-3")
    vibe_noise = sum(1 for a in vibe_result["atoms"] if a.session_id == "session-2")
    print(f"  Session 1 hits: {vibe_s1_hits}")
    print(f"  Session 3 hits: {vibe_s3_hits}")
    print(f"  Session 2 noise: {vibe_noise}")

    # ── Experiment 3: VibeMemory recall mode ──
    print("\n" + "-" * 40)
    print("3. VibeMemory (Recall Mode)")
    print("-" * 40)

    vibe_recall_result = recall("API timeout", agent_id, store, mode="recall")
    print(f"  Mode: recall")
    print(f"  Total walked: {vibe_recall_result['total_walked']}")
    print(f"  Top results:")
    for atom in vibe_recall_result["atoms"]:
        print(f"    [{atom.session_id}] {atom.summary[:60]}...")

    vr_s1_hits = sum(1 for a in vibe_recall_result["atoms"] if a.session_id == "session-1")
    vr_noise = sum(1 for a in vibe_recall_result["atoms"] if a.session_id == "session-2")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"\n{'Metric':<30} {'RAG':<12} {'Vibe(prec)':<12} {'Vibe(recall)':<12}")
    print("-" * 66)
    print(f"{'Session 1 (relevant) hits':<30} {rag_s1_hits:<12} {vibe_s1_hits:<12} {vr_s1_hits:<12}")
    print(f"{'Session 2 (noise)':<30} {rag_noise:<12} {vibe_noise:<12} {vr_noise:<12}")
    print(f"{'Total walked':<30} {len(rag_results):<12} {vibe_result['total_walked']:<12} {vibe_recall_result['total_walked']:<12}")

    # Noise ratio
    rag_noise_ratio = rag_noise / max(len(rag_results), 1)
    vibe_noise_ratio = vibe_noise / max(len(vibe_result["atoms"]), 1)
    vr_noise_ratio = vr_noise / max(len(vibe_recall_result["atoms"]), 1)

    print(f"\n{'Noise Ratio':<30} {rag_noise_ratio:.0%}          {vibe_noise_ratio:.0%}          {vr_noise_ratio:.0%}")

    # Cross-session capability
    print(f"\n{'Cross-session recall':<30} {'Yes' if rag_s1_hits > 0 else 'No':<12} {'Yes' if vibe_s1_hits > 0 else 'No':<12} {'Yes' if vr_s1_hits > 0 else 'No':<12}")

    print("\n" + "=" * 60)
    print("Comparison complete!")
    print("=" * 60)


def _ingest(
    store: VibeStorage,
    messages: list[dict],
    agent_id: str,
    session_id: str,
    base_time: datetime,
) -> list[MemoryAtom]:
    """Ingest a session"""
    atoms = chunk_session(messages, agent_id, session_id)
    for i, atom in enumerate(atoms):
        atom.created_at = base_time + timedelta(minutes=i * 5)

    edges = build_same_session_edges(atoms)

    for atom in atoms:
        store.insert_atom(atom)
    for edge in edges:
        store.insert_edge(edge)

    return atoms


if __name__ == "__main__":
    compare()