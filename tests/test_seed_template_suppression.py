import json

import pytest

from vibe_memory import VibeMemory
from vibe_memory.coldstart import ColdStartManager
from vibe_memory.storage.sqlite_store import VibeStorage


@pytest.fixture
def seed_path(tmp_path):
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps({"version": "one", "atoms": [{"content": "Configuration color is violet", "tags": ["config"]}]}), encoding="utf-8")
    return str(path)


def memory(db):
    return VibeMemory(agent_id="agent", db_path=str(db), embedding_backend="tfidf")


def test_bootstrapped_version_does_not_augment_from_template(seed_path, tmp_path):
    mem = memory(tmp_path / "test.db")
    try:
        mem.cold_start.seed_memory_path = seed_path
        stored = mem.cold_start.bootstrap()
        assert mem.storage.get_atom(stored[0].id) is not None
        result = {"atoms": [], "trace": "keep"}
        assert mem.cold_start.augment_recall("config violet", result) == {"atoms": [], "trace": "keep"}
    finally:
        mem.storage.conn.close()


def test_forget_removes_fact_from_recall_and_prompt_across_reopen(seed_path, tmp_path):
    db = tmp_path / "test.db"
    mem = memory(db)
    try:
        mem.cold_start.seed_memory_path = seed_path
        stored = mem.cold_start.bootstrap()
        assert any("violet" in atom.content for atom in mem.recall("config violet")["atoms"])
        assert mem.forget(stored[0].id)
        assert not any("violet" in atom.content for atom in mem.recall("config violet")["atoms"])
        assert "violet" not in mem.inject("config violet").lower()
    finally:
        mem.storage.conn.close()
    reopened = memory(db)
    try:
        reopened.cold_start.seed_memory_path = seed_path
        assert reopened.cold_start.bootstrap() == []
        assert reopened.recall("config violet")["atoms"] == []
        assert "violet" not in reopened.inject("config violet").lower()
    finally:
        reopened.storage.conn.close()


def test_uninitialized_version_still_augments(seed_path):
    store = VibeStorage(":memory:")
    try:
        cm = ColdStartManager(store, "agent", seed_memory_path=seed_path)
        result = cm.augment_recall("config violet", {"atoms": []})
        assert result["augmented"]
        assert result["atoms"][0].agent_id == "__seed__"
    finally:
        store.conn.close()


def test_marker_does_not_suppress_other_tenant_agent_or_changed_document(seed_path):
    from pathlib import Path
    store = VibeStorage(":memory:")
    try:
        ColdStartManager(store, "a", seed_memory_path=seed_path).bootstrap()
        for tenant, agent in (("default", "b"), ("other", "a")):
            cm = ColdStartManager(store, agent, tenant_id=tenant, seed_memory_path=seed_path)
            assert cm.augment_recall("config violet", {"atoms": []})["atoms"]
        data = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        data["version"] = "two"
        Path(seed_path).write_text(json.dumps(data), encoding="utf-8")
        cm = ColdStartManager(store, "a", seed_memory_path=seed_path)
        assert cm.augment_recall("config violet", {"atoms": []})["atoms"]
    finally:
        store.conn.close()


def test_other_connection_cached_templates_observe_completion(seed_path, tmp_path):
    db = str(tmp_path / "shared.db")
    first, second = VibeStorage(db), VibeStorage(db)
    try:
        reader = ColdStartManager(second, "agent", seed_memory_path=seed_path)
        assert reader.augment_recall("config violet", {"atoms": []})["atoms"]
        writer = ColdStartManager(first, "agent", seed_memory_path=seed_path)
        stored = writer.bootstrap()
        first.delete_atom(stored[0].id)
        assert reader.augment_recall("config violet", {"atoms": []})["atoms"] == []
    finally:
        first.conn.close()
        second.conn.close()


def test_failed_delete_retains_persisted_fact_and_completed_template_policy(seed_path):
    import sqlite3
    mem = memory(":memory:")
    try:
        mem.cold_start.seed_memory_path = seed_path
        stored = mem.cold_start.bootstrap()
        mem.storage.conn.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON atoms BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
        with pytest.raises(sqlite3.IntegrityError):
            mem.forget(stored[0].id)
        assert mem.storage.get_atom(stored[0].id) is not None
        assert any(atom.id == stored[0].id for atom in mem.recall("config violet")["atoms"])
        assert mem.cold_start.augment_recall("config violet", {"atoms": []})["atoms"] == []
    finally:
        mem.storage.conn.close()
