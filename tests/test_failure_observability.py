import json
import io
import sqlite3
from types import SimpleNamespace

import pytest

from vibe_memory import VibeMemory
from vibe_memory.metrics import MetricsCollector
from vibe_memory.reflect import Reflector
from vibe_memory.retrieval.ppr import recall
from vibe_memory.retrieval import strategies


SECRET = "private query and sk-synthetic-secret"


@pytest.fixture
def memory():
    mem = VibeMemory(agent_id="failures", db_path=":memory:", embedding_backend="tfidf")
    mem.store_batch([{"role": "assistant", "content": f"database timeout investigation {i}"}
                     for i in range(3)])
    yield mem
    mem.storage.conn.close()


def fail(*args, **kwargs):
    raise TimeoutError(SECRET)


@pytest.mark.parametrize("stage,method", [
    ("semantic", None), ("bm25", "BM25Strategy"),
    ("graph", "GraphStrategy"), ("temporal", "TemporalStrategy"),
])
def test_retrieval_failure_visible_without_exception_text(memory, monkeypatch, stage, method):
    if method:
        monkeypatch.setattr(getattr(strategies, method), "search", fail)
    else:
        monkeypatch.setattr(memory.embedding, "search", fail)
    result = recall(SECRET, memory.agent_id, memory.storage, strategies=[stage],
                    embedding_provider=memory.embedding)
    assert result["atoms"] == []
    assert result["failures"] == [{"stage": stage, "reason": "timeout"}]
    assert SECRET not in json.dumps(result)


def test_sdk_partial_retrieval_counts_and_empty_call_has_no_stale_failures(memory, monkeypatch):
    monkeypatch.setattr(memory.embedding, "search", fail)
    result = memory.recall("database timeout")
    assert result["atoms"]
    assert result["failures"] == [{"stage": "semantic", "reason": "timeout"}]
    assert memory.metrics.stats()["degradation"]["retrieval_semantic:timeout"] == 1
    for atom in memory.history():
        memory.storage.delete_atom(atom.id)
    assert memory.recall("nothing")["failures"] == []
    assert memory.metrics.stats()["degradation"]["retrieval_semantic:timeout"] == 1


def test_embedding_cache_failure_preserves_write_and_is_counted(memory, monkeypatch):
    memory.metrics.reset()
    monkeypatch.setattr(memory.embedding, "encode_query", fail)
    atom = memory.store("important new database finding", auto_build_edges=False, auto_episode=False)
    assert memory.storage.get_atom(atom.id).content == atom.content
    assert memory.metrics.stats()["degradation"] == {"embedding_cache:timeout": 1}
    memory.metrics.reset()
    assert memory.metrics.stats()["degradation"] == {}


@pytest.mark.parametrize("method", ["reflect", "reflect_on_topic"])
@pytest.mark.parametrize("kind,stage,reason", [
    ("provider", "reflect_provider", "timeout"),
    ("parse", "reflect_parse", "invalid_data"),
    ("store", "reflect_store", "timeout"),
])
def test_reflect_failure_stages(memory, monkeypatch, method, kind, stage, reason):
    response = {"insights": [{"summary": "safe finding", "detail": "safe detail"}]}
    provider = SimpleNamespace(chat=fail if kind == "provider" else
                               lambda **kwargs: {"content": SECRET if kind == "parse" else json.dumps(response)})
    reflector = Reflector(memory, provider)
    if kind == "store":
        monkeypatch.setattr(memory, "store", fail)
    assert getattr(reflector, method)("database") == []
    assert reflector.stats()["degradation"] == {f"{stage}:{reason}": 1}
    assert SECRET not in json.dumps(reflector.stats())


@pytest.mark.parametrize("content", ['{"insights": []}', '```json\n{"insights": []}\n```',
                                         'prefix {"insights": []} suffix'])
def test_valid_no_insights_is_not_failure(memory, content):
    reflector = Reflector(memory, SimpleNamespace(chat=lambda **kw: {"content": content}))
    assert reflector.reflect() == []
    assert reflector.stats()["degradation"] == {}


@pytest.mark.parametrize("content", ['[]', 'null', '{"insights": null}',
                                         '{"insights": [42]}', '{}'])
def test_malformed_reflect_shape_is_safe_failure(memory, content):
    reflector = Reflector(memory, SimpleNamespace(chat=lambda **kw: {"content": content}))
    assert reflector.reflect() == []
    assert reflector.stats()["degradation"] == {"reflect_parse:invalid_data": 1}


def test_custom_exception_name_and_text_never_become_metric_keys():
    error_type = type(SECRET, (Exception,), {})
    metrics = MetricsCollector()
    assert metrics.record_failure("embedding_cache", error_type(SECRET)) == {
        "stage": "embedding_cache", "reason": "unexpected"}
    assert metrics.stats()["degradation"] == {"embedding_cache:unexpected": 1}


