import pytest
from datetime import datetime

from vibe_memory import VibeMemory
from vibe_memory.chunking.chunker import ChunkingConfig, chunk_session, should_ingest
from vibe_memory.models.memory_atom import MemoryAtom


def test_chunk_limit_preserves_all_text_context_and_order():
    text = "token预算设置为2048。" * 4
    messages = [{"role": "user", "content": "原始问题"},
                {"role": "assistant", "content": text},
                {"role": "assistant", "content": "后续内容"}]
    chunks = chunk_session(messages, "agent", "s", ChunkingConfig(max_chunk_chars=7))
    first = chunks[:-1]
    assert all(len(atom.content) <= 7 for atom in chunks)
    assert "".join(atom.content for atom in first) == text
    assert all("原始问题" in atom.context_before for atom in first)
    assert all("后续内容" in atom.context_after for atom in first)
    assert [atom.episode_position for atom in chunks] == list(range(1, len(chunks) + 1))
    assert len({atom.id for atom in chunks}) == len(chunks)
    assert messages[1]["content"] == text


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_chunk_limit_is_rejected(limit):
    with pytest.raises(ValueError, match="max_chunk_chars"):
        ChunkingConfig(max_chunk_chars=limit)


def test_previous_atom_and_threshold_control_lexical_novelty():
    previous = MemoryAtom(id="a", agent_id="agent", session_id="s", content="abcd", summary="abcd")
    assert not should_ingest("abcd", previous)
    assert should_ingest("abXY", previous, threshold=0.5)
    assert not should_ingest("abXY", previous, threshold=0.6)
    assert should_ingest("完全不同的话题", previous)
    assert should_ingest("error", previous, threshold=1.0)
    assert not should_ingest("OK", previous, threshold=0.0)


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_novelty_threshold_is_rejected(threshold):
    with pytest.raises(ValueError, match="threshold"):
        should_ingest("text", None, threshold)


def test_sdk_filters_whole_response_before_splitting_acknowledgment_tail():
    memory = VibeMemory("agent", embedding_backend="tfidf")
    text = "正文" * 1000 + "已"
    try:
        chunks = memory.store_batch([
            {"role": "assistant", "content": text}, {"role": "assistant", "content": "OK"},
        ], session_id="s")
        assert [len(atom.content) for atom in chunks] == [2000, 1]
        assert "".join(atom.content for atom in chunks) == text
        assert memory._store_count == 2
        assert len(memory.storage.get_atoms_by_session("s", agent_id="agent")) == 2
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize("text,limit", [("", 1), ("abcd", 4), ("abcde", 4), ("甲😀乙", 1)])
def test_empty_exact_limit_and_unicode_content_are_preserved(text, limit):
    chunks = chunk_session([{"role": "assistant", "content": text}], "agent", "s",
                           ChunkingConfig(max_chunk_chars=limit, context_window=0))
    assert "".join(atom.content for atom in chunks) == text
    assert all(len(atom.content) <= limit for atom in chunks)
    assert all(atom.context_before == atom.context_after == "" for atom in chunks)


@pytest.mark.parametrize("window", [-1, True, 1.5])
def test_invalid_context_window_is_rejected(window):
    with pytest.raises(ValueError, match="context_window"):
        ChunkingConfig(context_window=window)


def test_direct_chunking_retains_routine_replies_unless_filter_requested():
    messages = [{"role": "user", "content": "问题"}, {"role": "assistant", "content": "OK"}]
    chunks = chunk_session(messages, "agent", "s")
    assert [atom.content for atom in chunks] == ["OK"]
    assert chunks[0].episode_position == 1
    assert chunk_session(messages, "agent", "s", filter_routine=True) == []


def test_split_positions_preserve_persisted_order_on_timestamp_ties(monkeypatch):
    import vibe_memory.chunking.chunker as chunker
    class FixedClock:
        @staticmethod
        def now():
            return datetime(2020, 1, 1)
    monkeypatch.setattr(chunker, "datetime", FixedClock)
    memory = VibeMemory("agent", embedding_backend="tfidf")
    text = "甲" * 2000 + "乙" * 2000 + "丙"
    try:
        stored = memory.store_batch([{"role": "assistant", "content": text}], session_id="s")
        persisted = memory.storage.get_atoms_by_session("s", agent_id="agent")
        assert [atom.id for atom in persisted] == [atom.id for atom in stored]
        assert [atom.episode_position for atom in persisted] == [0, 1, 2]
        assert "".join(atom.content for atom in persisted) == text
        assert all(atom.episode_id for atom in persisted)
    finally:
        memory.storage.conn.close()
