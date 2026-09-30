import json
import sqlite3

import pytest

from vibe_memory import VibeMemory
from vibe_memory.coldstart import ColdStartManager
from vibe_memory.defense import MemoryDefense
from vibe_memory.storage.sqlite_store import VibeStorage


def seed_file(tmp_path, rows):
    path = tmp_path / "synthetic-seeds.json"
    path.write_text(json.dumps({"version": "test-1", "domain": "synthetic", "atoms": rows}), encoding="utf-8")
    return str(path)


def test_seed_loading_and_bootstrap_apply_sdk_defense(tmp_path):
    path = seed_file(tmp_path, [{"content": "contact synthetic@example.invalid", "summary": "contact synthetic@example.invalid"}])
    mem = VibeMemory(agent_id="agent", db_path=":memory:", embedding_backend="tfidf")
    try:
        mem.cold_start.seed_memory_path = path
        loaded = mem.cold_start.load_seed_memory()
        assert "synthetic@" not in loaded[0].content
        assert "synthetic@" not in loaded[0].summary
        stored = mem.cold_start.bootstrap()
        assert "synthetic@" not in mem.storage.get_atom(stored[0].id).content
    finally:
        mem.storage.conn.close()


def test_seed_block_preflight_leaves_no_rows_or_success_flag(tmp_path):
    path = seed_file(tmp_path, [{"content": "safe"}, {"content": "contact synthetic@example.invalid"}])
    mem = VibeMemory(agent_id="agent", db_path=":memory:", embedding_backend="tfidf", defense=MemoryDefense(mode="block"))
    try:
        mem.cold_start.seed_memory_path = path
        with pytest.raises(ValueError) as error:
            mem.cold_start.bootstrap()
        assert "synthetic@" not in str(error.value)
        assert mem.history() == []
        assert not mem.cold_start._bootstrapped
    finally:
        mem.storage.conn.close()


def test_reopen_does_not_repeat_bootstrap_or_restore_deleted_seed(tmp_path):
    path = seed_file(tmp_path, [{"content": "safe seed"}])
    db = str(tmp_path / "test.db")
    first = VibeStorage(db)
    cm = ColdStartManager(first, "agent", seed_memory_path=path)
    stored = cm.bootstrap()
    first.conn.close()
    second = VibeStorage(db)
    try:
        assert ColdStartManager(second, "agent", seed_memory_path=path).bootstrap() == []
        assert second.count_atoms_by_agent("agent") == 1
        second.delete_atom(stored[0].id)
        assert ColdStartManager(second, "agent", seed_memory_path=path).bootstrap() == []
        assert second.count_atoms_by_agent("agent") == 0
    finally:
        second.conn.close()


def test_failed_seed_insert_rolls_back_whole_bootstrap(tmp_path):
    path = seed_file(tmp_path, [{"content": "first"}, {"content": "second"}])
    store = VibeStorage(":memory:")
    cm = ColdStartManager(store, "agent", seed_memory_path=path)
    try:
        store.conn.execute("CREATE TRIGGER fail_seed BEFORE INSERT ON atoms WHEN new.content='second' BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
        with pytest.raises(sqlite3.IntegrityError):
            cm.bootstrap()
        assert store.count_atoms_by_agent("agent") == 0
        assert not cm._bootstrapped
        store.conn.execute("DROP TRIGGER fail_seed")
        assert len(cm.bootstrap()) == 2
    finally:
        store.conn.close()


def test_scope_and_new_seed_content_have_separate_completion_markers(tmp_path):
    path = seed_file(tmp_path, [{"content": "first"}])
    store = VibeStorage(":memory:")
    try:
        for tenant, agent in (("default", "a"), ("default", "b"), ("other", "a")):
            assert len(ColdStartManager(store, agent, tenant_id=tenant, seed_memory_path=path).bootstrap()) == 1
            assert len(ColdStartManager(store, agent, tenant_id=tenant, seed_memory_path=path).bootstrap()) == 0
        seed_file(tmp_path, [{"content": "second"}])
        assert len(ColdStartManager(store, "a", seed_memory_path=path).bootstrap()) == 1
        assert store.count_atoms_by_agent("a") == 2
    finally:
        store.conn.close()


def test_two_connections_bootstrap_exactly_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path = seed_file(tmp_path, [{"content": "first"}, {"content": "second"}])
    db = str(tmp_path / "concurrent.db")
    stores = [VibeStorage(db), VibeStorage(db)]
    barrier = Barrier(2)
    def run(store):
        manager = ColdStartManager(store, "agent", seed_memory_path=path)
        barrier.wait(timeout=5)
        return len(manager.bootstrap())
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(run, stores)) == [0, 2]
        assert stores[0].count_atoms_by_agent("agent") == 2
    finally:
        for store in stores:
            store.conn.close()


def test_bootstrap_refuses_caller_transaction(tmp_path):
    path = seed_file(tmp_path, [{"content": "first"}])
    store = VibeStorage(":memory:")
    try:
        store.conn.execute("BEGIN")
        with pytest.raises(RuntimeError):
            ColdStartManager(store, "agent", seed_memory_path=path).bootstrap()
        assert store.conn.in_transaction
        store.conn.rollback()
        assert len(ColdStartManager(store, "agent", seed_memory_path=path).bootstrap()) == 1
    finally:
        store.conn.close()


def test_direct_manager_warn_custom_exclusion_and_invalid_partition(tmp_path):
    path = seed_file(tmp_path, [{"content": "contact synthetic@example.invalid PRIVATEWORD"}])
    store = VibeStorage(":memory:")
    try:
        warn = ColdStartManager(store, "warn", seed_memory_path=path, defense=MemoryDefense(mode="warn"))
        assert "synthetic@" in warn.bootstrap()[0].content
        custom = ColdStartManager(store, "custom", seed_memory_path=path, defense=MemoryDefense(patterns=[("PRIVATEWORD", "custom")], exclude_patterns=["email"]))
        assert custom.bootstrap()[0].content == "contact synthetic@example.invalid [REDACTED:custom]"
        seed_file(tmp_path, [{"content": "safe", "type": "unknown"}])
        with pytest.raises(ValueError, match="Invalid seed partition"):
            ColdStartManager(store, "bad", seed_memory_path=path).bootstrap()
        assert store.count_atoms_by_agent("bad") == 0
    finally:
        store.conn.close()
