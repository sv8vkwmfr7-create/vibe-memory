import tracemalloc

import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel, Lifecycle


@pytest.mark.parametrize('mode', ['precision', 'recall'])
def test_warm_sparse_recall_stays_within_fixture_allocation_budget(mode):
    memory = VibeMemory(agent_id='projection', embedding_backend='tfidf')
    try:
        anchor = memory.store(
            '连接池耗尽导致接口超时，释放连接后恢复正常',
            auto_build_edges=False, auto_episode=False)
        for index in range(2999):
            memory.store(
                f'日常维护记录编号{index}，桌面主题颜色和背景图片设置完成',
                auto_build_edges=False, auto_episode=False)
        memory.recall('接口超时如何修复连接池', mode=mode, top_k=5)

        # Public-call allocation contract for this fixture, not RSS or an SLA.
        tracemalloc.start()
        try:
            result = memory.recall('接口超时如何修复连接池', mode=mode, top_k=5)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert anchor.id in {atom.id for atom in result['atoms']}
        assert result['failures'] == []
        assert peak < 3 * 1024 * 1024, peak
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('mode', ['precision', 'recall'])
@pytest.mark.parametrize('external_writer', [False, True])
def test_sparse_recall_observes_updates_reinforcement_store_and_forget(tmp_path, mode, external_writer):
    path = str(tmp_path / 'visibility.db')
    reader = VibeMemory(agent_id='projection', db_path=path, embedding_backend='tfidf')
    writer = (VibeMemory(agent_id='projection', db_path=path, embedding_backend='tfidf')
              if external_writer else reader)
    try:
        anchor = writer.store('quasar incident resolution', session_id='evidence',
                              auto_build_edges=False, auto_episode=False)
        writer.store('wallpaper daily routine', auto_build_edges=False, auto_episode=False)
        first = reader.recall('quasar incident resolution', mode=mode, top_k=1)
        assert [atom.id for atom in first['atoms']] == [anchor.id]
        assert first['atoms'][0].access_count == 1

        writer.update(anchor.id, content='nebula incident resolution', summary='new summary',
                      tags=['new-tag'], scope={'service': 'orders'}, weight=0.2,
                      confidence=0.4, decay_rate=0.8)
        second = reader.recall('nebula incident resolution', mode=mode, top_k=1,
                               scope={'service': 'orders'})
        assert [atom.id for atom in second['atoms']] == [anchor.id]
        updated = second['atoms'][0]
        assert (updated.content, updated.summary, updated.tags, updated.scope) == (
            'nebula incident resolution', 'new summary', ['new-tag'], {'service': 'orders'})
        assert (updated.confidence, updated.decay_rate, updated.access_count) == (0.4, 0.8, 2)
        assert updated.weight == pytest.approx(0.3)
        assert second['failures'] == []

        # Caller-owned mutable results must not poison subsequent retrieval.
        updated.content = 'caller-only modification'
        updated.tags.append('caller-tag')
        updated.scope['service'] = 'caller-service'
        third = reader.recall('nebula incident resolution', mode=mode, top_k=1)
        assert (third['atoms'][0].content, third['atoms'][0].tags, third['atoms'][0].scope) == (
            'nebula incident resolution', ['new-tag'], {'service': 'orders'})
        assert third['atoms'][0].access_count == 3
        assert third['atoms'][0].weight == pytest.approx(0.4)

        added = writer.store('pulsar unique recovery', auto_build_edges=False, auto_episode=False)
        assert [atom.id for atom in reader.recall('pulsar unique recovery', mode=mode,
                                                top_k=1)['atoms']] == [added.id]
        assert writer.forget(added.id)
        assert writer.forget(anchor.id)
        remaining = reader.recall('nebula pulsar resolution', mode=mode, top_k=5)
        assert {atom.id for atom in remaining['atoms']}.isdisjoint({anchor.id, added.id})
        assert reader.history('evidence') == []
        assert remaining['failures'] == []
    finally:
        if writer is not reader:
            writer.storage.conn.close()
        reader.storage.conn.close()


@pytest.mark.parametrize('mode', ['precision', 'recall'])
@pytest.mark.parametrize('external_writer', [False, True])
def test_metadata_update_keeps_warm_recall_within_fixture_allocation_budget(tmp_path, mode, external_writer):
    path = str(tmp_path / 'metadata.db')
    memory = VibeMemory(agent_id='metadata-budget', db_path=path, embedding_backend='tfidf')
    writer = (VibeMemory(agent_id='metadata-budget', db_path=path, embedding_backend='tfidf')
              if external_writer else memory)
    try:
        anchor = memory.store('quasar incident resolution',
                              auto_build_edges=False, auto_episode=False)
        for index in range(2999):
            memory.store(f'wallpaper maintenance record {index}',
                         auto_build_edges=False, auto_episode=False)
        memory.recall('quasar incident resolution', mode=mode, top_k=1)
        prior = writer.storage.get_atom(anchor.id)
        updated = writer.update(anchor.id, confidence=0.6, summary='reviewed incident',
                                tags=['reviewed'], scope={'service': 'orders'},
                                decay_rate=0.8, weight=0.2)
        assert updated.version == prior.version + 1

        # Public-call allocation contract, not an elapsed-time or RSS gate.
        tracemalloc.start()
        try:
            result = memory.recall('quasar incident resolution', mode=mode, top_k=1)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert result['failures'] == []
        assert [atom.id for atom in result['atoms']] == [anchor.id]
        assert result['atoms'][0].confidence == 0.6
        assert (result['atoms'][0].summary, result['atoms'][0].tags,
                result['atoms'][0].scope, result['atoms'][0].decay_rate) == (
            'reviewed incident', ['reviewed'], {'service': 'orders'}, 0.8)
        assert result['atoms'][0].weight == pytest.approx(0.3)
        assert peak < 3 * 1024 * 1024, peak
    finally:
        if writer is not memory:
            writer.storage.conn.close()
        memory.storage.conn.close()


