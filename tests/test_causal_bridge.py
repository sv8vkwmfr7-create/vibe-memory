"""Opt-in causal recall through the public SDK, using synthetic cases only."""
from vibe_memory.sdk import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


def case(mem, label=EdgeLabel.CAUSAL, confidence=1.0):
    def store(text, session_id):
        return mem.store(text, session_id=session_id, auto_build_edges=False, auto_episode=False)
    incident = store('database connection timeout error on checkout', session_id='incident')
    cause = store('credentials expired during rollover', session_id='earlier-session')
    fix = store('database connection timeout fixed by credential renewal retry policy', session_id='fix')
    for text in ('database timeout dashboard charts metrics histogram monitoring',
                 'connection timeout handbook SQL schema index migration documentation',
                 'checkout error console browser javascript rendering canvas widgets',
                 'database connection report revenue forecast accounting quarterly spreadsheet'):
        store(text, session_id='unrelated')
    mem.link(incident.id, cause.id, label=label, confidence=confidence)
    mem.link(cause.id, fix.id, label=label, confidence=confidence)
    return cause.id


def test_opt_in_preserves_cross_session_cause_without_changing_default():
    mem = VibeMemory(agent_id='bridge', db_path=':memory:', embedding_backend='tfidf')
    try:
        cause = case(mem)
        query = 'database connection timeout error on checkout'
        baseline = [a.id for a in mem.recall(query, top_k=5)['atoms']]
        assert cause not in baseline
        assert cause in [a.id for a in mem.recall(query, top_k=5, causal_bridge=True)['atoms']]
        assert [a.id for a in mem.recall(query, top_k=5)['atoms']] == baseline
    finally:
        mem.storage.conn.close()


@pytest.mark.parametrize('options', [{'mode': 'budget', 'causal_bridge': True},
                                   {'mode': 'recall', 'causal_bridge': True},
                                   {'causal_bridge': 'false'}, {'causal_bridge': 1}])
def test_bridge_rejects_unsupported_mode_or_nonboolean(options):
    mem = VibeMemory(agent_id='bridge', db_path=':memory:', embedding_backend='tfidf')
    try:
        with pytest.raises(ValueError, match='causal_bridge'):
            mem.recall('query', **options)
    finally:
        mem.storage.conn.close()


@pytest.mark.parametrize('label,confidence', [(EdgeLabel.SIMILAR, 1.0),
                                            (EdgeLabel.CAUSAL, 0.01)])
def test_unrelated_label_or_weak_causal_edges_do_not_promote(label, confidence):
    mem = VibeMemory(agent_id='bridge', db_path=':memory:', embedding_backend='tfidf')
    try:
        cause = case(mem, label, confidence)
        result = mem.recall('database connection timeout error on checkout', top_k=5,
                            causal_bridge=True)
        assert cause not in [a.id for a in result['atoms']]
    finally:
        mem.storage.conn.close()


def test_graph_free_opt_in_preserves_ranking():
    mem = VibeMemory(agent_id='bridge', db_path=':memory:', embedding_backend='tfidf')
    try:
        mem.store('database error', auto_build_edges=False, auto_episode=False)
        mem.store('browser rendering', auto_build_edges=False, auto_episode=False)
        query = 'database error'
        assert [a.id for a in mem.recall(query, causal_bridge=True)['atoms']] == [
            a.id for a in mem.recall(query)['atoms']]
    finally:
        mem.storage.conn.close()


def test_tenant_scoped_parallel_opt_in_does_not_change_other_calls(tmp_path):
    path = str(tmp_path / 'bridge.db')
    causes = {}
    for tenant in ('alpha', 'beta'):
        mem = VibeMemory(agent_id='bridge', tenant_id=tenant, db_path=path,
                         embedding_backend='tfidf')
        try:
            causes[tenant] = case(mem)
        finally:
            mem.storage.conn.close()
    barrier = Barrier(4)
    def run(tenant, enabled):
        mem = VibeMemory(agent_id='bridge', tenant_id=tenant, db_path=path,
                         embedding_backend='tfidf')
        try:
            barrier.wait(timeout=10)
            for _ in range(10):
                atoms = mem.recall('database connection timeout error on checkout', top_k=5,
                                   causal_bridge=enabled)['atoms']
                assert all(a.tenant_id == tenant for a in atoms)
                assert (causes[tenant] in {a.id for a in atoms}) == enabled
        finally:
            mem.storage.conn.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run, tenant, flag) for tenant in causes for flag in (False, True)]
        for future in futures:
            future.result(timeout=30)
