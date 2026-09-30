from datetime import datetime, timedelta
from copy import deepcopy

import pytest

from vibe_memory.sdk import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom, Episode
from vibe_memory.chunking.episode import EpisodeBuilder


@pytest.fixture
def memory():
    mem = VibeMemory(agent_id="agent", db_path=":memory:", embedding_backend="tfidf")
    for i in range(3):
        mem.storage.insert_atom(MemoryAtom(id=str(i), agent_id="agent", session_id="s", content=str(i), summary=str(i), tags=["topic"], created_at=datetime(2026, 9, 30) + timedelta(seconds=i)))
    yield mem
    mem.storage.conn.close()


def test_repeated_aggregation_is_bounded_and_persists_member_links(memory):
    memory._auto_episode_aggregation("s")
    first = memory.storage.get_episodes_by_session("s")[0]
    for _ in range(5):
        memory._auto_episode_aggregation("s")
    episodes = memory.storage.get_episodes_by_session("s")
    assert len(episodes) == 1
    assert episodes[0].id == first.id
    assert all(memory.storage.get_atom(mid).episode_id == first.id for mid in first.atom_ids)


def test_growth_keeps_identity_and_replaces_summary(memory):
    memory._auto_episode_aggregation("s")
    first = memory.storage.get_episodes_by_session("s")[0]
    memory.storage.insert_atom(MemoryAtom(id="3", agent_id="agent", session_id="s", content="3", summary="3", tags=["topic"], created_at=datetime(2026, 9, 30, 0, 0, 3)))
    memory._auto_episode_aggregation("s")
    episodes = memory.storage.get_episodes_by_session("s")
    assert len(episodes) == 1
    assert episodes[0].id == first.id
    assert episodes[0].atom_ids == ["0", "1", "2", "3"]
    assert "4 chunks" in episodes[0].summary


def test_builder_refuses_mixed_owners_or_sessions():
    first = MemoryAtom(id="a", agent_id="a", session_id="s", content="a", summary="a", tags=["topic"])
    for changes in ({"agent_id": "b"}, {"tenant_id": "foreign"}, {"session_id": "other"}):
        second = MemoryAtom(id="b", agent_id="a", session_id="s", content="b", summary="b", tags=["topic"])
        for field, value in changes.items():
            setattr(second, field, value)
        with pytest.raises(ValueError):
            EpisodeBuilder().build_episodes([first, second])


def test_rebuild_preserves_other_owners_and_usage_metadata(memory):
    memory._auto_episode_aggregation("s")
    eid = memory.storage.get_episodes_by_session("s")[0].id
    memory.storage.conn.execute("UPDATE episodes SET access_count=7, weight=2 WHERE id=?", (eid,))
    memory.storage.conn.commit()
    for tenant, agent in (("foreign", "agent"), ("default", "other")):
        memory.storage.insert_episode(Episode(id=tenant + agent, tenant_id=tenant, agent_id=agent, session_id="s", summary="keep", topic="topic", atom_ids=[]))
    memory._auto_episode_aggregation("s")
    episodes = memory.storage.get_episodes_by_session("s")
    assert len(episodes) == 3
    own = next(ep for ep in episodes if ep.id == eid)
    assert (own.access_count, own.weight) == (7, 2)


def test_topic_changes_remove_obsolete_episode_and_links(memory):
    memory._auto_episode_aggregation("s")
    for i in range(3):
        memory.update(str(i), tags=["topic" + str(i)])
    memory._auto_episode_aggregation("s")
    assert memory.storage.get_episodes_by_session("s") == []
    assert all(memory.storage.get_atom(str(i)).episode_id is None for i in range(3))


def test_failed_replacement_rolls_back_episode_and_links(memory):
    import sqlite3
    memory._auto_episode_aggregation("s")
    before = memory.storage.get_episodes_by_session("s")
    memory.storage.conn.execute("CREATE TRIGGER fail_episode BEFORE INSERT ON episodes BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
    with pytest.raises(sqlite3.IntegrityError):
        memory._auto_episode_aggregation("s")
    assert memory.storage.get_episodes_by_session("s") == before
    assert all(memory.storage.get_atom(str(i)).episode_id == before[0].id for i in range(3))


def test_changed_session_snapshot_is_rejected(memory):
    memory._auto_episode_aggregation("s")
    before = memory.storage.get_episodes_by_session("s")
    atoms = memory.storage.get_atoms_by_session("s", agent_id="agent")
    episodes = EpisodeBuilder().build_episodes(deepcopy(atoms))
    memory.update("0", summary="new summary")
    with pytest.raises(ValueError, match="Session changed"):
        memory.storage.replace_session_episodes("s", "agent", "default", atoms, episodes)
    assert memory.storage.get_episodes_by_session("s") == before


def test_caller_transaction_is_not_committed(memory):
    memory.storage.conn.execute("BEGIN")
    with pytest.raises(RuntimeError):
        memory._auto_episode_aggregation("s")
    assert memory.storage.conn.in_transaction
    memory.storage.conn.rollback()


def test_timestamp_ties_keep_source_order(memory):
    for i in range(3):
        atom = memory.storage.get_atom(str(i))
        atom.created_at = datetime(2026, 9, 30)
        atom.episode_position = 10 + i
        memory.storage.update_atom(atom)
    for _ in range(3):
        memory._auto_episode_aggregation("s")
        assert memory.storage.get_episodes_by_session("s")[0].atom_ids == ["0", "1", "2"]
    assert [memory.storage.get_atom(str(i)).episode_position for i in range(3)] == [10, 11, 12]
