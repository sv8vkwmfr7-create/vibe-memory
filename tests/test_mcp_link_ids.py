"""Link ID resolution through real MCP stdio and synthetic SDK stores."""

import pytest

from test_mcp_enhancement import exchange, payload
from vibe_memory import VibeMemory


@pytest.fixture
def link_ids(tmp_path, monkeypatch):
    ids = (
        "11111111-0000-0000-0000-000000000001",
        "11111111-0000-0000-0000-000000000002",
        "22222222-0000-0000-0000-000000000003",
    )
    mem = VibeMemory(agent_id="mcp-agent", db_path=str(tmp_path / "memory.db"),
                     embedding_backend="tfidf")
    try:
        with monkeypatch.context() as patch:
            fixed_ids = iter(ids)
            patch.setattr("uuid.uuid4", lambda: next(fixed_ids))
            for index in range(3):
                mem.store(f"合成连接证据{index}", session_id=f"link-session-{index}",
                          auto_build_edges=False, auto_episode=False)
    finally:
        mem.storage.conn.close()
    return ids


@pytest.mark.parametrize("ambiguous_endpoint", ["from_id", "to_id"])
def test_link_rejects_ambiguous_prefix_without_writing_edge(tmp_path, link_ids,
                                                          ambiguous_endpoint):
    arguments = {"from_id": link_ids[2], "to_id": link_ids[0], "label": "causal"}
    arguments[ambiguous_endpoint] = "11111111"
    replies = exchange(tmp_path, [("vibe_link", arguments), ("vibe_stats", {})])
    assert "error" in replies[0], replies[0]
    assert replies[0]["error"]["code"] == -32000
    assert "ambiguous" in replies[0]["error"]["message"].lower()
    assert payload(replies[1])["total_edges"] == 0


@pytest.mark.parametrize("source_index,target_index,short_endpoint", [
    (0, 1, None), (0, 2, None), (1, 2, "to_id"),
    (2, 0, "from_id"), (2, 1, "from_id"),
])
def test_link_keeps_full_ids_and_unique_eight_character_ids(tmp_path, link_ids,
                                                         source_index, target_index,
                                                         short_endpoint):
    source, target = link_ids[source_index], link_ids[target_index]
    arguments = {"from_id": source, "to_id": target, "label": "causal"}
    if short_endpoint:
        arguments[short_endpoint] = arguments[short_endpoint][:8]
    replies = exchange(tmp_path, [("vibe_link", arguments), ("vibe_stats", {}),
                                 ("vibe_recall", {"query": "合成连接证据", "top_k": 10})])
    assert payload(replies[0])["message"] == "Edge created successfully"
    assert payload(replies[1])["total_edges"] == 1
    # Recall traces can be reversed; verify endpoint identity, not causal direction.
    assert {frozenset((trace["from"], trace["to"]))
            for trace in payload(replies[2])["relationships"]} == {frozenset((source, target))}


def test_link_prefers_exact_eight_character_id_over_longer_prefixes(tmp_path,
                                                                 link_ids, monkeypatch):
    mem = VibeMemory(agent_id="mcp-agent", db_path=str(tmp_path / "memory.db"),
                     embedding_backend="tfidf")
    try:
        with monkeypatch.context() as patch:
            patch.setattr("uuid.uuid4", lambda: "11111111")
            mem.store("合成连接证据精确短ID", session_id="exact-id-session",
                      auto_build_edges=False, auto_episode=False)
    finally:
        mem.storage.conn.close()
    replies = exchange(tmp_path, [
        ("vibe_link", {"from_id": "11111111", "to_id": link_ids[2], "label": "causal"}),
        ("vibe_recall", {"query": "合成连接证据", "top_k": 10}),
    ])
    assert payload(replies[0])["message"] == "Edge created successfully"
    assert {frozenset((trace["from"], trace["to"]))
            for trace in payload(replies[1])["relationships"]} == {
                frozenset(("11111111", link_ids[2]))}


@pytest.mark.parametrize("owner", [
    {"agent_id": "other-agent"}, {"agent_id": "mcp-agent", "tenant_id": "other-tenant"},
])
def test_link_prefix_resolution_stays_within_tenant_and_agent(tmp_path, link_ids,
                                                            monkeypatch, owner):
    foreign_id = "22222222-0000-0000-0000-000000000004"
    mem = VibeMemory(**owner, db_path=str(tmp_path / "memory.db"), embedding_backend="tfidf")
    try:
        with monkeypatch.context() as patch:
            patch.setattr("uuid.uuid4", lambda: foreign_id)
            mem.store("合成连接证据外部所有者", session_id="foreign-session",
                      auto_build_edges=False, auto_episode=False)
    finally:
        mem.storage.conn.close()
    replies = exchange(tmp_path, [
        ("vibe_link", {"from_id": link_ids[0], "to_id": "22222222", "label": "causal"}),
        ("vibe_link", {"from_id": foreign_id, "to_id": link_ids[0], "label": "causal"}),
        ("vibe_link", {"from_id": link_ids[0], "to_id": foreign_id, "label": "causal"}),
        ("vibe_stats", {}),
        ("vibe_recall", {"query": "合成连接证据", "top_k": 10}),
    ])
    assert payload(replies[0])["message"] == "Edge created successfully"
    assert "error" in payload(replies[1]) and "error" in payload(replies[2])
    assert payload(replies[3])["total_edges"] == 1
    assert {frozenset((trace["from"], trace["to"]))
            for trace in payload(replies[4])["relationships"]} == {
                frozenset((link_ids[0], link_ids[2]))}


@pytest.mark.parametrize("invalid_id", ["", "1111111", "11111111-0", "99999999"])
def test_link_invalid_ids_do_not_write_edges(tmp_path, link_ids, invalid_id):
    replies = exchange(tmp_path, [
        ("vibe_link", {"from_id": link_ids[2], "to_id": invalid_id, "label": "causal"}),
        ("vibe_stats", {}),
    ])
    assert "error" in payload(replies[0])
    assert payload(replies[1])["total_edges"] == 0
