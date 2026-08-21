"""
Tests: graph partition manager + Louvain community detection

M2 收尾 — 图分区 + 社区检测。
"""

import uuid
from datetime import datetime

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle,
)
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.graph.partition import (
    GraphPartitionManager, PartitionStats,
    _tag_overlap, _infer_cross_edge_label,
)
from vibe_memory.graph.community import (
    LouvainCommunityDetector, CommunityDetectionConfig,
)


# ── Helpers ──

def _make_atom(id: str, partition: GraphPartition, tags: list[str], session_id: str = "s1") -> MemoryAtom:
    return MemoryAtom(
        id=id, agent_id="agent-1", session_id=session_id,
        content=f"Content of {id}", summary=f"Summary {id}",
        type=partition, tags=tags,
    )


def _make_edge(id: str, from_id: str, to_id: str, label: EdgeLabel, confidence: float = 0.9) -> Edge:
    return Edge(
        id=id, from_atom_id=from_id, to_atom_id=to_id,
        label=label, confidence=confidence, weight=1.0,
    )


# ── Tests ──

def test_partition_manager_init():
    """Test GraphPartitionManager initialization"""
    store = VibeStorage(":memory:")

    # Insert atoms in different partitions
    s1 = _make_atom("s1", GraphPartition.SESSION, ["error", "config"])
    s2 = _make_atom("s2", GraphPartition.SESSION, ["config"])
    d1 = _make_atom("d1", GraphPartition.DOCUMENT, ["api", "reference"])
    p1 = _make_atom("p1", GraphPartition.PARAMETRIC, ["preference", "style"])

    store.insert_atom(s1)
    store.insert_atom(s2)
    store.insert_atom(d1)
    store.insert_atom(p1)

    # Insert edges
    e1 = _make_edge("e1", "s1", "s2", EdgeLabel.CAUSAL)
    e2 = _make_edge("e2", "s1", "d1", EdgeLabel.LOOKUP)
    e2.cross_partition = True
    store.insert_edge(e1)
    store.insert_edge(e2)

    mgr = GraphPartitionManager(store)
    mgr.initialize("agent-1")

    # Verify partitions
    assert len(mgr._atom_index[GraphPartition.SESSION]) == 2
    assert len(mgr._atom_index[GraphPartition.DOCUMENT]) == 1
    assert len(mgr._atom_index[GraphPartition.PARAMETRIC]) == 1

    # Verify edges
    session_edges = mgr.get_edges_in_partition(GraphPartition.SESSION)
    assert len(session_edges) == 1
    assert session_edges[0].label == EdgeLabel.CAUSAL

    # Verify cross-partition edges
    cross = mgr.get_cross_partition_edges()
    assert len(cross) == 1
    assert cross[0].label == EdgeLabel.LOOKUP

    print("[PASS] partition manager init test")


def test_partition_route():
    """Test atom and edge routing"""
    store = VibeStorage(":memory:")
    mgr = GraphPartitionManager(store)

    s1 = _make_atom("s1", GraphPartition.SESSION, ["error"])
    d1 = _make_atom("d1", GraphPartition.DOCUMENT, ["api"])
    p1 = _make_atom("p1", GraphPartition.PARAMETRIC, ["preference"])

    store.insert_atom(s1)
    store.insert_atom(d1)
    store.insert_atom(p1)

    mgr.route_atom(s1)
    mgr.route_atom(d1)
    mgr.route_atom(p1)

    assert "s1" in mgr._atom_index[GraphPartition.SESSION]
    assert "d1" in mgr._atom_index[GraphPartition.DOCUMENT]
    assert "p1" in mgr._atom_index[GraphPartition.PARAMETRIC]

    # Route same-partition edge
    e1 = _make_edge("e1", "s1", "d1", EdgeLabel.LOOKUP)
    mgr.route_edge(e1)
    assert e1.cross_partition  # s1(session) -> d1(document) = cross

    # Route cross-partition edge
    e2 = _make_edge("e2", "d1", "p1", EdgeLabel.REFERENCE)
    mgr.route_edge(e2)
    assert e2.cross_partition

    print("[PASS] partition route test")


