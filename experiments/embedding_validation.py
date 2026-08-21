"""
Embedding Validation Experiment: 真实 TF-IDF vs 语义 embedding

验证 M3 最关键假设：
1. 真实向量（TF-IDF）替换手工标签后，噪声是否增加？→ 已确认：40%
2. 种子后过滤能否抑制噪声？→ 已确认：不能（建边阶段就给了噪声边）
3. 语义 embedding（sentence-transformers）能否从源头解决？→ 待验证

对比六组：
A. Tag Matching + PPR (baseline) — 手工标签，噪声 20%
B. TF-IDF RAG (pure vector) — 纯向量，噪声 40%
C. TF-IDF + PPR (no filter) — 向量+图，噪声 40%
D. TF-IDF + Seed Filter + PPR — 种子过滤不生效（噪声边已建）
E. Semantic Embedding RAG — 语义向量 Top-K ← 新
F. Semantic Embedding + Seed Filter + PPR — 语义+过滤+图 ← 新
"""

import uuid
import os
from typing import Optional
import numpy as np

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.ppr import PPRConfig, personalized_pagerank, recall
from vibe_memory.retrieval.seed_filter import SeedFilter
from vibe_memory.embedding import TfidfProvider, index_flat, create_provider, EmbeddingProvider
from vibe_memory.embedding.provider import SentenceTransformerProvider


# ── 模拟数据 ──

def _make_atom(id: str, session_id: str, content: str, summary: str, tags: list[str]) -> MemoryAtom:
    return MemoryAtom(
        id=id, agent_id="agent-1", session_id=session_id,
        content=content, summary=summary,
        type=GraphPartition.SESSION, tags=tags,
    )


S1_ATOMS = [
    _make_atom("s1a", "session-1",
        "Looking at the logs. The API timeout is set to 30 seconds which is too short for our use case. We need to increase it.",
        "API timeout 30s too short", ["error", "config"]),
    _make_atom("s1b", "session-1",
        "Changed the timeout configuration from 30 seconds to 60 seconds in the service config file. Restarting the service now.",
        "Changed timeout 30s to 60s", ["config"]),
    _make_atom("s1c", "session-1",
        "The API timeout issue is now fixed. Service restarted successfully and requests are completing within the new 60 second window. No more timeout errors.",
        "API timeout issue fixed", ["error", "config"]),
]

S2_ATOMS = [
    _make_atom("s2a", "session-2",
        "Reviewed the database connection pool settings. Current pool size is 10 max connections with 2 minimum. For better throughput we should increase to 20.",
        "DB pool review", ["config"]),
    _make_atom("s2b", "session-2",
        "Updated the database pool configuration. Changed max connections from 10 to 20 and increased connection timeout from 5s to 15s.",
        "DB pool config updated", ["config"]),
    _make_atom("s2c", "session-2",
        "The user asked about today's weather forecast. I checked the weather API and it reports sunny with a high of 25 degrees Celsius.",
        "Weather query", ["query"]),
]

S3_ATOMS = [
    _make_atom("s3a", "session-3",
        "The API is timing out again. Let me check our memory. Last time we changed the timeout from 30s to 60s which fixed the issue. The current config still shows 60s so we need to investigate further.",
        "API timeout again, recall session 1", ["error", "config"]),
]


def _build_graph(store: VibeStorage) -> list[MemoryAtom]:
    """构建完整的图：插入分片 + 建边"""
    all_atoms = S1_ATOMS + S2_ATOMS + S3_ATOMS
    for a in all_atoms:
        store.insert_atom(a)

    from vibe_memory.edges.edge_builder import (
        build_same_session_edges,
        build_cross_session_candidates,
    )

    for session_atoms in [S1_ATOMS, S2_ATOMS, S3_ATOMS]:
        for e in build_same_session_edges(session_atoms):
            store.insert_edge(e)

    candidates = build_cross_session_candidates(S3_ATOMS[0], S1_ATOMS + S2_ATOMS)
    for dup in candidates["duplicate"]:
        e = Edge(
            id=str(uuid.uuid4()), from_atom_id="s3a", to_atom_id=dup.id,
            label=EdgeLabel.SIMILAR, confidence=0.9, weight=1.0,
            source=EdgeSource.RULE, status=EdgeStatus.ACTIVE,
        )
        store.insert_edge(e)
    for sim in candidates["similar"]:
        e = Edge(
            id=str(uuid.uuid4()), from_atom_id="s3a", to_atom_id=sim.id,
            label=EdgeLabel.SIMILAR, confidence=0.6, weight=0.5,
            source=EdgeSource.RULE, status=EdgeStatus.ACTIVE,
        )
        store.insert_edge(e)

    return all_atoms


