"""
Session Manager Tests

Verifies:
  1. SessionManager: init, creates .vibe directory
  2. start_session: creates session file, writes injection
  3. start_session: recalls zero memories on empty DB
  4. start_session: recalls stored memories
  5. start_session: with context
  6. end_session: stores summary as atom
  7. end_session: stores highlights
  8. end_session: marks session as ended
  9. end_session: no active session error
  10. recall: ad-hoc query
  11. stats: includes session and memory data
  12. quick_start: convenience function
  13. quick_end: convenience function
  14. Session state persists across restarts
  15. Injection file content format
  16. Multiple session cycle
  17. Cross-session memory recall
  18. Tags propagation
  19. CLI: start command
  20. CLI: end command
  21. CLI: recall command
  22. CLI: stats command
  23. CLI: inject command
  24. CLI: env var overrides
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import pytest

from vibe_memory.cli.session_manager import SessionManager, quick_start, quick_end
from vibe_memory.cli.main import main as cli_main


# --- Helpers ---

@pytest.fixture
def temp_vibe_dir():
    """Create temporary .vibe directory."""
    tmp = tempfile.mkdtemp(prefix="vibe-test-")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def session_manager(temp_vibe_dir):
    """Create a SessionManager with temp directory."""
    return SessionManager(
        agent_id="test-agent",
        vibe_dir=temp_vibe_dir,
        embedding_backend="tfidf",
    )


# --- 1. Init ---

def test_session_manager_init(temp_vibe_dir):
    """Test: SessionManager creates .vibe directory"""
    mgr = SessionManager(agent_id="test-agent", vibe_dir=temp_vibe_dir)
    assert os.path.isdir(temp_vibe_dir)
    assert mgr.agent_id == "test-agent"
    assert mgr.session_file.name == "session.json"
    assert mgr.inject_file.name == "inject.md"
    print("[PASS] session_manager_init")


# --- 2. start_session ---

def test_start_session_empty(session_manager, temp_vibe_dir):
    """Test: start_session with empty DB creates session"""
    result = session_manager.start_session()

    assert "session_id" in result
    assert result["previous_session_id"] is None
    assert result["memories_count"] == 0

    # Check session file
    assert os.path.exists(os.path.join(temp_vibe_dir, "session.json"))
    with open(os.path.join(temp_vibe_dir, "session.json"), encoding="utf-8") as f:
        state = json.load(f)
    assert state["session_id"] == result["session_id"]
    assert state["agent_id"] == "test-agent"
    print("[PASS] start_session_empty")


def test_start_session_writes_injection(session_manager, temp_vibe_dir):
    """Test: start_session writes injection file"""
    session_manager.start_session()

    inject_path = os.path.join(temp_vibe_dir, "inject.md")
    assert os.path.exists(inject_path)

    content = open(inject_path, encoding="utf-8").read()
    assert "VibeMemory" in content
    print("[PASS] start_session_writes_injection")


def test_start_session_with_context(session_manager, temp_vibe_dir):
    """Test: start_session accepts context string"""
    result = session_manager.start_session(context="Working on API timeout bug")

    assert result["memories_count"] == 0  # empty DB
    with open(os.path.join(temp_vibe_dir, "session.json"), encoding="utf-8") as f:
        state = json.load(f)
    assert "API timeout" in state["context"]
    print("[PASS] start_session_with_context")


def test_start_session_recalls_stored_memories(session_manager, temp_vibe_dir):
    """Test: start_session recalls memories from previous sessions"""
    # Store some memories first
    session_manager.mem.store(
        "API timeout error investigation: increased timeout from 30s to 60s",
        session_id="prev-session-1",
        tags=["api", "error", "timeout"],
    )
    session_manager.mem.store(
        "Database connection pool exhausted after API timeout fix",
        session_id="prev-session-1",
        tags=["database", "error"],
    )
    session_manager.mem.store(
        "CSS flexbox layout broken in Safari",
        session_id="prev-session-2",
        tags=["frontend", "css", "bug"],
    )

    # Start new session with API-related context
    result = session_manager.start_session(context="API timeout issue")

    assert result["memories_count"] > 0
    print("[PASS] start_session_recalls_stored_memories")


# --- 3. end_session ---

def test_end_session_stores_summary(session_manager, temp_vibe_dir):
    """Test: end_session stores summary as memory atom"""
    session_manager.start_session()
    result = session_manager.end_session(
        summary="Fixed API timeout: increased to 60s with retry logic",
    )

    assert result["stored_count"] == 1
    assert "ended_at" in result

    # Verify atom was stored
    atoms = session_manager.mem.storage.get_atoms_by_agent("test-agent")
    assert len(atoms) == 1
    assert "Fixed API timeout" in atoms[0].content
    print("[PASS] end_session_stores_summary")


def test_end_session_stores_highlights(session_manager, temp_vibe_dir):
    """Test: end_session stores highlights"""
    session_manager.start_session()
    result = session_manager.end_session(
        summary="Refactored auth module",
        highlights=[
            "JWT expiry extended to 24h",
            "Rate limit bypass fixed",
            "Added OAuth2 fallback",
        ],
    )

    assert result["stored_count"] == 4  # 1 summary + 3 highlights
    atoms = session_manager.mem.storage.get_atoms_by_agent("test-agent")
    assert len(atoms) == 4
    print("[PASS] end_session_stores_highlights")


def test_end_session_marks_ended(session_manager, temp_vibe_dir):
    """Test: end_session marks session as ended"""
    session_manager.start_session()
    session_manager.end_session(summary="Test summary")

    with open(os.path.join(temp_vibe_dir, "session.json"), encoding="utf-8") as f:
        state = json.load(f)
    assert "ended_at" in state
    print("[PASS] end_session_marks_ended")


def test_end_session_no_active(session_manager, temp_vibe_dir):
    """Test: end_session with no active session"""
    # No start_session called
    result = session_manager.end_session(summary="Should fail")
    assert "error" in result
    assert result["stored_count"] == 0
    print("[PASS] end_session_no_active")


def test_end_session_with_tags(session_manager, temp_vibe_dir):
    """Test: end_session propagates tags"""
    session_manager.start_session()
    session_manager.end_session(
        summary="Deployed v2.1",
        tags=["deployment", "release"],
    )

    atoms = session_manager.mem.storage.get_atoms_by_agent("test-agent")
    assert len(atoms) == 1
    assert "deployment" in atoms[0].tags
    print("[PASS] end_session_with_tags")


# --- 4. recall ---

def test_recall(session_manager, temp_vibe_dir):
    """Test: ad-hoc recall returns results"""
    session_manager.mem.store(
        "API timeout bug: fixed by increasing timeout",
        session_id="s1",
        tags=["api", "bug"],
    )

    result = session_manager.recall("API timeout")
    assert len(result["atoms"]) > 0
    print("[PASS] recall")


# --- 5. stats ---

def test_stats(session_manager, temp_vibe_dir):
    """Test: stats includes session and memory data"""
    session_manager.start_session()
    session_manager.mem.store("Test memory", session_id="s1")

    stats = session_manager.stats()
    assert "session" in stats
    assert "memory" in stats
    assert stats["memory"]["total_atoms"] == 1
    print("[PASS] stats")


# --- 6. Convenience functions ---

def test_quick_start(temp_vibe_dir):
    """Test: quick_start creates manager and starts session"""
    mgr = quick_start(agent_id="test-agent", vibe_dir=temp_vibe_dir)
    assert isinstance(mgr, SessionManager)
    assert os.path.exists(os.path.join(temp_vibe_dir, "session.json"))
    print("[PASS] quick_start")


def test_quick_end(temp_vibe_dir):
    """Test: quick_end stores summary"""
    mgr = quick_start(agent_id="test-agent", vibe_dir=temp_vibe_dir)
    result = quick_end(agent_id="test-agent", vibe_dir=temp_vibe_dir, summary="Test done")
    assert result["stored_count"] == 1
    print("[PASS] quick_end")


# --- 7. Persistence ---

def test_session_state_persists(temp_vibe_dir):
    """Test: session state persists across manager instances"""
    mgr1 = SessionManager(agent_id="test-agent", vibe_dir=temp_vibe_dir)
    result1 = mgr1.start_session()

    # New instance should read previous state
    mgr2 = SessionManager(agent_id="test-agent", vibe_dir=temp_vibe_dir)
    state = mgr2._read_session_state()
    assert state["session_id"] == result1["session_id"]
    print("[PASS] session_state_persists")


def test_multiple_session_cycle(session_manager, temp_vibe_dir):
    """Test: multiple session start/end cycle"""
    results = []
    for i in range(3):
        r = session_manager.start_session(context=f"Task {i}")
        session_manager.end_session(summary=f"Completed task {i}")
        results.append(r)

    assert len(results) == 3
    # Each should have previous_session_id set
    assert results[1]["previous_session_id"] == results[0]["session_id"]
    assert results[2]["previous_session_id"] == results[1]["session_id"]

    # All 3 sessions stored
    atoms = session_manager.mem.storage.get_atoms_by_agent("test-agent")
    assert len(atoms) == 3
    print("[PASS] multiple_session_cycle")


# --- 8. Cross-session recall ---

def test_cross_session_recall(session_manager, temp_vibe_dir):
    """Test: memories from previous sessions are recalled"""
    # Session 1: store API fix
    session_manager.start_session(context="API timeout bug")
    session_manager.end_session(summary="Fixed API timeout: increased from 30s to 60s")

    # Session 2: store different topic
    session_manager.start_session(context="CSS layout bug")
    session_manager.end_session(summary="Fixed Safari flexbox bug with -webkit prefix")

    # Session 3: recall API-related
    result = session_manager.start_session(context="API timeout issue again")

    assert result["memories_count"] > 0
    # Should recall session 1's API fix
    atoms = session_manager.mem.storage.get_atoms_by_agent("test-agent")
    assert len(atoms) == 2
    print("[PASS] cross_session_recall")


# --- 9. Injection format ---

def test_injection_format(session_manager, temp_vibe_dir):
    """Test: injection file has correct format"""
    session_manager.mem.store(
        "API timeout investigation: increased timeout to 60s",
        session_id="s1",
        tags=["api", "error"],
    )
    session_manager.mem.store(
        "Database pool exhausted",
        session_id="s1",
        tags=["database"],
    )

    session_manager.start_session(context="API timeout")
    content = open(os.path.join(temp_vibe_dir, "inject.md"), encoding="utf-8").read()

    assert "VibeMemory" in content
    assert "Memory Signals" in content  # MAG default injection mode
    assert "Session" not in content  # MAG groups by priority, not session
    print("[PASS] injection_format")


# --- 10. CLI ---

def test_cli_start(temp_vibe_dir, monkeypatch):
    """Test: CLI start command"""
    monkeypatch.setattr(sys, "argv", ["vibe-session", "start"])
    monkeypatch.setenv("VIBE_DIR", temp_vibe_dir)
    monkeypatch.setenv("VIBE_AGENT_ID", "cli-test")

    # Should not crash
    cli_main()
    assert os.path.exists(os.path.join(temp_vibe_dir, "session.json"))
    print("[PASS] cli_start")


def test_cli_end(temp_vibe_dir, monkeypatch):
    """Test: CLI end command"""
    monkeypatch.setenv("VIBE_DIR", temp_vibe_dir)
    monkeypatch.setenv("VIBE_AGENT_ID", "cli-test")

    # Start first
    monkeypatch.setattr(sys, "argv", ["vibe-session", "start"])
    cli_main()

    # End
    monkeypatch.setattr(sys, "argv", [
        "vibe-session", "end",
        "--summary", "Test completed",
        "--highlight", "Fixed bug",
    ])
    cli_main()

    with open(os.path.join(temp_vibe_dir, "session.json"), encoding="utf-8") as f:
        state = json.load(f)
    assert "ended_at" in state
    print("[PASS] cli_end")


def test_cli_recall(temp_vibe_dir, monkeypatch):
    """Test: CLI recall command"""
    monkeypatch.setenv("VIBE_DIR", temp_vibe_dir)
    monkeypatch.setenv("VIBE_AGENT_ID", "cli-test")

    # Store a memory first
    mgr = SessionManager(agent_id="cli-test", vibe_dir=temp_vibe_dir)
    mgr.mem.store("API timeout fix", session_id="s1", tags=["api"])

    monkeypatch.setattr(sys, "argv", ["vibe-session", "recall", "API timeout"])
    cli_main()
    print("[PASS] cli_recall")


def test_cli_stats(temp_vibe_dir, monkeypatch):
    """Test: CLI stats command"""
    monkeypatch.setenv("VIBE_DIR", temp_vibe_dir)
    monkeypatch.setenv("VIBE_AGENT_ID", "cli-test")

    mgr = SessionManager(agent_id="cli-test", vibe_dir=temp_vibe_dir)
    mgr.start_session()
    mgr.mem.store("Test memory", session_id="cli-s1")

    monkeypatch.setattr(sys, "argv", ["vibe-session", "stats"])
    cli_main()
    print("[PASS] cli_stats")


def test_cli_inject(temp_vibe_dir, monkeypatch):
    """Test: CLI inject command"""
    monkeypatch.setenv("VIBE_DIR", temp_vibe_dir)
    monkeypatch.setenv("VIBE_AGENT_ID", "cli-test")

    mgr = SessionManager(agent_id="cli-test", vibe_dir=temp_vibe_dir)
    mgr.start_session()

    monkeypatch.setattr(sys, "argv", ["vibe-session", "inject"])
    cli_main()
    print("[PASS] cli_inject")


def test_cli_env_var_override(temp_vibe_dir, monkeypatch):
    """Test: CLI respects VIBE_DIR and VIBE_AGENT_ID env vars"""
    custom_dir = os.path.join(temp_vibe_dir, "custom")
    monkeypatch.setenv("VIBE_DIR", custom_dir)
    monkeypatch.setenv("VIBE_AGENT_ID", "custom-agent")

    monkeypatch.setattr(sys, "argv", ["vibe-session", "start"])
    cli_main()

    assert os.path.exists(os.path.join(custom_dir, "session.json"))
    with open(os.path.join(custom_dir, "session.json"), encoding="utf-8") as f:
        state = json.load(f)
    assert state["agent_id"] == "custom-agent"
    print("[PASS] cli_env_var_override")


# --- Run all ---

if __name__ == "__main__":
    tests = [
        test_session_manager_init,
        test_start_session_empty,
        test_start_session_writes_injection,
        test_start_session_with_context,
        test_start_session_recalls_stored_memories,
        test_end_session_stores_summary,
        test_end_session_stores_highlights,
        test_end_session_marks_ended,
        test_end_session_no_active,
        test_end_session_with_tags,
        test_recall,
        test_stats,
        test_quick_start,
        test_quick_end,
        test_session_state_persists,
        test_multiple_session_cycle,
        test_cross_session_recall,
        test_injection_format,
        test_cli_start,
        test_cli_end,
        test_cli_recall,
        test_cli_stats,
        test_cli_inject,
        test_cli_env_var_override,
    ]

    passed = 0
    for test in tests:
        try:
            # Create temp dir for each test
            tmp = tempfile.mkdtemp(prefix="vibe-test-")
            if "cli_" in test.__name__:
                # CLI tests need monkeypatch
                import pytest
                pytest.skip("Run with pytest for CLI tests")
            test(tmp)
            passed += 1
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{passed}/{len(tests)} tests passed")