def test_cross_partition_edge_building():
    """Test automatic cross-partition edge building"""
    store = VibeStorage(":memory:")

    s1 = _make_atom("s1", GraphPartition.SESSION, ["error", "config"])
    d1 = _make_atom("d1", GraphPartition.DOCUMENT, ["error", "api"])
    d2 = _make_atom("d2", GraphPartition.DOCUMENT, ["config"])
    p1 = _make_atom("p1", GraphPartition.PARAMETRIC, ["preference"])

    store.insert_atom(s1)
    store.insert_atom(d1)
    store.insert_atom(d2)
    store.insert_atom(p1)

    mgr = GraphPartitionManager(store)
    mgr.route_atom(s1)
    mgr.route_atom(d1)
    mgr.route_atom(d2)
    mgr.route_atom(p1)

    # Build cross-partition edges from session atom
    edges = mgr.build_cross_partition_edges(s1)

    # s1 should connect to d1 (shared "error" tag) -> LOOKUP
    # s1 should connect to d2 (shared "config" tag) -> LOOKUP
    # s1 should NOT connect to p1 (no shared tags, overlap < 0.3)
    assert len(edges) >= 1  # At least d1 or d2
    for edge in edges:
        assert edge.cross_partition
        assert edge.label in (EdgeLabel.LOOKUP, EdgeLabel.INFLUENCE, EdgeLabel.REFERENCE)

    print("[PASS] cross-partition edge building test")


def test_partition_get_neighbors():
    """Test get_neighbors with and without cross-partition"""
    store = VibeStorage(":memory:")

    s1 = _make_atom("s1", GraphPartition.SESSION, ["error"])
    s2 = _make_atom("s2", GraphPartition.SESSION, ["config"])
    d1 = _make_atom("d1", GraphPartition.DOCUMENT, ["error", "api"])

    store.insert_atom(s1)
    store.insert_atom(s2)
    store.insert_atom(d1)

    mgr = GraphPartitionManager(store)
    mgr.route_atom(s1)
    mgr.route_atom(s2)
    mgr.route_atom(d1)

    # Same-partition edge: s1 -> s2
    e1 = _make_edge("e1", "s1", "s2", EdgeLabel.CAUSAL)
    mgr.route_edge(e1)

    # Cross-partition edge: s1 -> d1
    e2 = _make_edge("e2", "s1", "d1", EdgeLabel.LOOKUP)
    e2.cross_partition = True
    mgr._cross_edges.append(e2)

    # Same partition only
    neighbors_same = mgr.get_neighbors("s1", include_cross_partition=False)
    assert len(neighbors_same) == 1
    assert neighbors_same[0].id == "s2"

    # Include cross-partition
    neighbors_all = mgr.get_neighbors("s1", include_cross_partition=True)
    assert len(neighbors_all) == 2
    neighbor_ids = {n.id for n in neighbors_all}
    assert "s2" in neighbor_ids
    assert "d1" in neighbor_ids

    print("[PASS] partition get_neighbors test")


def test_partition_stats():
    """Test partition statistics"""
    store = VibeStorage(":memory:")

    s1 = MemoryAtom(
        id="s1", agent_id="agent-1", session_id="s1",
        content="Session 1", summary="S1",
        type=GraphPartition.SESSION, tags=["error"],
        lifecycle=Lifecycle.ACTIVE, weight=0.9,
    )
    s2 = MemoryAtom(
        id="s2", agent_id="agent-1", session_id="s1",
        content="Session 2", summary="S2",
        type=GraphPartition.SESSION, tags=["routine"],
        lifecycle=Lifecycle.WARM, weight=0.5,
    )
    d1 = MemoryAtom(
        id="d1", agent_id="agent-1", session_id="doc",
        content="API docs", summary="API",
        type=GraphPartition.DOCUMENT, tags=["api"],
        lifecycle=Lifecycle.ACTIVE, weight=0.8,
    )
    store.insert_atom(s1)
    store.insert_atom(s2)
    store.insert_atom(d1)

    e1 = _make_edge("e1", "s1", "s2", EdgeLabel.CAUSAL)
    e2 = _make_edge("e2", "s1", "d1", EdgeLabel.LOOKUP)
    e2.cross_partition = True
    store.insert_edge(e1)
    store.insert_edge(e2)

    mgr = GraphPartitionManager(store)
    mgr.initialize("agent-1")

    stats = mgr.get_partition_stats()

    session_stats = stats[GraphPartition.SESSION]
    assert session_stats.atom_count == 2
    assert session_stats.active_atoms == 1
    assert session_stats.warm_atoms == 1
    assert session_stats.edge_count == 1

    doc_stats = stats[GraphPartition.DOCUMENT]
    assert doc_stats.atom_count == 1
    assert doc_stats.active_atoms == 1

    overall = mgr.get_overall_stats()
    assert overall["total_atoms"] == 3
    assert overall["total_edges"] == 1
    assert overall["total_cross_partition_edges"] >= 1

    print("[PASS] partition stats test")