def _get_semantic_provider():
    """创建语义 provider，HF 镜像优先"""
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    return SentenceTransformerProvider(model_name="all-MiniLM-L6-v2", device="cpu")


def _count_hits(ranked_ids: list[str]) -> dict:
    return {
        "s1": sum(1 for aid in ranked_ids if aid.startswith("s1")),
        "s2": sum(1 for aid in ranked_ids if aid.startswith("s2")),
        "s3": sum(1 for aid in ranked_ids if aid.startswith("s3")),
    }


# ── 实验函数 ──

def experiment_tag_baseline(all_atoms: list[MemoryAtom], store: VibeStorage):
    """A: 标签匹配 baseline"""
    from vibe_memory.retrieval.ppr import _tag_match_score
    query = "API timeout error"
    query_lower = query.lower()
    active = [a for a in all_atoms if a.lifecycle.value in ("active", "warm")]
    scored = [(a, _tag_match_score(query_lower, a)) for a in active]
    scored.sort(key=lambda x: x[1], reverse=True)
    seed_atoms = [a for a, _ in scored[:5]]

    scores = personalized_pagerank(seed_atoms, store, PPRConfig.precision())
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
    ranked_ids = [aid for aid, _ in ranked]
    hits = _count_hits(ranked_ids)

    return {
        "method": "Tag Matching + PPR",
        "s1_relevant": hits["s1"], "s2_noise": hits["s2"], "s3_query": hits["s3"],
        "noise_ratio": hits["s2"] / len(ranked_ids) if ranked_ids else 0,
        "cross_session_recall": hits["s1"] > 0,
        "total": len(ranked_ids),
    }


def experiment_tfidf_rag(all_atoms: list[MemoryAtom]):
    """B: TF-IDF RAG"""
    documents = [a.content for a in all_atoms]
    provider = TfidfProvider().fit(documents)
    doc_vectors = provider.encode(documents)
    query_vec = provider.encode_query("API timeout error")

    indices, scores = index_flat(doc_vectors, query_vec, top_k=5)
    ranked_ids = [all_atoms[i].id for i in indices]
    hits = _count_hits(ranked_ids)

    return {
        "method": "TF-IDF RAG (Top-K)",
        "s1_relevant": hits["s1"], "s2_noise": hits["s2"], "s3_query": hits["s3"],
        "noise_ratio": hits["s2"] / len(ranked_ids) if ranked_ids else 0,
        "cross_session_recall": hits["s1"] > 0,
        "total": len(ranked_ids),
        "top_scores": [round(float(s), 4) for s in scores],
    }


def experiment_tfidf_vibe_no_filter(all_atoms: list[MemoryAtom], store: VibeStorage):
    """C: TF-IDF + PPR（无种子过滤）"""
    result = recall("API timeout error", "agent-1", store, mode="precision", top_k=5,
                    embedding_provider=TfidfProvider(),
                    seed_filter=SeedFilter(min_seeds_to_filter=99))
    ranked_ids = [a.id for a in result["atoms"]]
    hits = _count_hits(ranked_ids)

    return {
        "method": "TF-IDF + PPR (no filter)",
        "s1_relevant": hits["s1"], "s2_noise": hits["s2"], "s3_query": hits["s3"],
        "noise_ratio": hits["s2"] / len(ranked_ids) if ranked_ids else 0,
        "cross_session_recall": hits["s1"] > 0,
        "total": len(ranked_ids),
        "seed_count": result.get("seed_count", 0),
        "filtered_count": result.get("filtered_count", 0),
    }


