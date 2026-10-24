"""Safe relation review through a real public MCP stdio process."""
from contextlib import contextmanager
from dataclasses import replace
import json
import sys

import pytest

from vibe_memory import VibeMemory
from vibe_memory.doctor import DoctorError, MCPProcess
from vibe_memory.models.memory_atom import EdgeLabel, EdgeSource, EdgeStatus, GraphPartition


@pytest.fixture
def records(tmp_path):
    path = str(tmp_path / "review.db")
    with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as memory:
        first = memory.store("Order timeout was investigated.", session_id="first",
                             auto_build_edges=False, auto_episode=False,
                             context_before="Earlier incident", context_after="Later incident")
        second = memory.store("Order timeout needs another investigation.", session_id="second",
                              auto_build_edges=False, auto_episode=False)
    return path, first, second


@contextmanager
def server(path):
    client = MCPProcess(path, "mcp-review", 10, sys.executable)
    try:
        client.request("initialize")
        yield client
    finally:
        client.close()


def test_mcp_prepare_exposes_full_owned_evidence(records):
    path, first, second = records
    with server(path) as client:
        tools = {tool["name"]: tool for tool in client.request("tools/list")["tools"]}
        assert "vibe_prepare_relation_review" in tools
        schema = tools["vibe_prepare_relation_review"]["inputSchema"]
        assert set(schema["required"]) == {"from_id", "to_id"}
        assert schema["additionalProperties"] is False
        review = client.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        assert review["from"]["id"] == first.id
        assert review["from"]["content"] == first.content
        assert review["from"]["context_before"] == "Earlier incident"
        assert review["from"]["context_after"] == "Later incident"
        assert review["to"]["content"] == second.content
        assert review["semantic_verified"] is False
        assert review["decision_origin"] == "caller_assertion"
    with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as memory:
        assert memory.storage.get_all_edges_raw() == []


@pytest.mark.parametrize("decision", ["accept", "reject", "uncertain"])
def test_mcp_apply_reports_real_effect_and_consumes_review(records, decision):
    path, first, second = records
    with server(path) as client:
        tools = {tool["name"]: tool for tool in client.request("tools/list")["tools"]}
        assert "vibe_apply_relation_review" in tools
        schema = tools["vibe_apply_relation_review"]["inputSchema"]
        assert set(schema["required"]) == {"review_id", "decision"}
        assert schema["properties"]["decision"]["enum"] == ["accept", "reject", "uncertain"]
        assert schema["additionalProperties"] is False
        review = client.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        arguments = {"review_id": review["review_id"], "decision": decision,
                     "from_quote": "Order timeout", "to_quote": "Order timeout"}
        result = client.call_tool("vibe_apply_relation_review", arguments)
        assert result["applied"] is (decision == "accept")
        assert result["semantic_verified"] is False
        assert result["decision_origin"] == "caller_assertion"
        assert client.call_tool("vibe_apply_relation_review", dict(arguments, decision="accept"))["applied"] is False
        assert "total_atoms" in client.call_tool("vibe_stats")
    with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as memory:
        edges = memory.storage.get_all_edges_raw()
        assert len(edges) == (1 if decision == "accept" else 0)
        if edges:
            assert edges[0].id == result["edge_id"]
            assert (edges[0].from_atom_id, edges[0].to_atom_id) == (first.id, second.id)
            assert (edges[0].label, edges[0].source) == (EdgeLabel.SIMILAR, EdgeSource.RULE)


def test_mcp_bad_prepare_inputs_do_not_break_following_requests(records):
    path, first, second = records
    invalid = [None, [], "bad", 1, {}, {"from_id": first.id},
               {"from_id": first.id, "to_id": second.id, "extra": "ignored?"},
               {"from_id": None, "to_id": second.id},
               {"from_id": first.id, "to_id": []},
               {"from_id": first.id[:8], "to_id": second.id},
               {"from_id": first.id, "to_id": second.id[:8]},
               {"from_id": first.id, "to_id": first.id}]
    with server(path) as client:
        for arguments in invalid:
            with pytest.raises(DoctorError, match="Tool error"):
                client.request("tools/call", {"name": "vibe_prepare_relation_review", "arguments": arguments})
            assert client.request("ping") == {}
            assert client.call_tool("vibe_stats")["total_edges"] == 0
        review = client.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        assert client.call_tool("vibe_apply_relation_review", {"review_id": review["review_id"],
                                                               "decision": "reject"})["status"] == "reject"


