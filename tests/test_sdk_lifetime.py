import gc
import warnings

import pytest

from vibe_memory import VibeMemory, WALMaintenance


@pytest.mark.parametrize("wal", [False, True])
def test_failed_construction_releases_connection_and_preserves_backend_error(tmp_path, wal):
    path = str(tmp_path / "failed-startup.db")
    options = {}
    if wal:
        options.update(journal_mode="wal", wal_maintenance=WALMaintenance(path))
    with VibeMemory("lifetime", path, embedding_backend="tfidf", **options) as memory:
        atom = memory.store("saved before failed startup", session_id="s",
                            auto_build_edges=False, auto_episode=False)

    def attempt():
        try:
            VibeMemory("lifetime", path, embedding_backend="invalid-fixture-backend",
                       **options)
        except ValueError as error:
            return str(error)
        pytest.fail("invalid backend must reject construction")

    gc.collect()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        outcome = attempt()
        gc.collect()
    assert outcome == (
        "Unknown backend: invalid-fixture-backend. Use 'tfidf', 'st', or 'auto'.")
    assert not [item for item in caught if issubclass(item.category, ResourceWarning)]
    with VibeMemory("lifetime", path, embedding_backend="tfidf", **options) as reopened:
        assert [row.id for row in reopened.history(session_id="s")] == [atom.id]
        reopened.store("saved after failed startup", session_id="s",
                       auto_build_edges=False, auto_episode=False)
        assert len(reopened.history(session_id="s")) == 2


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