def experiment_tfidf_vibe_with_filter(all_atoms: list[MemoryAtom], store: VibeStorage):
    """D: TF-IDF + 种子后过滤 + PPR"""
    result = recall("API timeout error", "agent-1", store, mode="precision", top_k=5,
                    embedding_provider=TfidfProvider(),
                    seed_filter=SeedFilter(min_cross_seed_edges=1, min_seeds_to_filter=3))
    ranked_ids = [a.id for a in result["atoms"]]
    hits = _count_hits(ranked_ids)

    return {
        "method": "TF-IDF + Seed Filter + PPR",
        "s1_relevant": hits["s1"], "s2_noise": hits["s2"], "s3_query": hits["s3"],
        "noise_ratio": hits["s2"] / len(ranked_ids) if ranked_ids else 0,
        "cross_session_recall": hits["s1"] > 0,
        "total": len(ranked_ids),
        "seed_count": result.get("seed_count", 0),
        "filtered_count": result.get("filtered_count", 0),
    }


def experiment_semantic_rag(all_atoms: list[MemoryAtom]):
    """E: 语义 embedding RAG"""
    try:
        provider = _get_semantic_provider()
        documents = [a.content for a in all_atoms]
        doc_vectors = provider.encode(documents)
        query_vec = provider.encode_query("API timeout error")
    except Exception as e:
        return {
            "method": "Semantic Embedding RAG",
            "s1_relevant": 0, "s2_noise": 0, "s3_query": 0,
            "noise_ratio": 0, "cross_session_recall": False,
            "total": 0, "error": str(e)[:80],
        }

    indices, scores = index_flat(doc_vectors, query_vec, top_k=5)
    ranked_ids = [all_atoms[i].id for i in indices]
    hits = _count_hits(ranked_ids)

    return {
        "method": "Semantic Embedding RAG",
        "s1_relevant": hits["s1"], "s2_noise": hits["s2"], "s3_query": hits["s3"],
        "noise_ratio": hits["s2"] / len(ranked_ids) if ranked_ids else 0,
        "cross_session_recall": hits["s1"] > 0,
        "total": len(ranked_ids),
        "top_scores": [round(float(s), 4) for s in scores],
        "model": "all-MiniLM-L6-v2 (384d)",
    }


def experiment_semantic_vibe(all_atoms: list[MemoryAtom], store: VibeStorage):
    """F: 语义 embedding + 种子过滤 + PPR"""
    try:
        provider = _get_semantic_provider()
        result = recall("API timeout error", "agent-1", store, mode="precision", top_k=5,
                        embedding_provider=provider,
                        seed_filter=SeedFilter(min_cross_seed_edges=1, min_seeds_to_filter=3))
    except Exception as e:
        return {
            "method": "Semantic + Seed Filter + PPR",
            "s1_relevant": 0, "s2_noise": 0, "s3_query": 0,
            "noise_ratio": 0, "cross_session_recall": False,
            "total": 0, "error": str(e)[:80],
        }

    ranked_ids = [a.id for a in result["atoms"]]
    hits = _count_hits(ranked_ids)

    return {
        "method": "Semantic + Seed Filter + PPR",
        "s1_relevant": hits["s1"], "s2_noise": hits["s2"], "s3_query": hits["s3"],
        "noise_ratio": hits["s2"] / len(ranked_ids) if ranked_ids else 0,
        "cross_session_recall": hits["s1"] > 0,
        "total": len(ranked_ids),
        "seed_count": result.get("seed_count", 0),
        "filtered_count": result.get("filtered_count", 0),
        "model": "all-MiniLM-L6-v2 (384d)",
    }


# ── 输出 ──