def test_mcp_bad_apply_inputs_keep_review_pending_and_server_usable(records):
    path, first, second = records
    with server(path) as client:
        review = client.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        valid = {"review_id": review["review_id"], "decision": "accept",
                 "from_quote": "Order timeout", "to_quote": "Order timeout"}
        invalid = [None, [], "bad", 1, {}, {"review_id": review["review_id"]},
                   dict(valid, extra="ignored?"), dict(valid, review_id=[]),
                   dict(valid, review_id=None), dict(valid, decision=True),
                   dict(valid, decision="causal"), dict(valid, from_quote=None),
                   dict(valid, to_quote=1), dict(valid, from_quote=""),
                   dict(valid, from_quote="   "), dict(valid, to_quote="not in the body"),
                   {"review_id": review["review_id"], "decision": "accept"}]
        for arguments in invalid:
            with pytest.raises(DoctorError, match="Tool error"):
                client.request("tools/call", {"name": "vibe_apply_relation_review", "arguments": arguments})
            assert client.request("ping") == {}
            assert client.call_tool("vibe_stats")["total_edges"] == 0
        assert client.call_tool("vibe_apply_relation_review", valid)["applied"] is True


@pytest.mark.parametrize("owner", [{"agent_id": "foreign"}, {"tenant_id": "foreign"}])
def test_mcp_prepare_rejects_foreign_endpoints_and_same_session(records, owner):
    path, first, second = records
    arguments = dict(agent_id="mcp-review", db_path=path, embedding_backend="tfidf")
    arguments.update(owner)
    with VibeMemory(**arguments) as foreign:
        outside = foreign.store("Foreign timeout record.", session_id="outside", auto_build_edges=False)
    with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as memory:
        same = memory.store("Another record in first session.", session_id="first", auto_build_edges=False)
    with server(path) as client:
        for from_id, to_id in [(first.id, outside.id), (outside.id, second.id), (first.id, same.id)]:
            with pytest.raises(DoctorError, match="Tool error"):
                client.call_tool("vibe_prepare_relation_review", {"from_id": from_id, "to_id": to_id})
        assert client.call_tool("vibe_stats")["total_edges"] == 0


@pytest.mark.parametrize("field,value", [
    ("content", "Order timeout now has new evidence."),
    ("summary", "Changed conclusion"), ("scope", {"environment": "test"}),
    ("tags", ["changed"]), ("type", GraphPartition.DOCUMENT), ("version", 2),
    ("context_before", "New earlier evidence"), ("context_after", "New later evidence"),
    ("tenant_id", "foreign"), ("agent_id", "foreign"),
])
def test_mcp_apply_rejects_evidence_changed_by_other_connection(records, field, value):
    path, first, second = records
    with server(path) as client:
        review = client.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as writer:
            expected = writer.storage.get_atom(first.id)
            writer.storage.delete_atom(first.id)
            writer.storage.insert_atom(replace(expected, **{field: value}))
            assert getattr(writer.storage.get_atom(first.id), field) == value
            result = client.call_tool("vibe_apply_relation_review", {"review_id": review["review_id"],
                                     "decision": "accept", "from_quote": "Order timeout", "to_quote": "Order timeout"})
            assert result["applied"] is False
            assert writer.storage.get_all_edges_raw() == []


@pytest.mark.parametrize("endpoint", [0, 1])
def test_mcp_apply_rejects_deleted_evidence(records, endpoint):
    path, first, second = records
    with server(path) as client:
        review = client.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as writer:
            assert writer.forget((first, second)[endpoint].id) is True
            assert client.call_tool("vibe_apply_relation_review", {"review_id": review["review_id"],
                                   "decision": "accept", "from_quote": "Order timeout", "to_quote": "Order timeout"})["applied"] is False
            assert writer.storage.get_all_edges_raw() == []


