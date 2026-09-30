from datetime import datetime, timedelta
from dataclasses import replace
import sqlite3

import pytest

from vibe_memory import VibeMemory
from vibe_memory.edges.edge_builder import build_same_session_edges
from vibe_memory.models.memory_atom import MemoryAtom, EdgeStatus


@pytest.mark.parametrize("status", list(EdgeStatus))
def test_append_preserves_existing_edge_and_counts_only_new_edges(status):
    memory = VibeMemory(agent_id="agent", embedding_backend="tfidf")
    try:
        atoms = [MemoryAtom(id=name, agent_id="agent", session_id="session",
                            content=name, summary=name,
                            created_at=datetime(2020, 1, 1) + timedelta(seconds=i))
                 for i, name in enumerate(("a", "b", "c"))]
        for atom in atoms[:2]:
            memory.storage.insert_atom(atom)
        original = build_same_session_edges(atoms[:2])[0]
        original.weight = 0.42
        original.created_at = datetime(2020, 1, 1)
        original.last_accessed = datetime(2021, 1, 1)
        original.version = 7
        original.status = status
        memory.storage.insert_edge(original)
        before = dict(memory.storage.conn.execute("SELECT * FROM edges").fetchone())
        memory.storage.insert_atom(atoms[2])
        memory._auto_build_edges(atoms[2])
        after = dict(memory.storage.conn.execute(
            "SELECT * FROM edges WHERE from_atom_id='a' AND to_atom_id='b'"
        ).fetchone())
        assert after == before
        assert len(memory.storage.get_all_edges_raw()) == 2
        assert memory._edge_count == 1
        memory._auto_build_edges(atoms[2])
        assert len(memory.storage.get_all_edges_raw()) == 2
        assert memory._edge_count == 1
    finally:
        memory.storage.conn.close()


def test_public_store_retains_edge_history_on_session_append():
    memory = VibeMemory(agent_id="agent", embedding_backend="tfidf")
    try:
        for i, text in enumerate(("数据库连接池最大连接数为二十", "文档导出格式使用纯文本文件")):
            atom = memory.store(text, session_id="s", auto_episode=False)
            memory.storage.conn.execute("UPDATE atoms SET created_at=? WHERE id=?", (
                (datetime(2020, 1, 1) + timedelta(seconds=i)).isoformat(), atom.id))
            memory.storage.conn.commit()
        original = memory.storage.get_all_edges()[0]
        original.weight = 0.42
        original.last_accessed = datetime(2021, 1, 1)
        memory.storage.update_edge(original)
        before = dict(memory.storage.conn.execute("SELECT * FROM edges").fetchone())
        memory.store("任务队列使用先入先出的顺序", session_id="s", auto_episode=False)
        assert dict(memory.storage.conn.execute(
            "SELECT * FROM edges WHERE id=?", (original.id,)
        ).fetchone()) == before
        assert memory._edge_count == 2
    finally:
        memory.storage.conn.close()


def test_missing_pair_insertion_keeps_explicit_replacement_and_direction():
    memory = VibeMemory(agent_id="agent", embedding_backend="tfidf")
    try:
        atoms = [MemoryAtom(id=n, agent_id="agent", session_id="s", content=n, summary=n)
                 for n in ("a", "b")]
        for atom in atoms:
            memory.storage.insert_atom(atom)
        edge = build_same_session_edges(atoms)[0]
        assert memory.storage.insert_edge_if_missing(edge)
        replacement = replace(edge, id="replacement", weight=0.42)
        assert not memory.storage.insert_edge_if_missing(replacement)
        memory.storage.insert_edge(replacement)
        assert memory.storage.get_edge(edge.id) is None
        assert memory.storage.get_edge("replacement").weight == 0.42
        reverse = replace(edge, id="reverse", from_atom_id="b", to_atom_id="a")
        assert memory.storage.insert_edge_if_missing(reverse)
        assert len(memory.storage.get_all_edges_raw()) == 2
        with pytest.raises(sqlite3.IntegrityError):
            memory.storage.insert_edge_if_missing(replace(edge, id="reverse", to_atom_id="c"))
        memory.storage.conn.rollback()
        assert len(memory.storage.get_all_edges_raw()) == 2
    finally:
        memory.storage.conn.close()