def test_evict_atoms():
    """Test atom eviction from partition manager"""
    store = VibeStorage(":memory:")

    s1 = _make_atom("s1", GraphPartition.SESSION, ["error"])
    s2 = _make_atom("s2", GraphPartition.SESSION, ["routine"])
    store.insert_atom(s1)
    store.insert_atom(s2)

    e1 = _make_edge("e1", "s1", "s2", EdgeLabel.CAUSAL)
    store.insert_edge(e1)

    mgr = GraphPartitionManager(store)
    mgr.initialize("agent-1")

    assert "s1" in mgr._atom_index[GraphPartition.SESSION]

    # Evict s1
    evicted = mgr.evict_atoms(["s1"])
    assert evicted == 1
    assert "s1" not in mgr._atom_index[GraphPartition.SESSION]
    assert "s2" in mgr._atom_index[GraphPartition.SESSION]

    # s1's outgoing edges should be removed
    assert "s1" not in mgr._outgoing_index[GraphPartition.SESSION]

    print("[PASS] evict atoms test")


# ── Louvain Community Detection Tests ──

def test_louvain_simple_chain():
    """Test Louvain on a simple 3-node chain"""
    a1 = _make_atom("a1", GraphPartition.SESSION, ["error", "config"])
    a2 = _make_atom("a2", GraphPartition.SESSION, ["error", "config"])
    a3 = _make_atom("a3", GraphPartition.SESSION, ["query"])

    atoms = [a1, a2, a3]

    # Strong edges between a1-a2, weak between a2-a3
    edges = [
        _make_edge("e1", "a1", "a2", EdgeLabel.CAUSAL, confidence=0.9),
        _make_edge("e2", "a2", "a3", EdgeLabel.ADJACENT, confidence=0.3),
    ]
    # Make a2-a3 edge very weak
    edges[1].weight = 0.1

    detector = LouvainCommunityDetector(atoms, edges)
    communities = detector.detect()

    # Should have at least 1 community
    assert len(communities) > 0
    # a1 and a2 should be in same community (strong edge)
    assert communities["a1"] == communities["a2"]

    stats = detector.get_stats()
    assert stats["num_communities"] >= 1
    assert stats["modularity"] >= 0.0

    print("[PASS] Louvain simple chain test")


def test_louvain_empty():
    """Test Louvain with empty input"""
    detector = LouvainCommunityDetector([], [])
    communities = detector.detect()
    assert len(communities) == 0

    stats = detector.get_stats()
    assert stats["num_communities"] == 0

    print("[PASS] Louvain empty test")


def test_louvain_single_node():
    """Test Louvain with single node"""
    a1 = _make_atom("a1", GraphPartition.SESSION, ["error"])
    detector = LouvainCommunityDetector([a1], [])
    communities = detector.detect()
    assert len(communities) == 1
    assert "a1" in communities

    print("[PASS] Louvain single node test")


def test_louvain_isolated_nodes():
    """Test Louvain with isolated nodes (no edges)"""
    a1 = _make_atom("a1", GraphPartition.SESSION, ["error"])
    a2 = _make_atom("a2", GraphPartition.SESSION, ["config"])
    a3 = _make_atom("a3", GraphPartition.SESSION, ["query"])

    detector = LouvainCommunityDetector([a1, a2, a3], [])
    communities = detector.detect()

    # Each isolated node gets its own community, then small ones get merged
    assert len(communities) == 3

    print("[PASS] Louvain isolated nodes test")


def test_louvain_config():
    """Test Louvain with custom config"""
    a1 = _make_atom("a1", GraphPartition.SESSION, ["error"])
    a2 = _make_atom("a2", GraphPartition.SESSION, ["error"])
    a3 = _make_atom("a3", GraphPartition.SESSION, ["error"])
    a4 = _make_atom("a4", GraphPartition.SESSION, ["error"])

    atoms = [a1, a2, a3, a4]
    edges = [
        _make_edge("e1", "a1", "a2", EdgeLabel.CAUSAL, confidence=0.9),
        _make_edge("e2", "a2", "a3", EdgeLabel.CAUSAL, confidence=0.8),
        _make_edge("e3", "a3", "a4", EdgeLabel.CAUSAL, confidence=0.7),
    ]

    # High resolution -> more small communities
    cfg_high = CommunityDetectionConfig(resolution=2.0, min_community_size=1)
    detector_high = LouvainCommunityDetector(atoms, edges, cfg_high)
    communities_high = detector_high.detect()

    # Low resolution -> fewer large communities
    cfg_low = CommunityDetectionConfig(resolution=0.5, min_community_size=1)
    detector_low = LouvainCommunityDetector(atoms, edges, cfg_low)
    communities_low = detector_low.detect()

    # Both should produce valid results
    assert len(communities_high) >= 1
    assert len(communities_low) >= 1

    print("[PASS] Louvain config test")


