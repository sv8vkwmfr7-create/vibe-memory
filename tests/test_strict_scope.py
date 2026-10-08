"""Opt-in scope exclusion through public SDK interfaces."""
import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel


@pytest.mark.parametrize('mode', ['precision', 'recall', 'budget'])
def test_strict_scope_rejects_conflicting_and_missing_metadata(mode):
    memory = VibeMemory(agent_id='strict-scope', embedding_backend='tfidf')
    try:
        memory.store('支付服务测试环境重试次数为1次。', session_id='test',
                     scope={'service': 'payment', 'environment': 'test'})
        memory.store('支付服务重试次数为7次。', session_id='unknown')
        result = memory.recall('支付服务生产环境重试次数是多少？', mode=mode,
                               scope={'environment': 'production'}, strict_scope=True)
        assert result['atoms'] == []
        assert result['trace'] == []
        assert result['failures'] == []
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('mode', ['precision', 'recall', 'budget'])
def test_strict_graph_cannot_cross_conflicting_scope_to_reach_other_records(mode):
    memory = VibeMemory(agent_id='strict-graph', embedding_backend='tfidf')
    try:
        scope = {'environment': 'production'}
        anchor = memory.store('支付服务连接超时。', scope=scope, auto_build_edges=False)
        bridge = memory.store('凭据过期。', scope={'environment': 'test'}, auto_build_edges=False)
        hidden = memory.store('磁盘损坏。', scope=scope, auto_build_edges=False)
        memory.link(bridge.id, anchor.id, label=EdgeLabel.CAUSAL, confidence=1.0)
        memory.link(hidden.id, bridge.id, label=EdgeLabel.CAUSAL, confidence=1.0)
        result = memory.recall('支付服务连接超时', mode=mode, top_k=5,
                               scope=scope, strict_scope=True)
        assert {atom.id for atom in result['atoms']} == {anchor.id}
        assert result['trace'] == []
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('mode', ['precision', 'recall', 'budget'])
def test_strict_scope_filters_before_top_k_and_matches_all_normalized_keys(mode):
    memory = VibeMemory(agent_id='strict-top-k', embedding_backend='tfidf')
    try:
        for index in range(105):
            memory.store(f'payment retry exact match {index}',
                         scope={'service': 'payment', 'environment': 'test'}, auto_build_edges=False,
                         auto_episode=False)
        good = memory.store('payment retry limit three',
                            scope={'service': 'payment', 'environment': 'production', 'operation': 'retry'},
                            auto_build_edges=False, auto_episode=False)
        result = memory.recall('payment retry exact match', mode=mode, top_k=1,
                               scope={'service': ' PAYMENT ', 'environment': 'Production'},
                               strict_scope=True)
        assert [atom.id for atom in result['atoms']] == [good.id]
        assert result['failures'] == []
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('scope', [None, {}])
def test_strict_without_scope_keeps_existing_behavior(scope):
    memory = VibeMemory(agent_id='strict-empty', embedding_backend='tfidf')
    try:
        atom = memory.store('支付服务测试环境重试次数为1次。', scope={'environment': 'test'})
        result = memory.recall('支付服务重试次数', scope=scope, strict_scope=True)
        assert [a.id for a in result['atoms']] == [atom.id]
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('value', [1, 'true', None])
def test_strict_scope_requires_boolean(value):
    memory = VibeMemory(agent_id='strict-invalid', embedding_backend='tfidf')
    try:
        with pytest.raises(ValueError, match='strict_scope must be a boolean'):
            memory.recall('支付服务', strict_scope=value)
    finally:
        memory.storage.conn.close()


def test_strict_scope_missing_key_does_not_match_requested_empty_string():
    memory = VibeMemory(agent_id='strict-missing', embedding_backend='tfidf')
    try:
        memory.store('支付服务重试次数为1次。')
        assert memory.recall('支付服务重试次数', scope={'environment': ''}, strict_scope=True)['atoms'] == []
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('causal_bridge', [False, True])
def test_strict_scope_keeps_matching_nonlexical_graph_evidence(causal_bridge):
    memory = VibeMemory(agent_id='strict-cause', embedding_backend='tfidf')
    try:
        scope = {'environment': 'production'}
        anchor = memory.store('支付服务连接超时。', scope=scope, auto_build_edges=False)
        cause = memory.store('凭据过期。', scope=scope, auto_build_edges=False)
        wrong = memory.store('磁盘损坏。', scope={'environment': 'test'}, auto_build_edges=False)
        memory.link(cause.id, anchor.id, label=EdgeLabel.CAUSAL, confidence=1.0)
        memory.link(wrong.id, anchor.id, label=EdgeLabel.CAUSAL, confidence=1.0)
        result = memory.recall('支付服务连接超时', scope=scope, strict_scope=True,
                               causal_bridge=causal_bridge)
        assert {atom.id for atom in result['atoms']} == {anchor.id, cause.id}
        assert all(trace['from'] in {anchor.id, cause.id} and trace['to'] in {anchor.id, cause.id}
                   for trace in result['trace'])
    finally:
        memory.storage.conn.close()
