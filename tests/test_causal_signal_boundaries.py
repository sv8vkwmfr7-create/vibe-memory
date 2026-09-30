import pytest
from unittest.mock import Mock

from vibe_memory import VibeMemory
from vibe_memory.edges.edge_builder import (
    _has_causal_signal, build_same_session_edges, classify_cross_session_edge,
)
from vibe_memory.models.memory_atom import MemoryAtom, EdgeLabel
from vibe_memory.llm.edge_classifier import LLMEdgeClassifier
from vibe_memory.llm.provider import LLMError


@pytest.mark.parametrize("text", [
    "JSON payload", "console output", "resource pool", "故障日志已归档", "事故记录已归档",
    "然后读取日志", "更新配置文件", "修复界面布局", "查询结果有三条", "update config",
    "fix layout", "change settings", "so_flag=1", "because_id=2", "so2", "thereforex",
])
def test_substrings_actions_and_sequence_are_not_causal_evidence(text):
    assert not _has_causal_signal(text)


@pytest.mark.parametrize("text", [
    "因为连接池耗尽，请求超时", "由于端口被占用，启动失败", "池满导致超时",
    "所以增加连接数", "因此更换节点", "从而降低延迟", "于是减少并发", "因而暂停任务",
    "故而重试请求", "故此停止任务", "BECAUSE the pool is full", "Pool full, so retry.",
    "Therefore, lower concurrency", "thus reducing latency", "hence the timeout",
])
def test_explicit_causal_connectors_remain_recognized(text):
    assert _has_causal_signal(text)


def atoms(first, second, tags):
    return [MemoryAtom(id=str(i), agent_id="agent", session_id="s", content=text,
                       summary=text, tags=tags)
            for i, text in enumerate((first, second))]


@pytest.mark.parametrize("tags,label", [([], EdgeLabel.ADJACENT), (["config"], EdgeLabel.SIMILAR)])
def test_same_session_uses_noncausal_fallback(tags, label):
    pair = atoms("JSON payload", "故障日志已归档", tags)
    edge = build_same_session_edges(pair)[0]
    assert edge.label == label
    assert (edge.from_atom_id, edge.to_atom_id) == ("0", "1")
    assert classify_cross_session_edge(*pair)[0] == EdgeLabel.SIMILAR


def test_explicit_connectors_preserve_causal_building():
    pair = atoms("因为连接池耗尽，请求超时", "因此增加连接数", [])
    assert build_same_session_edges(pair)[0].label == EdgeLabel.CAUSAL
    assert classify_cross_session_edge(*pair)[0] == EdgeLabel.CAUSAL


@pytest.mark.parametrize("texts,label", [
    (("JSON payload", "故障日志已归档"), EdgeLabel.SIMILAR),
    (("因为连接池耗尽，请求超时", "因此增加连接数"), EdgeLabel.CAUSAL),
])
def test_llm_failure_uses_the_same_signal_boundaries(texts, label):
    provider = Mock()
    provider.chat.side_effect = LLMError("synthetic provider unavailable")
    classifier = LLMEdgeClassifier(provider, max_retries=0)
    assert classifier.classify(*atoms(*texts, []))[0] == label
    provider.chat.assert_called_once()


def test_sdk_batch_does_not_turn_json_and_failure_nouns_into_causal_edges():
    memory = VibeMemory(agent_id="agent", embedding_backend="tfidf")
    try:
        stored = memory.store_batch([
            {"role": "assistant", "content": "JSON payload uses UTF8 encoding"},
            {"role": "assistant", "content": "故障日志已归档到本地目录"},
        ], session_id="s")
        assert len(stored) == 2
        edges = memory.storage.get_all_edges()
        assert len(edges) == 1
        assert edges[0].label != EdgeLabel.CAUSAL
    finally:
        memory.storage.conn.close()