@pytest.mark.parametrize("error,reason", [
    (TimeoutError(SECRET), "timeout"), (ConnectionError(SECRET), "connection"),
    (sqlite3.OperationalError(SECRET), "storage"), (ValueError(SECRET), "invalid_data"),
    (TypeError(SECRET), "invalid_data"), (KeyError(SECRET), "invalid_data"),
    (IndexError(SECRET), "invalid_data"), (OSError(SECRET), "os_error"),
    (RuntimeError(SECRET), "unexpected"),
])
def test_failure_categories_and_unknown_stages_have_fixed_labels(error, reason):
    metrics = MetricsCollector()
    assert metrics.record_failure(SECRET, error) == {"stage": "other", "reason": reason}
    assert metrics.stats()["degradation"] == {f"other:{reason}": 1}


def test_all_strategies_failed_remain_distinct_from_no_matches(memory, monkeypatch):
    monkeypatch.setattr(memory.embedding, "search", fail)
    for strategy in (strategies.BM25Strategy, strategies.GraphStrategy, strategies.TemporalStrategy):
        monkeypatch.setattr(strategy, "search", fail)
    result = memory.recall("database")
    assert result["atoms"] == []
    assert result["failures"] == [{"stage": stage, "reason": "timeout"}
                                  for stage in ("semantic", "bm25", "graph", "temporal")]
    assert memory.metrics.stats()["degradation"] == {
        f"retrieval_{stage}:timeout": 1 for stage in ("semantic", "bm25", "graph", "temporal")}


def test_cache_persistence_failure_counted_after_primary_write(memory, monkeypatch):
    def broken_update(*args, **kwargs):
        raise sqlite3.OperationalError(SECRET)
    monkeypatch.setattr(memory.storage, "update_atom", broken_update)
    atom = memory.store("important database error", auto_build_edges=False, auto_episode=False)
    persisted = memory.storage.get_atom(atom.id)
    assert persisted.content == atom.content
    assert persisted.embedding is None
    assert memory.metrics.stats()["degradation"] == {"embedding_cache:storage": 1}


def test_successful_reflect_insight_stores_without_failure(memory):
    response = {"insights": [{"summary": "safe finding", "detail": "safe detail"}]}
    reflector = Reflector(memory, SimpleNamespace(chat=lambda **kw: {"content": json.dumps(response)}))
    stored = reflector.reflect()
    assert len(stored) == 1
    assert memory.storage.get_atom(stored[0].id).summary == "safe finding"
    assert reflector.stats()["degradation"] == {}


def test_semantic_failure_after_query_encoding_does_not_rerank_partial_state(memory, monkeypatch):
    # Dense encoder succeeded, but index result failed: other strategies must still return.
    import numpy as np
    import importlib
    ppr = importlib.import_module("vibe_memory.retrieval.ppr")
    memory.embedding = SimpleNamespace(encode=lambda docs: np.ones((len(docs), 2)),
                                       encode_query=lambda query: np.ones(2))
    monkeypatch.setattr(ppr, "index_flat", fail)
    result = memory.recall("database")
    assert result["atoms"]
    assert result["failures"] == [{"stage": "semantic", "reason": "timeout"}]


def test_public_failure_counts_exclude_arbitrary_degradation_names():
    metrics = MetricsCollector()
    metrics.record_degradation(SECRET)
    metrics.record_failure("embedding_cache", TimeoutError(SECRET))
    assert metrics.stats()["failures"] == {"embedding_cache:timeout": 1}
    metrics.reset()
    assert metrics.stats()["failures"] == {}


def test_http_recall_session_and_stats_preserve_safe_failures(monkeypatch):
    from test_http_security import running, request
    with running(monkeypatch) as server:
        mem = server.httpd.memory_instance
        mem.store_batch([{"role": "assistant", "content": "database timeout"}])
        mem.metrics.record_degradation(SECRET)
        monkeypatch.setattr(mem.embedding, "search", fail)
        for path, body in [("/recall", {"query": "database"}),
                           ("/session/start", {"context": "database"})]:
            status, result, _ = request(server, path, "POST", body)
            assert status == 200
            assert result["failures"] == [{"stage": "semantic", "reason": "timeout"}]
            assert SECRET not in json.dumps(result)
        result = request(server)[1]
        assert result["failures"] == {"retrieval_semantic:timeout": 2}
        assert SECRET not in json.dumps(result)


def test_mcp_recall_session_and_stats_preserve_safe_failures(memory, monkeypatch):
    import sys
    import vibe_memory
    from vibe_memory.mcp_server import run_server
    monkeypatch.setattr(memory.embedding, "search", fail)
    memory.metrics.record_degradation(SECRET)
    monkeypatch.setattr(vibe_memory, "VibeMemory", lambda **kw: memory)
    calls = [{"jsonrpc": "2.0", "id": i, "method": "tools/call",
              "params": {"name": name, "arguments": args}}
             for i, (name, args) in enumerate([
                 ("vibe_recall", {"query": "database"}),
                 ("vibe_session_start", {"context": "database"}),
                 ("vibe_stats", {}),
             ], 1)]
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(json.dumps(c) for c in calls)))
    monkeypatch.setattr(sys, "stdout", stream)
    run_server(":memory:", "failures", "")
    results = [json.loads(json.loads(line)["result"]["content"][0]["text"])
               for line in stream.getvalue().splitlines()]
    for result in results[:2]:
        assert result["failures"] == [{"stage": "semantic", "reason": "timeout"}]
    assert results[2]["failures"] == {"retrieval_semantic:timeout": 2}
    assert SECRET not in stream.getvalue()
