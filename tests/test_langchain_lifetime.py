import gc
import warnings

import pytest

from vibe_memory.langchain import VibeMemoryLC


def test_close_is_repeatable_and_preserves_saved_context(tmp_path):
    path = str(tmp_path / "memory.db")
    memory = VibeMemoryLC(agent_id="lifetime", db_path=path)
    try:
        memory.save_context({"input": "database timeout"}, {"output": "timeout set to 60 seconds"})
        memory.close()
        memory.close()
        with pytest.raises(RuntimeError, match="VibeMemory is closed"):
            memory.load_memory_variables({"input": "database timeout"})
        with pytest.raises(RuntimeError, match="VibeMemory is closed"):
            memory.save_context({"input": "database timeout"}, {"output": "must not be saved"})
        reopened = VibeMemoryLC(agent_id="lifetime", db_path=path)
        try:
            history = reopened.load_memory_variables({"input": "database timeout"})["history"]
            assert "timeout set to 60 seconds" in history
            assert "must not be saved" not in history
        finally:
            reopened.mem.close()
    finally:
        memory.mem.close()


@pytest.mark.parametrize("exceptional", [False, True])
def test_context_exit_closes_and_preserves_caller_exception(tmp_path, exceptional):
    path = str(tmp_path / "context.db")
    gc.collect()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        memory = VibeMemoryLC(agent_id="lifetime", db_path=path)
        try:
            if exceptional:
                with pytest.raises(ValueError, match="caller failure"):
                    with memory as active:
                        assert active is memory
                        active.save_context({"input": "database timeout"}, {"output": "saved before exception"})
                        raise ValueError("caller failure")
            else:
                with memory as active:
                    assert active is memory
                    active.save_context({"input": "database timeout"}, {"output": "saved normally"})
            with pytest.raises(RuntimeError, match="VibeMemory is closed"):
                memory.load_memory_variables({"input": "database timeout"})
            with pytest.raises(RuntimeError, match="VibeMemory is closed"):
                with memory:
                    pytest.fail("closed helper must not be entered again")
        except BaseException:
            memory.mem.close()
            raise
        del active, memory
        gc.collect()
    assert not [item for item in caught if issubclass(item.category, ResourceWarning)]
    reopened = VibeMemoryLC(agent_id="lifetime", db_path=path)
    try:
        expected = "saved before exception" if exceptional else "saved normally"
        history = reopened.load_memory_variables({"input": expected})["history"]
        assert expected in history
    finally:
        reopened.mem.close()


def test_clear_deletes_context_without_closing_helper(tmp_path):
    with VibeMemoryLC(agent_id="lifetime", db_path=str(tmp_path / "clear.db")) as memory:
        memory.save_context({"input": "banana harvest"}, {"output": "banana harvest completed"})
        memory.clear()
        assert memory.load_memory_variables({"input": "banana harvest"}) == {"history": ""}
        memory.save_context({"input": "quartz satellite"}, {"output": "quartz satellite launched"})
        assert "quartz satellite launched" in memory.load_memory_variables({"input": "quartz satellite"})["history"]
