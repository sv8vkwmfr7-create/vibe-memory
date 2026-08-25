"""
Tests for VibeMemory MCP Server.

Tests JSON-RPC 2.0 protocol over subprocess stdio:
- initialize, tools/list, tools/call, ping
- vibe_store, vibe_recall, vibe_session_start, vibe_session_end
- vibe_stats, vibe_link, vibe_forget, vibe_flush
- Error handling: unknown tool, invalid arguments
- Multiple rounds of store→recall→session lifecycle
"""

import json
import subprocess
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixtures ──

class MCPClient:
    """Test client for MCP server via subprocess."""

    def __init__(self, db_path=":memory:", agent_id="test-agent"):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "vibe_memory.mcp_server",
             "--db-path", db_path, "--agent-id", agent_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self._id = 0

    def send(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline().strip())

    def call_tool(self, name, arguments=None):
        return self.send("tools/call", {"name": name, "arguments": arguments or {}})

    def get_text(self, response):
        return json.loads(response["result"]["content"][0]["text"])

    def close(self):
        self.proc.terminate()
        self.proc.wait()


@pytest.fixture
def client():
    c = MCPClient()
    # Initialize first
    c.send("initialize", {})
    yield c
    c.close()


# ── Protocol ──

def test_initialize(client):
    r = client.send("initialize", {})
    assert r["result"]["serverInfo"]["name"] == "vibe-memory"
    assert r["result"]["serverInfo"]["version"] == "0.3.0"
    assert "tools" in r["result"]["capabilities"]


def test_ping(client):
    r = client.send("ping", {})
    assert "error" not in r


def test_tools_list(client):
    r = client.send("tools/list", {})
    tools = {t["name"] for t in r["result"]["tools"]}
    assert "vibe_store" in tools
    assert "vibe_recall" in tools
    assert "vibe_session_start" in tools
    assert "vibe_session_end" in tools
    assert "vibe_stats" in tools
    assert "vibe_link" in tools
    assert "vibe_forget" in tools
    assert "vibe_flush" in tools
    assert len(r["result"]["tools"]) == 8


def test_unknown_method(client):
    r = client.send("nonexistent", {})
    assert r["error"]["code"] == -32601


def test_unknown_tool(client):
    r = client.call_tool("nonexistent_tool")
    assert r["error"]["code"] == -32601


# ── vibe_store ──

def test_store_basic(client):
    r = client.call_tool("vibe_store", {"content": "Fixed API timeout"})
    data = client.get_text(r)
    assert data["message"] == "Memory stored successfully"
    assert len(data["id"]) > 0


def test_store_with_tags(client):
    r = client.call_tool("vibe_store", {
        "content": "Fixed API timeout",
        "tags": ["bug", "api", "fix"],
    })
    data = client.get_text(r)
    assert "bug" in data["tags"]


def test_store_with_summary(client):
    r = client.call_tool("vibe_store", {
        "content": "Fixed API timeout from 30s to 60s",
        "summary": "API timeout fix",
    })
    data = client.get_text(r)
    assert "API timeout" in data["summary"]


# ── vibe_recall ──

def test_recall_basic(client):
    client.call_tool("vibe_store", {"content": "Fixed API timeout", "tags": ["bug"]})
    r = client.call_tool("vibe_recall", {"query": "API timeout"})
    data = client.get_text(r)
    assert data["count"] >= 1


def test_recall_mode(client):
    client.call_tool("vibe_store", {"content": "Fixed API timeout", "tags": ["bug"]})
    r = client.call_tool("vibe_recall", {"query": "API timeout", "mode": "precision"})
    data = client.get_text(r)
    assert data["mode"] == "precision"


def test_recall_empty(client):
    r = client.call_tool("vibe_recall", {"query": "nonexistent query xyz"})
    data = client.get_text(r)
    assert data["count"] == 0


def test_recall_with_trace(client):
    client.call_tool("vibe_store", {"content": "Fixed API timeout", "tags": ["bug", "api"]})
    client.call_tool("vibe_store", {"content": "Connection pool fix", "tags": ["bug", "db"]})
    r = client.call_tool("vibe_recall", {"query": "timeout", "mode": "recall"})
    data = client.get_text(r)
    assert "relationships" in data


# ── vibe_session_start ──

def test_session_start(client):
    client.call_tool("vibe_store", {"content": "Previous session memory", "tags": ["test"]})
    r = client.call_tool("vibe_session_start", {"context": "Previous session"})
    data = client.get_text(r)
    assert data["memories_recalled"] >= 1
    assert len(data["session_id"]) > 0


def test_session_start_no_context(client):
    r = client.call_tool("vibe_session_start", {})
    data = client.get_text(r)
    assert len(data["session_id"]) > 0


# ── vibe_session_end ──

def test_session_end_basic(client):
    client.call_tool("vibe_session_start", {"context": "test"})
    r = client.call_tool("vibe_session_end", {
        "summary": "Fixed API timeout bug",
        "highlights": ["timeout changed to 60s"],
    })
    data = client.get_text(r)
    assert data["stored"] >= 1


def test_session_end_no_highlights(client):
    client.call_tool("vibe_session_start", {"context": "test"})
    r = client.call_tool("vibe_session_end", {"summary": "Did some work"})
    data = client.get_text(r)
    assert data["stored"] >= 1


def test_session_end_multiple_highlights(client):
    client.call_tool("vibe_session_start", {"context": "test"})
    r = client.call_tool("vibe_session_end", {
        "summary": "Fixed bugs",
        "highlights": ["highlight 1", "highlight 2", "highlight 3"],
    })
    data = client.get_text(r)
    assert data["stored"] >= 4  # 1 summary + 3 highlights


