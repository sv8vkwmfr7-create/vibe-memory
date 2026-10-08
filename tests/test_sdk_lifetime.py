import gc
import warnings

import pytest

from vibe_memory import VibeMemory, WALMaintenance


@pytest.mark.parametrize("wal", [False, True])
def test_close_is_repeatable_rejects_use_and_preserves_stored_memory(tmp_path, wal):
    path = str(tmp_path / "memory.db")
    options = {"embedding_backend": "tfidf"}
    if wal:
        options.update(journal_mode="wal", wal_maintenance=WALMaintenance(path))
    memory = VibeMemory("lifetime", path, **options)
    try:
        atom = memory.store("timeout set to 60 seconds", session_id="s",
                            auto_build_edges=False, auto_episode=False)
        memory.close()
        memory.close()
        with pytest.raises(RuntimeError, match="VibeMemory is closed"):
            memory.history(session_id="s")
        with pytest.raises(RuntimeError, match="VibeMemory is closed"):
            memory.store("must not be saved", session_id="s")
        reopened = VibeMemory("lifetime", path, **options)
        try:
            assert [row.id for row in reopened.history(session_id="s")] == [atom.id]
        finally:
            reopened.storage.conn.close()
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize("wal", [False, True])
@pytest.mark.parametrize("exceptional", [False, True])
def test_context_exit_closes_without_suppressing_errors(tmp_path, wal, exceptional):
    path = str(tmp_path / "context.db")
    options = {"embedding_backend": "tfidf"}
    if wal:
        options.update(journal_mode="wal", wal_maintenance=WALMaintenance(path))
    gc.collect()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        memory = VibeMemory("lifetime", path, **options)
        try:
            if exceptional:
                with pytest.raises(ValueError, match="caller failure"):
                    with memory as active:
                        assert active is memory
                        active.store("saved before exception", session_id="s",
                                     auto_build_edges=False, auto_episode=False)
                        raise ValueError("caller failure")
            else:
                with memory as active:
                    assert active is memory
                    active.store("saved normally", session_id="s",
                                 auto_build_edges=False, auto_episode=False)
            with pytest.raises(RuntimeError, match="VibeMemory is closed"):
                memory.history(session_id="s")
            with pytest.raises(RuntimeError, match="VibeMemory is closed"):
                with memory:
                    pytest.fail("closed SDK must not be entered again")
        except BaseException:
            memory.storage.conn.close()
            raise
        del active, memory
        gc.collect()
    assert not [item for item in caught if issubclass(item.category, ResourceWarning)]
    reopened = VibeMemory("lifetime", path, **options)
    try:
        expected = "saved before exception" if exceptional else "saved normally"
        assert [row.content for row in reopened.history(session_id="s")] == [expected]
    finally:
        reopened.storage.conn.close()