@pytest.mark.parametrize("status", list(EdgeStatus))
def test_mcp_preserves_existing_directed_edges_in_every_status(records, status):
    path, first, second = records
    with server(path) as client:
        review = client.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as writer:
            edge = writer.link(first.id, second.id, label=EdgeLabel.CAUSAL, confidence=0.91, source=EdgeSource.LEARNER)
            edge.status = status
            edge.weight = 0.39
            writer.storage.insert_edge(edge)
            result = client.call_tool("vibe_apply_relation_review", {"review_id": review["review_id"],
                                     "decision": "accept", "from_quote": "Order timeout", "to_quote": "Order timeout"})
            assert result["applied"] is False
            assert writer.storage.get_all_edges_raw() == [edge]


def test_mcp_review_ids_do_not_transfer_to_other_process_or_restart(records):
    path, first, second = records
    with server(path) as original:
        review = original.call_tool("vibe_prepare_relation_review", {"from_id": first.id, "to_id": second.id})
        arguments = {"review_id": review["review_id"], "decision": "accept",
                     "from_quote": "Order timeout", "to_quote": "Order timeout"}
        with server(path) as other:
            assert other.call_tool("vibe_apply_relation_review", arguments)["applied"] is False
    with server(path) as restarted:
        assert restarted.call_tool("vibe_apply_relation_review", arguments)["applied"] is False
        assert restarted.call_tool("vibe_stats")["total_edges"] == 0


def test_mcp_pending_review_limit_does_not_evict_old_reviews(records):
    path, first, second = records
    with server(path) as client:
        arguments = {"from_id": first.id, "to_id": second.id}
        reviews = [client.call_tool("vibe_prepare_relation_review", arguments) for _ in range(32)]
        with pytest.raises(DoctorError, match="32"):
            client.call_tool("vibe_prepare_relation_review", arguments)
        assert client.call_tool("vibe_apply_relation_review", {"review_id": reviews[0]["review_id"],
                                                               "decision": "reject"})["status"] == "reject"
        replacement = client.call_tool("vibe_prepare_relation_review", arguments)
        for review in reviews[1:] + [replacement]:
            assert client.call_tool("vibe_apply_relation_review", {"review_id": review["review_id"],
                                                                   "decision": "uncertain"})["status"] == "uncertain"
        assert client.call_tool("vibe_stats")["total_edges"] == 0


def test_mcp_delivers_whole_payload_at_budget_and_rejects_overflow(records):
    path, first, second = records
    with server(path) as client:
        arguments = {"from_id": first.id, "to_id": second.id}
        old = client.call_tool("vibe_prepare_relation_review", arguments)
        overhead = len(json.dumps(old, ensure_ascii=False))
        with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as writer:
            atom = writer.storage.get_atom(first.id)
            writer.storage.delete_atom(first.id)
            # Replace the existing context so the known JSON payload is exactly 20000 characters.
            padding = 20000 - overhead + len(atom.context_before)
            writer.storage.insert_atom(replace(atom, context_before="界" * padding))
            review = client.call_tool("vibe_prepare_relation_review", arguments)
            assert len(json.dumps(review, ensure_ascii=False)) == 20000
            assert review["from"]["context_before"] == "界" * padding
            writer.storage.delete_atom(first.id)
            writer.storage.insert_atom(replace(atom, context_before="界" * (padding + 1)))
            with pytest.raises(DoctorError, match="20000"):
                client.call_tool("vibe_prepare_relation_review", arguments)
            assert client.call_tool("vibe_apply_relation_review", {"review_id": old["review_id"],
                                                                   "decision": "reject"})["status"] == "reject"
            assert client.call_tool("vibe_stats")["total_edges"] == 0


def test_mcp_legacy_link_and_recall_remain_available(records):
    path, first, second = records
    with server(path) as client:
        client.call_tool("vibe_link", {"from_id": first.id, "to_id": second.id, "label": "causal"})
        client.call_tool("vibe_link", {"from_id": first.id, "to_id": second.id, "label": "similar"})
        assert client.call_tool("vibe_stats")["total_edges"] == 1
        assert first.id in {record["full_id"] for record in client.call_tool("vibe_recall", {"query": "Order timeout"})["memories"]}
    with VibeMemory("mcp-review", db_path=path, embedding_backend="tfidf") as memory:
        edges = memory.storage.get_all_edges_raw()
        assert len(edges) == 1 and edges[0].label == EdgeLabel.SIMILAR
