import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from vibe_memory.models.memory_atom import Lifecycle, MemoryAtom
from vibe_memory.sdk import VibeMemory


def test_confirmed_use_recall_and_inject_do_not_reward_exposure(tmp_path):
    with VibeMemory('use', str(tmp_path / 'use.db'), embedding_backend='tfidf',
                    reinforcement_policy='confirmed_use') as memory:
        for key, text in [('one', 'copper deployment checkpoint'),
                          ('two', 'copper deployment resolution')]:
            memory.storage.insert_atom(MemoryAtom(key, 'use', 's', text, text, weight=0.5))
        edge = memory.link('one', 'two')
        before = memory.history()
        for _ in range(3):
            result = memory.recall('copper deployment checkpoint')
            assert 'one' in {a.id for a in result['atoms']}
            assert result['reinforcement_skipped'] is True
            assert memory.inject('copper deployment checkpoint')
        assert memory.history() == before
        assert memory.storage.get_edge(edge.id) == edge


def test_confirm_used_rewards_once_per_logical_event(tmp_path):
    with VibeMemory('use', str(tmp_path / 'reward.db'), embedding_backend='tfidf',
                    reinforcement_policy='confirmed_use') as memory:
        atom = MemoryAtom('one', 'use', 's', 'copper checkpoint', 'copper checkpoint',
                          weight=0.5, decay_rate=0.95)
        memory.storage.insert_atom(atom)
        assert memory.confirm_used('one', event_id='turn-1', expected_version=1) == {'applied': True}
        first = memory.history()[0]
        assert (first.weight, first.access_count, first.adopted_count) == (0.6, 1, 1)
        assert first.decay_rate == pytest.approx(0.96)
        assert first.last_accessed is not None
        assert (first.content, first.version, first.lifecycle, first.last_decayed_at,
                first.ignored_count) == (atom.content, 1, atom.lifecycle, None, 0)
        assert memory.confirm_used('one', event_id='turn-1', expected_version=1) == {'applied': False}
        assert memory.history()[0] == first
        assert memory.confirm_used('one', event_id='turn-2', expected_version=1) == {'applied': True}
        second = memory.history()[0]
        assert (second.weight, second.access_count, second.adopted_count) == (0.7, 2, 2)


def test_confirmation_survives_competing_connections_reopen_and_atom_changes(tmp_path):
    path = str(tmp_path / 'shared.db')
    options = {'embedding_backend': 'tfidf', 'reinforcement_policy': 'confirmed_use'}
    with VibeMemory('use', path, **options) as first, VibeMemory('use', path, **options) as second:
        first.storage.insert_atom(MemoryAtom('one', 'use', 's', 'checkpoint', 'checkpoint', weight=0.5))
        barrier = Barrier(2)

        def confirm(memory):
            barrier.wait(timeout=10)
            return memory.confirm_used('one', event_id='shared', expected_version=1)['applied']

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(confirm, [first, second]))
        assert sorted(outcomes) == [False, True]
        assert second.history()[0].access_count == 1
        changed = second.update('one', content='updated checkpoint')
        assert changed.version == 2
    with VibeMemory('use', path, **options) as memory:
        assert memory.confirm_used('one', event_id='shared', expected_version=1) == {'applied': False}
        before = memory.history()[0]
        with pytest.raises(ValueError, match='stale'):
            memory.confirm_used('one', event_id='next', expected_version=1)
        assert memory.history()[0] == before
        assert memory.confirm_used('one', event_id='next', expected_version=2) == {'applied': True}
        with pytest.raises(ValueError, match='conflicts'):
            memory.confirm_used('one', event_id='shared', expected_version=2)
        memory.storage.delete_atom('one')
        assert memory.confirm_used('one', event_id='shared', expected_version=1) == {'applied': False}


@pytest.mark.parametrize('tenant,agent', [('default', 'other'), ('other', 'use')])
def test_foreign_confirmation_does_not_reward_or_consume_event(tmp_path, tenant, agent):
    path = str(tmp_path / 'ownership.db')
    options = {'embedding_backend': 'tfidf', 'reinforcement_policy': 'confirmed_use'}
    with VibeMemory('use', path, **options) as owner, VibeMemory(agent, path, tenant_id=tenant, **options) as foreign:
        owner.storage.insert_atom(MemoryAtom('one', 'use', 's', 'checkpoint', 'checkpoint', weight=0.5))
        before = owner.history()[0]
        with pytest.raises(ValueError, match='unavailable'):
            foreign.confirm_used('one', event_id='event', expected_version=1)
        assert owner.history()[0] == before
        text = 'foreign checkpoint'
        foreign.storage.insert_atom(MemoryAtom('foreign', agent, 's', text, text, tenant_id=tenant))
        assert foreign.confirm_used('foreign', event_id='event', expected_version=1) == {'applied': True}
        assert owner.confirm_used('one', event_id='event', expected_version=1) == {'applied': True}


