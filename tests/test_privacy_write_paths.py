import pytest

from vibe_memory import VibeMemory
from vibe_memory.defense import MemoryDefense


SENSITIVE = "contact: synthetic@example.invalid"


@pytest.fixture
def memory():
    mem = VibeMemory(agent_id="privacy", db_path=":memory:", embedding_backend="tfidf")
    yield mem
    mem.storage.conn.close()


@pytest.mark.parametrize("field", ["summary", "context_before", "context_after"])
def test_store_redacts_explicit_text_fields(memory, field):
    atom = memory.store("safe content", **{field: SENSITIVE}, auto_build_edges=False)
    assert "synthetic@" not in getattr(memory.storage.get_atom(atom.id), field)
    assert "[REDACTED:email]" in getattr(atom, field)


@pytest.mark.parametrize("field", ["summary", "context_before", "context_after"])
def test_store_block_checks_auxiliary_fields_before_writing(memory, field):
    memory.defense = MemoryDefense(mode="block")
    with pytest.raises(ValueError) as error:
        memory.store("safe content", **{field: SENSITIVE})
    assert "synthetic@" not in str(error.value)
    assert memory.history() == []
    assert memory._store_count == 0


@pytest.mark.parametrize("field", ["content", "summary"])
def test_update_redacts_text(memory, field):
    atom = memory.store("safe content", auto_build_edges=False)
    updated = memory.update(atom.id, **{field: SENSITIVE})
    assert "synthetic@" not in getattr(updated, field)
    assert getattr(memory.storage.get_atom(atom.id), field) == getattr(updated, field)


@pytest.mark.parametrize("field", ["content", "summary"])
def test_update_block_is_non_mutating(memory, field):
    atom = memory.store("safe content", auto_build_edges=False)
    before = memory.storage.get_atom(atom.id)
    memory.defense = MemoryDefense(mode="block")
    with pytest.raises(ValueError) as error:
        memory.update(atom.id, **{field: SENSITIVE, "weight": 9})
    assert "synthetic@" not in str(error.value)
    assert memory.storage.get_atom(atom.id) == before


def test_batch_redacts_before_summary_truncation_and_context_copy(memory):
    sensitive = "sk-" + "A" * 40
    messages = [{"role": "user", "content": SENSITIVE},
                {"role": "assistant", "content": "error " + "x" * 175 + " " + sensitive},
                {"role": "assistant", "content": "error safe response"}]
    originals = [dict(message) for message in messages]
    atoms = memory.store_batch(messages, session_id="batch")
    assert len(atoms) == 2
    assert messages == originals
    for atom in memory.history("batch"):
        for field in ("content", "summary", "context_before", "context_after"):
            assert "synthetic@" not in getattr(atom, field)
            assert "sk-" not in getattr(atom, field)


def test_blocked_late_batch_message_leaves_no_partial_writes(memory):
    memory.defense = MemoryDefense(mode="block")
    with pytest.raises(ValueError) as error:
        memory.store_batch([{"role": "assistant", "content": "error safe response"},
                            {"role": "assistant", "content": "error another safe response"},
                            {"role": "assistant", "content": SENSITIVE}], session_id="batch")
    assert "synthetic@" not in str(error.value)
    assert memory.history("batch") == []
    assert memory.storage.get_all_edges() == []
    assert memory.storage.get_episodes_by_session("batch") == []
    assert memory._store_count == 0


def test_warn_preserves_text_across_store_update_and_batch(memory):
    memory.defense = MemoryDefense(mode="warn")
    atom = memory.store(SENSITIVE, summary=SENSITIVE, context_before=SENSITIVE, context_after=SENSITIVE, auto_build_edges=False)
    assert all(getattr(atom, field) == SENSITIVE for field in ("content", "summary", "context_before", "context_after"))
    assert memory.update(atom.id, summary=SENSITIVE).summary == SENSITIVE
    batch = memory.store_batch([{"role": "assistant", "content": SENSITIVE}], session_id="warn")
    assert batch[0].content == SENSITIVE


def test_custom_patterns_and_exclusions_apply_to_auxiliary_fields(memory):
    memory.defense = MemoryDefense(patterns=[("PRIVATEWORD", "custom")], exclude_patterns=["email"])
    atom = memory.store("safe", summary=SENSITIVE + " PRIVATEWORD", auto_build_edges=False)
    assert atom.summary == SENSITIVE + " [REDACTED:custom]"
    assert memory.update(atom.id, content="PRIVATEWORD").content == "[REDACTED:custom]"


def test_block_preflights_user_messages_even_without_assistant_chunks(memory):
    memory.defense = MemoryDefense(mode="block")
    with pytest.raises(ValueError):
        memory.store_batch([{"role": "user", "content": SENSITIVE}])
    assert memory.history() == []


def test_foreign_update_does_not_scan_or_write(memory, monkeypatch):
    from vibe_memory.models.memory_atom import MemoryAtom
    memory.storage.insert_atom(MemoryAtom(id="foreign", agent_id="other", session_id="s", content="safe", summary="safe"))
    monkeypatch.setattr(memory.defense, "scan", lambda text: pytest.fail("foreign input must not be scanned"))
    assert memory.update("foreign", content=SENSITIVE) is None
    assert memory.storage.get_atom("foreign").content == "safe"


@pytest.mark.parametrize("field", ["content", "summary", "context_before"])
def test_invalid_text_input_fails_before_writing(memory, field):
    kwargs = {"content": "safe", field: 123}
    with pytest.raises(ValueError, match="must be strings"):
        memory.store(**kwargs)
    assert memory.history() == []
