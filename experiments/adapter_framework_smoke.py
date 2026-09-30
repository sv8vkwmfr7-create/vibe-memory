"""Offline framework integration smoke. Requires openai-agents and langchain-core.

Run from the repo with its interpreter: python -m experiments.adapter_framework_smoke
Only synthetic in-memory data; real framework dispatch, scripted model responses.
"""

import asyncio
import json
import socket
from importlib.metadata import version
from unittest.mock import patch


def run() -> dict:
    connect = socket.socket.connect
    def local_connect(sock, address):
        # Windows asyncio creates a loopback socketpair for its internal wakeup pipe.
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1"}:
            raise AssertionError("External connections forbidden")
        return connect(sock, address)
    with patch.object(socket.socket, "connect", local_connect), patch.object(
            socket.socket, "connect_ex", side_effect=AssertionError("External connections forbidden")):
        return _run_offline()


def _run_offline() -> dict:
    from agents import Agent, Runner, RunConfig, function_tool, set_tracing_disabled
    from agents.items import ModelResponse
    from agents.models.interface import Model
    from agents.usage import Usage
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
    from langchain_core.runnables import RunnableLambda
    from vibe_memory.langchain import VibeMemoryLC
    from vibe_memory.openai_agents import create_vibe_tools

    set_tracing_disabled(True)

    class ScriptedModel(Model):
        step = 0

        async def get_response(self, **kwargs):
            outputs = [item for item in kwargs["input"]
                       if isinstance(item, dict) and item.get("type") == "function_call_output"]
            if self.step == 0:
                name, args = "vibe_store", {"content": "Database timeout configured to 60 seconds",
                    "tags": ["config"], "summary": None, "session_id": None}
            elif self.step == 1:
                assert json.loads(outputs[-1]["output"])["status"] == "stored"
                name, args = "vibe_recall", {"query": "database timeout", "mode": "precision", "top_k": 5}
            else:
                memories = json.loads(outputs[-1]["output"])["memories"]
                assert any("60 seconds" in item["summary"] for item in memories)
                return ModelResponse(output=[ResponseOutputMessage(id="synthetic-final",
                    type="message", role="assistant", status="completed",
                    content=[ResponseOutputText(type="output_text", text="offline-tools-ok", annotations=[])])],
                    usage=Usage(), response_id="synthetic-final")
            self.step += 1
            return ModelResponse(output=[ResponseFunctionToolCall(id=f"synthetic-{self.step}",
                call_id=f"synthetic-call-{self.step}", type="function_call", name=name,
                arguments=json.dumps(args))], usage=Usage(), response_id=f"synthetic-{self.step}")

        def stream_response(self, **kwargs):
            raise NotImplementedError("Only non-streaming smoke")

    tools = [function_tool(fn) for fn in create_vibe_tools()]
    assert len(tools) == 7
    assert all(tool.params_json_schema["type"] == "object" for tool in tools)
    agent = Agent(name="offline-memory-smoke", model=ScriptedModel(), tools=tools)
    result = asyncio.run(Runner.run(agent, "synthetic memory workflow",
                                   run_config=RunConfig(tracing_disabled=True)))
    assert result.final_output == "offline-tools-ok"

    memory = VibeMemoryLC()
    try:
        def read(inputs):
            return {**inputs, **memory.load_memory_variables(inputs)}

        def respond(inputs):
            return {**inputs, "output": "Database timeout configured to 60 seconds"}

        def save(inputs):
            memory.save_context({"input": inputs["input"]}, {"output": inputs["output"]})
            return inputs

        chain = RunnableLambda(read) | RunnableLambda(respond) | RunnableLambda(save)
        chain.invoke({"input": "database timeout first session"})
        second = chain.invoke({"input": "database timeout next session"})
        assert "60 seconds" in second["history"]
        assert memory.mem.stats()["total_atoms"] == 4
    finally:
        memory.mem.storage.conn.close()
    return {"openai_agents": version("openai-agents"), "langchain_core": version("langchain-core"),
            "tool_count": len(tools), "agent_store_recall": True, "runnable_read_save": True,
            "model": "scripted", "cloud_model_calls": 0, "external_connect_forbidden": True}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
