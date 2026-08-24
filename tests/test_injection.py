"""
Tests for MAC/MAG prompt injection module.

Covers:
- MACInjector: full-text injection with trace
- MAGInjector: gated signal injection
- build_injection(): universal factory
- Edge priority mapping
- Token budgeting and truncation
- SessionManager integration
- SDK inject() method
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vibe_memory.injection import (
    MACInjector,
    MAGInjector,
    build_injection,
    _atom_priority,
    _estimate_tokens,
    EDGE_PRIORITY,
)
from vibe_memory.models.memory_atom import (
    MemoryAtom, EdgeLabel, Lifecycle, GraphPartition,
)


# ── Fixtures ──

def make_atom(id="a1", content="", summary="", tags=None, session_id="s1"):
    return MemoryAtom(
        id=id, agent_id="test", session_id=session_id,
        content=content, summary=summary or content[:50],
        tags=tags or [], lifecycle=Lifecycle.ACTIVE,
        type=GraphPartition.SESSION,
    )


def make_recall_result(atoms, trace=None, mode="precision"):
    return {"atoms": atoms, "trace": trace or [], "mode": mode}


# ── _estimate_tokens ──

def test_estimate_tokens():
    assert _estimate_tokens("hello world") == 2  # 11 chars / 4 = 2
    assert _estimate_tokens("") == 0


def test_estimate_tokens_empty():
    assert _estimate_tokens("") == 0


# ── _atom_priority ──

def test_atom_priority_high():
    atom = make_atom("a1")
    trace = [{"from": "a1", "to": "a2", "edge_label": "因果接续"}]
    assert _atom_priority(atom, trace) == "high"


def test_atom_priority_medium():
    atom = make_atom("a1")
    trace = [{"from": "a1", "to": "a2", "edge_label": "同类经验"}]
    assert _atom_priority(atom, trace) == "medium"


def test_atom_priority_low_default():
    atom = make_atom("a1")
    trace = [{"from": "a1", "to": "a2", "edge_label": "时序相邻"}]
    assert _atom_priority(atom, trace) == "low"


def test_atom_priority_no_trace():
    atom = make_atom("a1")
    assert _atom_priority(atom, []) == "low"


def test_atom_priority_revision():
    atom = make_atom("a1")
    trace = [{"from": "a1", "to": "a2", "edge_label": "修正推翻"}]
    assert _atom_priority(atom, trace) == "high"


def test_atom_priority_picks_best():
    # Has both high and low edges — should pick high
    atom = make_atom("a1")
    trace = [
        {"from": "a1", "to": "a2", "edge_label": "时序相邻"},
        {"from": "a2", "to": "a1", "edge_label": "因果接续"},
    ]
    assert _atom_priority(atom, trace) == "high"


# ── MACInjector ──

def test_mac_empty():
    mac = MACInjector()
    result = mac.build(make_recall_result([]))
    assert "no relevant memories" in result


def test_mac_basic():
    mac = MACInjector(max_tokens=4000)
    atoms = [
        make_atom("a1", "Fixed API timeout", "Fixed timeout", ["error", "fix"], "s1"),
        make_atom("a2", "DB pool config", "DB pool", ["config"], "s2"),
    ]
    result = mac.build(make_recall_result(atoms))
    assert "Memory-Augmented Context" in result
    assert "Fixed API timeout" in result
    assert "DB pool config" in result


def test_mac_with_trace():
    mac = MACInjector(max_tokens=4000, include_trace=True)
    atoms = [
        make_atom("a1", "Fixed timeout", "Fixed timeout", ["error"], "s1"),
        make_atom("a2", "Pool issue", "Pool issue", ["error"], "s2"),
    ]
    trace = [
        {"from": "a1", "to": "a2", "edge_label": "因果接续", "confidence": 0.95},
    ]
    result = mac.build(make_recall_result(atoms, trace))
    assert "Relationship Map" in result
    assert "因果接续" in result


def test_mac_no_trace():
    mac = MACInjector(max_tokens=4000, include_trace=False)
    atoms = [
        make_atom("a1", "Fixed timeout", "Fixed timeout", ["error"], "s1"),
    ]
    result = mac.build(make_recall_result(atoms))
    assert "Relationship Map" not in result


def test_mac_summary_only():
    mac = MACInjector(max_tokens=4000, include_content=False)
    atoms = [
        make_atom("a1", "Fixed API timeout error, changed from 30s to 60s", "Fixed timeout", ["error"], "s1"),
    ]
    result = mac.build(make_recall_result(atoms))
    assert "Memory-Augmented Context" in result
    # Should have summary but not full content
    assert "Fixed timeout" in result


def test_mac_token_budget_truncation():
    mac = MACInjector(max_tokens=50)  # Very tight budget
    atoms = [
        make_atom("a1", "A" * 200, "Summary A", ["error"], "s1"),
        make_atom("a2", "B" * 200, "Summary B", ["config"], "s2"),
    ]
    result = mac.build(make_recall_result(atoms))
    assert "truncated" in result.lower()


def test_mac_priority_markers():
    mac = MACInjector(max_tokens=4000)
    atoms = [
        make_atom("a1", "Causal content", "Causal", ["error"], "s1"),
        make_atom("a2", "Similar content", "Similar", ["config"], "s2"),
    ]
    trace = [
        {"from": "a1", "to": "a2", "edge_label": "因果接续"},
    ]
    result = mac.build(make_recall_result(atoms, trace))
    # High priority atoms should have red marker
    assert "🔴" in result


# ── MAGInjector ──

def test_mag_empty():
    mag = MAGInjector()
    result = mag.build(make_recall_result([]))
    assert "no signals" in result


def test_mag_basic():
    mag = MAGInjector(max_tokens=1000)
    atoms = [
        make_atom("a1", "Fixed API timeout", "Fixed timeout", ["error", "fix"], "s1"),
        make_atom("a2", "DB pool config", "DB pool", ["config"], "s2"),
    ]
    result = mag.build(make_recall_result(atoms))
    assert "Memory Signals" in result
    assert "Fixed timeout" in result
    assert "DB pool" in result


def test_mag_groups_by_priority():
    mag = MAGInjector(max_tokens=2000)
    atoms = [
        make_atom("a1", "Causal", "Causal", ["error"], "s1"),
        make_atom("a2", "Similar", "Similar", ["config"], "s2"),
        make_atom("a3", "Adjacent", "Adjacent", ["query"], "s3"),
    ]
    trace = [
        {"from": "a1", "to": "a2", "edge_label": "因果接续"},
        {"from": "a2", "to": "a3", "edge_label": "时序相邻"},
    ]
    result = mag.build(make_recall_result(atoms, trace))
    # a1 and a2 share causal edge → both high → Critical
    assert "Critical Context" in result
    # a3 has only adjacent edge → low → Background
    assert "Background" in result
    assert "3 signals total" in result


def test_mag_token_budget():
    mag = MAGInjector(max_tokens=30)  # Very tight
    atoms = [
        make_atom("a1", "Causal content here", "Causal", ["error"], "s1"),
        make_atom("a2", "Similar content here", "Similar", ["config"], "s2"),
    ]
    result = mag.build(make_recall_result(atoms))
    # Should still produce something small
    assert "Memory Signals" in result


def test_mag_signal_count():
    mag = MAGInjector(max_tokens=2000)
    atoms = [
        make_atom("a1", "C", "C", ["t"], "s1"),
        make_atom("a2", "C", "C", ["t"], "s2"),
    ]
    trace = [
        {"from": "a1", "to": "a2", "edge_label": "因果接续"},
    ]
    result = mag.build(make_recall_result(atoms, trace))
    assert "2 signals total" in result
    # Both share causal edge → both critical
    assert "2 critical" in result


def test_mag_no_emphasis():
    mag = MAGInjector(max_tokens=2000, emphasis=False)
    atoms = [
        make_atom("a1", "C", "C", ["t"], "s1"),
        make_atom("a2", "C", "C", ["t"], "s2"),
    ]
    trace = [
        {"from": "a1", "to": "a2", "edge_label": "因果接续"},
    ]
    result = mag.build(make_recall_result(atoms, trace))
    assert "Critical Context" in result
    # No emphasis markers in descriptions
    assert "_" not in result.split("Critical Context")[0]


# ── build_injection ──

def test_build_injection_mac():
    atoms = [make_atom("a1", "Content", "Summary", ["t"], "s1")]
    result = build_injection(make_recall_result(atoms), mode="mac", max_tokens=4000)
    assert "Memory-Augmented Context" in result


def test_build_injection_mag():
    atoms = [make_atom("a1", "Content", "Summary", ["t"], "s1")]
    result = build_injection(make_recall_result(atoms), mode="mag", max_tokens=1000)
    assert "Memory Signals" in result


def test_build_injection_unknown_mode():
    with pytest.raises(ValueError, match="Unknown injection mode"):
        build_injection(make_recall_result([]), mode="unknown")


# ── Edge priority mapping ──

def test_all_edge_labels_mapped():
    for label in EdgeLabel:
        assert label in EDGE_PRIORITY, f"EdgeLabel.{label.name} missing from EDGE_PRIORITY"


def test_edge_priority_values():
    assert EDGE_PRIORITY[EdgeLabel.CAUSAL] == "high"
    assert EDGE_PRIORITY[EdgeLabel.REVISION] == "high"
    assert EDGE_PRIORITY[EdgeLabel.VERSION] == "high"
    assert EDGE_PRIORITY[EdgeLabel.SIMILAR] == "medium"
    assert EDGE_PRIORITY[EdgeLabel.INFLUENCE] == "medium"
    assert EDGE_PRIORITY[EdgeLabel.ADJACENT] == "low"


# ── SDK inject() integration ──

def test_sdk_inject_mac():
    from vibe_memory import VibeMemory
    mem = VibeMemory(agent_id="test", db_path=":memory:", embedding_backend="tfidf")
    mem.store("Fixed API timeout", session_id="s1", tags=["error", "fix"])
    mem.store("DB pool config", session_id="s2", tags=["config"])

    injection = mem.inject("API timeout", injection_mode="mac", max_tokens=4000)
    assert "Memory-Augmented Context" in injection
    assert "Fixed API timeout" in injection


def test_sdk_inject_mag():
    from vibe_memory import VibeMemory
    mem = VibeMemory(agent_id="test", db_path=":memory:", embedding_backend="tfidf")
    mem.store("Fixed API timeout", session_id="s1", tags=["error", "fix"])
    mem.store("DB pool config", session_id="s2", tags=["config"])

    injection = mem.inject("API timeout", injection_mode="mag", max_tokens=1000)
    assert "Memory Signals" in injection
    assert "Fixed API timeout" in injection


def test_sdk_inject_empty():
    from vibe_memory import VibeMemory
    mem = VibeMemory(agent_id="test", db_path=":memory:", embedding_backend="tfidf")
    injection = mem.inject("API timeout", injection_mode="mac")
    assert "no relevant memories" in injection


# ── SessionManager integration ──

def test_session_manager_injection_mode(tmp_path):
    from vibe_memory.cli.session_manager import SessionManager
    mgr = SessionManager(
        agent_id="test",
        vibe_dir=str(tmp_path / ".vibe"),
        injection_mode="mag",
    )
    assert mgr.injection_mode == "mag"


def test_session_manager_default_mag(tmp_path):
    from vibe_memory.cli.session_manager import SessionManager
    mgr = SessionManager(
        agent_id="test",
        vibe_dir=str(tmp_path / ".vibe"),
    )
    # Default should be "mag"
    assert mgr.injection_mode == "mag"


def test_session_manager_mac_injection(tmp_path):
    from vibe_memory.cli.session_manager import SessionManager
    mgr = SessionManager(
        agent_id="test",
        vibe_dir=str(tmp_path / ".vibe"),
        injection_mode="mac",
        embedding_backend="tfidf",
    )
    # Store some atoms
    mgr.mem.store("Fixed API timeout", session_id="s1", tags=["error"])
    mgr.mem.store("DB pool config", session_id="s2", tags=["config"])

    # Start session — should inject with MAC
    result = mgr.start_session(context="API timeout")
    assert result["memories_count"] >= 1

    # Check injection file (use utf-8 to handle emoji)
    content = mgr.inject_file.read_text(encoding="utf-8")
    assert "Memory-Augmented Context" in content


def test_session_manager_mag_injection(tmp_path):
    from vibe_memory.cli.session_manager import SessionManager
    mgr = SessionManager(
        agent_id="test",
        vibe_dir=str(tmp_path / ".vibe"),
        injection_mode="mag",
        embedding_backend="tfidf",
    )
    mgr.mem.store("Fixed API timeout", session_id="s1", tags=["error"])
    mgr.mem.store("DB pool config", session_id="s2", tags=["config"])

    result = mgr.start_session(context="API timeout")
    assert result["memories_count"] >= 1

    content = mgr.inject_file.read_text(encoding="utf-8")
    assert "Memory Signals" in content