def test_unavailable_records_and_conflicting_event_payloads_are_not_rewarded(tmp_path):
    with VibeMemory('use', str(tmp_path / 'invalid.db'), embedding_backend='tfidf',
                    reinforcement_policy='confirmed_use') as memory:
        for state in (Lifecycle.ARCHIVED, Lifecycle.COLD):
            memory.storage.insert_atom(MemoryAtom(state.value, 'use', 's', 'checkpoint', 'checkpoint',
                                                  lifecycle=state, weight=0.5))
            with pytest.raises(ValueError, match='unavailable'):
                memory.confirm_used(state.value, event_id='event', expected_version=1)
        with pytest.raises(ValueError, match='unavailable'):
            memory.confirm_used('missing', event_id='event', expected_version=1)
        for key in ('one', 'two'):
            memory.storage.insert_atom(MemoryAtom(key, 'use', 's', 'checkpoint', 'checkpoint', weight=0.5))
        assert memory.confirm_used('one', event_id='event', expected_version=1) == {'applied': True}
        before = memory.history()
        with pytest.raises(ValueError, match='conflicts'):
            memory.confirm_used('two', event_id='event', expected_version=1)
        assert memory.history() == before


def test_database_denial_rolls_back_receipt_and_reward_so_same_event_can_retry(tmp_path):
    with VibeMemory('use', str(tmp_path / 'rollback.db'), embedding_backend='tfidf',
                    reinforcement_policy='confirmed_use') as memory:
        memory.storage.insert_atom(MemoryAtom('one', 'use', 's', 'checkpoint', 'checkpoint', weight=0.5))
        before = memory.history()

        def deny_atom_update(action, table, column, database, source):
            if action == sqlite3.SQLITE_UPDATE and table == 'atoms':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        memory.storage.conn.set_authorizer(deny_atom_update)
        try:
            with pytest.raises(sqlite3.DatabaseError):
                memory.confirm_used('one', event_id='retry', expected_version=1)
        finally:
            memory.storage.conn.set_authorizer(None)
        assert memory.history() == before
        assert memory.confirm_used('one', event_id='retry', expected_version=1) == {'applied': True}
        assert memory.history()[0].access_count == 1


def test_confirmation_does_not_own_existing_transaction_and_is_reusable_after_rollback(tmp_path):
    with VibeMemory('use', str(tmp_path / 'borrowed.db'), embedding_backend='tfidf',
                    reinforcement_policy='confirmed_use') as memory:
        memory.storage.insert_atom(MemoryAtom('one', 'use', 's', 'checkpoint', 'checkpoint', weight=0.5))
        memory.storage.conn.execute('BEGIN')
        try:
            with pytest.raises(RuntimeError, match='idle connection'):
                memory.confirm_used('one', event_id='event', expected_version=1)
            assert memory.storage.conn.in_transaction
        finally:
            memory.storage.conn.rollback()
        assert memory.confirm_used('one', event_id='event', expected_version=1) == {'applied': True}


def test_legacy_recall_still_rewards_but_cannot_confirm_use(tmp_path):
    with VibeMemory('use', str(tmp_path / 'legacy.db'), embedding_backend='tfidf') as memory:
        memory.storage.insert_atom(MemoryAtom('one', 'use', 's', 'copper checkpoint', 'copper checkpoint', weight=0.5))
        memory.recall('copper checkpoint')
        assert memory.history()[0].weight == 0.6
        with pytest.raises(ValueError, match='reinforcement_policy'):
            memory.confirm_used('one', event_id='event', expected_version=1)


@pytest.mark.parametrize('policy', ['', None, True, 'automatic'])
def test_invalid_reinforcement_policy_is_rejected(tmp_path, policy):
    with pytest.raises(ValueError, match='reinforcement_policy'):
        VibeMemory('use', str(tmp_path / 'policy.db'), embedding_backend='tfidf',
                   reinforcement_policy=policy)


@pytest.mark.parametrize('atom_id,event_id,version', [('', 'e', 1), ('one', ' ', 1),
                                                    ('one', 'e', True), ('one', 'e', 0),
                                                    ('one', 'e', '1')])
def test_invalid_confirmation_input_does_not_reward(tmp_path, atom_id, event_id, version):
    with VibeMemory('use', str(tmp_path / 'inputs.db'), embedding_backend='tfidf',
                    reinforcement_policy='confirmed_use') as memory:
        memory.storage.insert_atom(MemoryAtom('one', 'use', 's', 'checkpoint', 'checkpoint', weight=0.5))
        before = memory.history()
        with pytest.raises(ValueError):
            memory.confirm_used(atom_id, event_id=event_id, expected_version=version)
        assert memory.history() == before
