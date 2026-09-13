from concurrent.futures import ThreadPoolExecutor

from vibe_memory.models.memory_atom import MemoryAtom, Lifecycle
from vibe_memory.storage.sqlite_store import VibeStorage


def test_reinforcement_preserves_current_text_and_accumulates_access(tmp_path):
    path = str(tmp_path / "memory.db")
    store = VibeStorage(path, journal_mode="wal")
    other = VibeStorage(path)
    try:
        store.insert_atom(MemoryAtom(id="anchor", agent_id="test", session_id="s",
                                    content="旧正文", summary="旧摘要", weight=0.5))
        current = other.get_atom("anchor")
        current.content = current.summary = "连接池超时修复"
        other.update_atom(current)
        first = store.reinforce_atoms(["anchor"], "test")[0]
        second = other.reinforce_atoms(["anchor"], "test")[0]
        assert first.content == "连接池超时修复"
        assert second.content == second.summary == "连接池超时修复"
        assert second.access_count == 2
        assert abs(second.weight - 0.7) < 1e-9
        assert store.get_atom("anchor").access_count == 2
    finally:
        other.conn.close()
        store.conn.close()


def test_concurrent_batches_do_not_lose_access_increments(tmp_path):
    path = str(tmp_path / "memory.db")
    stores = [VibeStorage(path, journal_mode="wal"), VibeStorage(path)]
    stores[0].insert_atom(MemoryAtom(id="anchor", agent_id="test", session_id="s",
                                     content="连接池超时修复", summary="连接池超时修复"))
    try:
        def reinforce(store):
            for _ in range(100):
                store.reinforce_atoms(["anchor"], "test")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reinforce, store) for store in stores]
            for future in futures:
                future.result(timeout=10)
        assert stores[0].get_atom("anchor").access_count == 200
    finally:
        for store in stores:
            store.conn.close()


def test_batch_reinforcement_excludes_other_scopes_and_archived_atoms():
    store = VibeStorage(tenant_id="tenant-a")
    try:
        for atom_id, agent, tenant, lifecycle in [
            ("normal", "test", "tenant-a", Lifecycle.ACTIVE),
            ("other-agent", "other", "tenant-a", Lifecycle.ACTIVE),
            ("other-tenant", "test", "tenant-b", Lifecycle.ACTIVE),
            ("archived", "test", "tenant-a", Lifecycle.ARCHIVED),
            ("warm", "test", "tenant-a", Lifecycle.WARM),
        ]:
            store.insert_atom(MemoryAtom(id=atom_id, agent_id=agent, tenant_id=tenant,
                                        session_id="s", content="记忆正文", summary="记忆正文",
                                        lifecycle=lifecycle))
        updated = store.reinforce_atoms(["normal", "normal", "other-agent", "other-tenant", "archived", "warm"], "test")
        assert {atom.id for atom in updated} == {"normal", "warm"}
        assert store.get_atom("normal").access_count == 1
        assert store.get_atom("warm").access_count == 1
        for atom_id in ("other-agent", "other-tenant", "archived"):
            assert store.get_atom(atom_id).access_count == 0
        assert store.reinforce_atoms([], "test") == []
    finally:
        store.conn.close()