def _print_result(r: dict):
    print(f"  Method:            {r['method']}")
    print(f"  Total results:     {r['total']}")
    print(f"  S1 relevant:       {r['s1_relevant']}")
    print(f"  S2 noise:          {r['s2_noise']}")
    print(f"  S3 query:          {r['s3_query']}")
    print(f"  Noise ratio:       {r['noise_ratio']:.0%}")
    print(f"  Cross-session:     {r['cross_session_recall']}")
    if "seed_count" in r:
        print(f"  Seed count:        {r['seed_count']} -> filtered: {r.get('filtered_count', '?')}")
    if "top_scores" in r:
        print(f"  Top scores:        {r['top_scores']}")
    if "model" in r:
        print(f"  Model:             {r['model']}")
    if "error" in r:
        print(f"  [SKIP] {r['error']}")


def run():
    print("=" * 70)
    print("Embedding Validation Experiment v2: TF-IDF + Semantic + Seed Filter")
    print("=" * 70)
    print()

    store = VibeStorage(":memory:")
    all_atoms = _build_graph(store)

    # A-D
    print("-" * 70)
    print("Experiment A: Tag Matching + PPR (baseline)")
    print("-" * 70)
    ra = experiment_tag_baseline(all_atoms, store)
    _print_result(ra)

    print()
    print("-" * 70)
    print("Experiment B: TF-IDF RAG (pure vector)")
    print("-" * 70)
    rb = experiment_tfidf_rag(all_atoms)
    _print_result(rb)

    print()
    print("-" * 70)
    print("Experiment C: TF-IDF + PPR (no seed filter)")
    print("-" * 70)
    rc = experiment_tfidf_vibe_no_filter(all_atoms, store)
    _print_result(rc)

    print()
    print("-" * 70)
    print("Experiment D: TF-IDF + Seed Filter + PPR")
    print("-" * 70)
    rd = experiment_tfidf_vibe_with_filter(all_atoms, store)
    _print_result(rd)

    print()
    print("-" * 70)
    print("Experiment E: Semantic Embedding RAG (loading model...)")
    print("-" * 70)
    re = experiment_semantic_rag(all_atoms)
    _print_result(re)

    print()
    print("-" * 70)
    print("Experiment F: Semantic + Seed Filter + PPR")
    print("-" * 70)
    rf = experiment_semantic_vibe(all_atoms, store)
    _print_result(rf)

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Method':<42} {'Noise':>8} {'Cross-Sess':>11} {'S1':>4} {'S2':>4}")
    print("-" * 70)
    for r in [ra, rb, rc, rd, re, rf]:
        print(f"{r['method']:<42} {r['noise_ratio']:>7.0%} {str(r['cross_session_recall']):>11} {r['s1_relevant']:>4} {r['s2_noise']:>4}")
    print("-" * 70)

    print()
    print("HYPOTHESIS CHECK:")
    for r in [(ra, "A"), (rb, "B"), (rc, "C"), (rd, "D"), (re, "E"), (rf, "F")]:
        rr, label = r
        if "error" in rr:
            print(f"  {label}. {rr['method']:<35} [SKIP] {rr['error']}")
        else:
            print(f"  {label}. {rr['method']:<35} {rr['noise_ratio']:.0%} noise, {rr['s1_relevant']} S1, {rr['s2_noise']} S2")

    if "error" not in re:
        if re["noise_ratio"] < rb["noise_ratio"]:
            print()
            print(f"  [PASS] Semantic embedding reduced noise from {rb['noise_ratio']:.0%} to {re['noise_ratio']:.0%}!")
            print(f"  all-MiniLM-L6-v2 successfully distinguishes API timeout from DB pool config.")
        else:
            print()
            print(f"  [INFO] Semantic embedding noise = {re['noise_ratio']:.0%}, same as TF-IDF.")
            print(f"  This small dataset may not benefit from semantic understanding.")

    if "error" not in rf and rf["noise_ratio"] == 0:
        print(f"  [PASS] Semantic + PPR = 0% noise! Full pipeline working as intended.")

    print()
    print("=" * 70)
    print("Experiment complete!")
    print("=" * 70)

    return ra, rb, rc, rd, re, rf


if __name__ == "__main__":
    run()