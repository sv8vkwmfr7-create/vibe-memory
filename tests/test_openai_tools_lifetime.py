import inspect
import json
import gc
from contextlib import nullcontext

import pytest

from vibe_memory import VibeMemory
from vibe_memory.openai_agents import create_vibe_tools


def test_factory_borrows_sdk_and_keeps_seven_plain_functions(tmp_path):
    with VibeMemory("borrowed", str(tmp_path / "memory.db"), embedding_backend="tfidf") as memory:
        first = memory.store("database timeout set to 60 seconds", session_id="s",
                             auto_build_edges=False, auto_episode=False)
        tools = create_vibe_tools(memory=memory)
        assert type(tools) is list
        assert all(inspect.isfunction(tool) for tool in tools)
        assert [tool.__name__ for tool in tools] == [
            "vibe_store", "vibe_recall", "vibe_session_start", "vibe_session_end",
            "vibe_stats", "vibe_link", "vibe_forget",
        ]
        functions = {tool.__name__: tool for tool in tools}
        assert json.loads(functions["vibe_stats"]())["total_atoms"] == 1
        second = json.loads(functions["vibe_store"]("database timeout reviewed", session_id="s"))
        assert {row.id for row in memory.history(session_id="s")} == {first.id, second["full_id"]}
        recalled = json.loads(functions["vibe_recall"]("database timeout"))
        assert {row["full_id"] for row in recalled["memories"]} == {first.id, second["full_id"]}


@pytest.mark.parametrize("options", [
    {"agent_id": "other-agent"},
    {"db_path": "must-not-open.db"},
    {"embedding_backend": "st"},
])
def test_borrowed_sdk_rejects_nondefault_construction_options(tmp_path, options):
    options = dict(options)
    if "db_path" in options:
        options["db_path"] = str(tmp_path / options["db_path"])
    with VibeMemory("borrowed", str(tmp_path / "memory.db"), embedding_backend="tfidf") as memory:
        with pytest.raises(ValueError, match="memory cannot be combined"):
            create_vibe_tools(memory=memory, **options)
        assert memory.history() == []


@pytest.mark.parametrize("exceptional", [False, True])
def test_borrowed_tools_follow_caller_lifetime_and_preserve_records(tmp_path, exceptional):
    path = str(tmp_path / "context.db")
    with pytest.raises(ValueError, match="caller failure") if exceptional else nullcontext():
        with VibeMemory("borrowed", path, embedding_backend="tfidf") as memory:
            functions = {tool.__name__: tool for tool in create_vibe_tools(memory=memory)}
            stored = json.loads(functions["vibe_store"]("timeout reviewed", session_id="s"))
            if exceptional:
                raise ValueError("caller failure")
    for name, arguments in [
        ("vibe_store", {"content": "must not persist"}),
        ("vibe_recall", {"query": "timeout reviewed"}),
        ("vibe_stats", {}),
    ]:
        with pytest.raises(RuntimeError, match="VibeMemory is closed"):
            functions[name](**arguments)
    with VibeMemory("borrowed", path, embedding_backend="tfidf") as reopened:
        assert [row.id for row in reopened.history(session_id="s")] == [stored["full_id"]]


def test_discarding_borrowed_tools_does_not_close_caller_sdk(tmp_path):
    with VibeMemory("borrowed", str(tmp_path / "discard.db"), embedding_backend="tfidf") as memory:
        tools = create_vibe_tools(memory=memory)
        del tools
        gc.collect()
        atom = memory.store("caller still owns memory", session_id="s",
                            auto_build_edges=False, auto_episode=False)
        assert [row.id for row in memory.history(session_id="s")] == [atom.id]


def test_owned_tools_close_and_preserve_records(tmp_path):
    path = str(tmp_path / "owned.db")
    tools = create_vibe_tools(agent_id="owned", db_path=path)
    functions = {tool.__name__: tool for tool in tools}
    stored = json.loads(functions["vibe_store"]("timeout reviewed", session_id="s"))
    tools.close()
    tools.close()
    with pytest.raises(RuntimeError, match="VibeMemory is closed"):
        functions["vibe_stats"]()
    with VibeMemory("owned", path, embedding_backend="tfidf") as reopened:
        assert [row.id for row in reopened.history(session_id="s")] == [stored["full_id"]]


@pytest.mark.parametrize("exceptional", [False, True])
def test_owned_tools_context_closes_without_losing_records(tmp_path, exceptional):
    path = str(tmp_path / "owned-context.db")
    with pytest.raises(ValueError, match="workflow failure") if exceptional else nullcontext():
        with create_vibe_tools(agent_id="owned", db_path=path) as tools:
            assert isinstance(tools, list)
            assert len(tools) == 7
            assert all(inspect.isfunction(tool) for tool in tools)
            assert tools[0].__name__ == "vibe_store"
            functions = {tool.__name__: tool for tool in tools}
            stored = json.loads(functions["vibe_store"]("context reviewed", session_id="s"))
            if exceptional:
                raise ValueError("workflow failure")
    tools.close()
    for name, arguments in [
        ("vibe_store", {"content": "must not persist"}),
        ("vibe_recall", {"query": "context reviewed"}),
        ("vibe_stats", {}),
    ]:
        with pytest.raises(RuntimeError, match="VibeMemory is closed"):
            functions[name](**arguments)
    with pytest.raises(RuntimeError, match="VibeMemory is closed"):
        with tools:
            pytest.fail("closed tools must not reenter")
    with VibeMemory("owned", path, embedding_backend="tfidf") as reopened:
        assert [row.id for row in reopened.history(session_id="s")] == [stored["full_id"]]