# ── vibe_stats ──

def test_stats_empty(client):
    r = client.call_tool("vibe_stats", {})
    data = client.get_text(r)
    assert "total_atoms" in data
    assert "total_edges" in data


def test_stats_after_store(client):
    client.call_tool("vibe_store", {"content": "Test memory"})
    client.call_tool("vibe_store", {"content": "Another memory"})
    r = client.call_tool("vibe_stats", {})
    data = client.get_text(r)
    assert data["total_atoms"] >= 2


# ── vibe_link ──

def test_link_basic(client):
    r1 = client.call_tool("vibe_store", {"content": "Memory A", "tags": ["test"]})
    a1 = client.get_text(r1)
    r2 = client.call_tool("vibe_store", {"content": "Memory B", "tags": ["test"]})
    a2 = client.get_text(r2)

    r = client.call_tool("vibe_link", {
        "from_id": a1["id"],
        "to_id": a2["id"],
        "label": "causal",
    })
    data = client.get_text(r)
    assert "edge" in data["message"].lower() or "created" in data["message"].lower()


def test_link_invalid_ids(client):
    r = client.call_tool("vibe_link", {
        "from_id": "nonexistent",
        "to_id": "also_fake",
        "label": "causal",
    })
    data = client.get_text(r)
    assert "error" in data


# ── vibe_forget ──

def test_forget_existing(client):
    r = client.call_tool("vibe_store", {"content": "To be deleted"})
    data = client.get_text(r)
    atom_id = data["id"]

    r = client.call_tool("vibe_forget", {"atom_id": atom_id})
    data = client.get_text(r)
    assert data["deleted"] is True


def test_forget_nonexistent(client):
    r = client.call_tool("vibe_forget", {"atom_id": "nonexistent"})
    data = client.get_text(r)
    assert data["deleted"] is False


# ── vibe_flush ──

def test_flush_empty(client):
    r = client.call_tool("vibe_flush", {})
    data = client.get_text(r)
    assert data["edges_created"] == 0


# ── Full lifecycle ──

def test_full_lifecycle(client):
    """Full session lifecycle: start → store → recall → link → end → recall again"""
    # Start session
    r = client.call_tool("vibe_session_start", {"context": "API timeout debugging"})
    start = client.get_text(r)
    assert start["memories_recalled"] >= 0

    # Store memories
    client.call_tool("vibe_store", {
        "content": "Fixed API timeout, changed from 30s to 60s",
        "tags": ["bug", "api", "fix"],
    })
    client.call_tool("vibe_store", {
        "content": "After timeout fix, connection pool exhausted",
        "tags": ["bug", "db", "fix"],
    })

    # Recall
    r = client.call_tool("vibe_recall", {"query": "API timeout"})
    data = client.get_text(r)
    assert data["count"] >= 1

    # Link
    results = data["memories"]
    if len(results) >= 2:
        r = client.call_tool("vibe_link", {
            "from_id": results[0]["id"],
            "to_id": results[1]["id"],
            "label": "causal",
        })

    # End session
    r = client.call_tool("vibe_session_end", {
        "summary": "Fixed API timeout and follow-up pool issue",
        "highlights": ["timeout 30→60s", "pool size increased"],
    })
    end = client.get_text(r)
    assert end["stored"] >= 3  # 1 summary + 2 highlights

    # Stats
    r = client.call_tool("vibe_stats", {})
    stats = client.get_text(r)
    assert stats["total_atoms"] >= 5  # 2 stores + 3 from session end
    assert stats["store_count"] >= 5

    # Recall again — should still find everything
    r = client.call_tool("vibe_recall", {"query": "API timeout"})
    data = client.get_text(r)
    assert data["count"] >= 1

    # Forget one
    r = client.call_tool("vibe_forget", {"atom_id": results[0]["id"]})
    forget_data = client.get_text(r)
    assert forget_data["deleted"] is True


# ── Multiple clients ──

def test_multiple_clients_independent():
    """Two clients with different DBs should be independent."""
    c1 = MCPClient(db_path=":memory:", agent_id="agent-1")
    c2 = MCPClient(db_path=":memory:", agent_id="agent-2")
    c1.send("initialize", {})
    c2.send("initialize", {})

    c1.call_tool("vibe_store", {"content": "Agent 1 memory"})
    c2.call_tool("vibe_store", {"content": "Agent 2 memory"})

    r1 = c1.call_tool("vibe_stats", {})
    r2 = c2.call_tool("vibe_stats", {})
    assert json.loads(r1["result"]["content"][0]["text"])["total_atoms"] == 1
    assert json.loads(r2["result"]["content"][0]["text"])["total_atoms"] == 1

    c1.close()
    c2.close()


# ── Edge cases ──

def test_store_empty_content(client):
    r = client.call_tool("vibe_store", {"content": ""})
    data = client.get_text(r)
    assert data["message"] == "Memory stored successfully"  # Should not crash


def test_recall_empty_query(client):
    r = client.call_tool("vibe_recall", {"query": ""})
    data = client.get_text(r)
    assert "count" in data  # Should not crash


def test_session_end_without_start(client):
    r = client.call_tool("vibe_session_end", {"summary": "No session started"})
    data = client.get_text(r)
    assert data["stored"] >= 1  # Should auto-generate session ID


def test_missing_required_arguments(client):
    r = client.call_tool("vibe_store", {})
    # Should get an error about missing 'content'
    assert "error" in r or "content" in json.dumps(r).lower()