def test_louvain_two_clusters():
    """Test Louvain with two distinct clusters"""
    # Cluster 1: error-related
    e1 = _make_atom("e1", GraphPartition.SESSION, ["error"])
    e2 = _make_atom("e2", GraphPartition.SESSION, ["error"])
    e3 = _make_atom("e3", GraphPartition.SESSION, ["error"])

    # Cluster 2: config-related
    c1 = _make_atom("c1", GraphPartition.SESSION, ["config"])
    c2 = _make_atom("c2", GraphPartition.SESSION, ["config"])

    atoms = [e1, e2, e3, c1, c2]

    edges = [
        # Strong intra-cluster edges
        _make_edge("ee1", "e1", "e2", EdgeLabel.CAUSAL, confidence=0.9),
        _make_edge("ee2", "e2", "e3", EdgeLabel.CAUSAL, confidence=0.8),
        _make_edge("cc1", "c1", "c2", EdgeLabel.SIMILAR, confidence=0.7),
        # Weak inter-cluster edge
        Edge(
            id="ec1", from_atom_id="e3", to_atom_id="c1",
            label=EdgeLabel.ADJACENT, confidence=0.2, weight=0.05,
            source=EdgeSource.RULE,
        ),
    ]

    detector = LouvainCommunityDetector(atoms, edges)
    communities = detector.detect()

    # e1/e2/e3 should be in same community
    assert communities["e1"] == communities["e2"]
    assert communities["e2"] == communities["e3"]

    # c1/c2 should be in same community
    assert communities["c1"] == communities["c2"]

    # The two clusters may or may not merge depending on modularity optimization
    stats = detector.get_stats()
    assert stats["num_communities"] >= 1
    assert stats["modularity"] >= 0.0

    print("[PASS] Louvain two clusters test")


def test_cross_edge_label_inference():
    """Test cross-partition edge label inference"""
    s = _make_atom("s", GraphPartition.SESSION, ["error"])
    d = _make_atom("d", GraphPartition.DOCUMENT, ["error"])
    p = _make_atom("p", GraphPartition.PARAMETRIC, ["preference"])
    s2 = _make_atom("s2", GraphPartition.SESSION, ["error"])

    # Session -> Document: LOOKUP
    label, conf = _infer_cross_edge_label(s, d)
    assert label == EdgeLabel.LOOKUP
    assert conf == 0.6

    # Document -> Session: INFLUENCE
    label, conf = _infer_cross_edge_label(d, s)
    assert label == EdgeLabel.INFLUENCE

    # Parametric -> Session: INFLUENCE
    label, conf = _infer_cross_edge_label(p, s)
    assert label == EdgeLabel.INFLUENCE

    # Session -> Session (different): REFERENCE or VERSION
    label, conf = _infer_cross_edge_label(s, s2)
    assert label in (EdgeLabel.REFERENCE, EdgeLabel.VERSION)

    print("[PASS] cross edge label inference test")


def test_tag_overlap_util():
    """Test tag overlap utility"""
    a = _make_atom("a", GraphPartition.SESSION, ["error", "config", "task"])
    b = _make_atom("b", GraphPartition.SESSION, ["error", "config"])
    c = _make_atom("c", GraphPartition.SESSION, ["query"])

    assert _tag_overlap(a, b) == 2/3  # 2 shared / 3 union
    assert _tag_overlap(a, c) == 0.0  # 0 shared / 4 union
    assert _tag_overlap(b, c) == 0.0

    print("[PASS] tag overlap test")


def run_all():
    print("=" * 50)
    print("VibeMemory M2 Graph Partition + Community Tests")
    print("=" * 50)

    # Partition tests
    test_partition_manager_init()
    test_partition_route()
    test_cross_partition_edge_building()
    test_partition_get_neighbors()
    test_partition_stats()
    test_evict_atoms()

    # Louvain tests
    test_louvain_simple_chain()
    test_louvain_empty()
    test_louvain_single_node()
    test_louvain_isolated_nodes()
    test_louvain_config()
    test_louvain_two_clusters()

    # Utility tests
    test_cross_edge_label_inference()
    test_tag_overlap_util()

    print()
    print("=" * 50)
    print("All M2 tests passed [PASS]")
    print("=" * 50)


if __name__ == "__main__":
    run_all()