@pytest.mark.parametrize('mode', ['precision', 'recall', 'budget'])
def test_scope_only_updates_change_strict_recall_membership_across_connections(tmp_path, mode):
    path = str(tmp_path / 'scope-membership.db')
    reader = VibeMemory(agent_id='scope-membership', db_path=path, embedding_backend='tfidf')
    writer = VibeMemory(agent_id='scope-membership', db_path=path, embedding_backend='tfidf')
    scope = {'environment': 'production'}
    try:
        old = writer.store('quasar incident resolution', scope=scope,
                           auto_build_edges=False, auto_episode=False)
        new = writer.store('nebula incident resolution', scope={'environment': 'test'},
                           auto_build_edges=False, auto_episode=False)
        first = reader.recall('quasar incident resolution', mode=mode, top_k=1,
                              scope=scope, strict_scope=True)
        assert [atom.id for atom in first['atoms']] == [old.id]
        writer.update(old.id, scope={'environment': 'test'})
        writer.update(new.id, scope=scope)
        second = reader.recall('nebula incident resolution', mode=mode, top_k=1,
                               scope=scope, strict_scope=True)
        assert second['failures'] == []
        assert [(atom.id, atom.content, atom.scope) for atom in second['atoms']] == [
            (new.id, 'nebula incident resolution', scope)]
        assert writer.forget(new.id)
        empty = reader.recall('nebula incident resolution', mode=mode, top_k=1,
                              scope=scope, strict_scope=True)
        assert empty['atoms'] == []
        assert empty['failures'] == []
    finally:
        writer.storage.conn.close()
        reader.storage.conn.close()


@pytest.mark.parametrize('mode', ['precision', 'recall'])
@pytest.mark.parametrize('label', list(EdgeLabel))
def test_sparse_graph_recall_keeps_owner_lifecycle_and_full_evidence(tmp_path, mode, label):
    path = str(tmp_path / 'owners.db')
    owners = [VibeMemory(agent_id=agent, tenant_id=tenant, db_path=path,
                         embedding_backend='tfidf') for tenant, agent in (
        ('local', 'agent'), ('foreign', 'agent'), ('local', 'other-agent'))]
    memory = owners[0]
    try:
        anchor = memory.store('quasar incident root cause', tags=['incident'],
                              scope={'service': 'orders'}, context_after='qualified evidence',
                              auto_build_edges=False, auto_episode=False)
        solution = memory.store('quasar incident remedy', tags=['remedy'],
                                auto_build_edges=False, auto_episode=False)
        memory.link(anchor.id, solution.id, label=label, confidence=0.65)
        warm = memory.storage.get_atom(solution.id)
        warm.lifecycle = Lifecycle.WARM
        memory.storage.update_atom(warm)
        excluded = []
        for lifecycle in (Lifecycle.COLD, Lifecycle.ARCHIVED):
            atom = memory.store('quasar incident root cause', auto_build_edges=False,
                                auto_episode=False)
            atom.lifecycle = lifecycle
            memory.storage.update_atom(atom)
            excluded.append(atom.id)
        for owner in owners[1:]:
            excluded.append(owner.store('quasar incident root cause', auto_build_edges=False,
                                        auto_episode=False).id)

        for _ in range(2):
            result = memory.recall('quasar incident root cause', mode=mode, top_k=5)
            assert {atom.id for atom in result['atoms']} == {anchor.id, solution.id}
            restored = next(atom for atom in result['atoms'] if atom.id == anchor.id)
            assert (restored.tags, restored.scope, restored.context_after) == (
                ['incident'], {'service': 'orders'}, 'qualified evidence')
            assert sorted(result['trace'], key=lambda item: item['to']) == sorted([
                {'from': solution.id, 'to': anchor.id, 'edge_label': label.value,
                 'depth': 1, 'confidence': 0.65},
                {'from': anchor.id, 'to': solution.id, 'edge_label': label.value,
                 'depth': 1, 'confidence': 0.65},
            ], key=lambda item: item['to'])
            assert result['failures'] == []

        # Lifecycle changes through another connection must remove a warmed result.
        updater = VibeMemory(agent_id='agent', tenant_id='local', db_path=path,
                             embedding_backend='tfidf')
        try:
            changed = updater.storage.get_atom(solution.id)
            changed.lifecycle = Lifecycle.COLD
            updater.storage.update_atom(changed)
        finally:
            updater.storage.conn.close()
        final = memory.recall('quasar incident root cause', mode=mode, top_k=5)
        assert {atom.id for atom in final['atoms']}.isdisjoint({solution.id, *excluded})
    finally:
        for owner in owners:
            owner.storage.conn.close()
