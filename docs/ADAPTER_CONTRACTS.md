# Adapter and reranker contracts — 2026-09-30

## OpenAI Agents SDK

`create_vibe_tools()` returns seven plain Python functions, preserving direct calls without an Agents SDK dependency. It does **not** return `FunctionTool` instances. Wrap each function before attaching it to an Agent, as in the [official function-tool guidance](https://developers.openai.com/api/docs/guides/tools):

```python
from agents import Agent, function_tool
from vibe_memory.openai_agents import create_vibe_tools

functions = create_vibe_tools(agent_id="my-agent", db_path="memory.db")
agent = Agent(name="Assistant", tools=[function_tool(fn) for fn in functions])
```

The tested wrapper/Runner version is `openai-agents==0.22.3` (Python 3.12.14). Offline smoke builds all seven tool schemas and runs store then recall through the real Runner with a scripted Model. This proves dispatch and memory persistence/recall, not cloud authentication, autonomous tool choice, answer quality, streaming or compatibility with every SDK version. Existing JSON output/short-ID/session semantics remain; no new tools or automatic wrapper are added.

## LangChain-style helper

`VibeMemoryLC` provides `memory_variables`, `save_context`, `load_memory_variables`, and `clear`. It is not a `BaseMemory` subclass and is not a drop-in `memory=` object for legacy chains that require one. It does not implement LangGraph state/checkpointing or asynchronous memory execution.

Use explicit read/save wiring. The tested framework boundary is `langchain-core==1.6.6`, using an actual `RunnableLambda` sequence and two synchronous invocations. The sequence loads history, computes a deterministic synthetic response, then calls `save_context`. The second invocation sees the first saved output. The helper itself does not automatically intercept a framework's conversation.

```python
from langchain_core.runnables import RunnableLambda
from vibe_memory.langchain import VibeMemoryLC

memory = VibeMemoryLC()
read_history = RunnableLambda(memory.load_memory_variables)
history = read_history.invoke({"input": "database timeout"})
# After your chain responds, save explicitly:
memory.save_context({"input": "database timeout"}, {"output": "timeout set to 60s"})
memory.mem.storage.conn.close()
```

## Reranking

The production recall path calls `rerank_by_similarity`, which combines cosine similarity and RRF scores when enabled by the existing mode/backend conditions. It does not use the `Reranker` class. `Reranker` is a compatibility placeholder: it returns `candidates[:top_k]` with unchanged order/scores; an optional provider's query encoding is attempted and discarded, including a silent pass-through on encoding failure. It is not zero-cost if that provider performs work. No cross-encoder/LLM scorer classes exist in this module. They remain unimplemented; this repair corrects the claim rather than implementing or enabling speculative scorers.

## Reproduce the offline smoke

Install the two exact framework versions in a disposable environment along with this project and its normal dependencies, then from the repository run:

```shell
python -m experiments.adapter_framework_smoke
```

The script disables OpenAI tracing and blocks external socket connects, allowing only Windows asyncio's loopback wakeup connection. Disable LangSmith tracing in the environment as well (`LANGSMITH_TRACING=false`). The observed output reports seven tools, both workflows true, a scripted model, zero cloud model calls and the exact framework versions. This is a local smoke, not an external benchmark.

Local verification used a separate temporary pip `--target` directory, without changing project dependency declarations or the project environment's installed distributions. On Windows this requires `site.addsitedir(target)` to process pywin32's `.pth` paths; simply adding the target to `PYTHONPATH` was insufficient. A first all-connect block also rejected asyncio's internal socketpair; the final script allows loopback but still blocks external connects. No compatibility claim relies on either failed setup run.
