# Adapter and reranker contracts — 2026-09-30

## OpenAI Agents SDK

`create_vibe_tools()` returns seven plain Python functions, preserving direct calls without an Agents SDK dependency. It does **not** return `FunctionTool` instances. Wrap each function before attaching it to an Agent, as in the [official function-tool guidance](https://developers.openai.com/api/docs/guides/tools):

```python
from agents import Agent, function_tool
from vibe_memory import VibeMemory
from vibe_memory.openai_agents import create_vibe_tools

with VibeMemory("my-agent", "memory.db", embedding_backend="tfidf") as memory:
    functions = create_vibe_tools(memory=memory)
    agent = Agent(name="Assistant", tools=[function_tool(fn) for fn in functions])
    # Complete Agent/Runner execution inside this lifetime.
```

The keyword-only `memory=` borrows an existing SDK; it does not create, close
or flush that SDK. Caller configuration is authoritative. Combining it with
non-default `agent_id`, `db_path` or `embedding_backend` raises ValueError,
including when a supplied value happens to match the borrowed SDK. Leave those
arguments at their defaults and configure the SDK itself. Caller `close/with`
controls lifetime; retaining tools past that lifetime does not reopen a database.
SDK-backed store/recall/stats calls reject closed use. Empty session-end calls
and direct-storage link failures retain existing behavior, not a new uniform
closed-error contract. No model-facing close tool is introduced.

Calls without `memory=` retain the legacy constructor and seven-function list.
That list has no close handle; legacy unmanaged callers must migrate to the
caller-owned pattern for deterministic cleanup. No destructor-based cleanup or
warning suppression is added. Tests use real temporary SDKs without Agents SDK
or cloud calls. On 2026-10-08 the real offline framework smoke was refreshed
using caller-owned SDK with; it is distinct from these plain-function tests.

The tested wrapper/Runner version is `openai-agents==0.22.3` (Python 3.12.14). Offline smoke builds all seven tool schemas and runs store then recall through the real Runner with a scripted Model. This proves dispatch and memory persistence/recall, not cloud authentication, autonomous tool choice, answer quality, streaming or compatibility with every SDK version. Existing JSON output/short-ID/session semantics remain; no new tools or automatic wrapper are added.

## LangChain-style helper

`VibeMemoryLC` provides `memory_variables`, `save_context`, `load_memory_variables`, and `clear`. It is not a `BaseMemory` subclass and is not a drop-in `memory=` object for legacy chains that require one. It does not implement LangGraph state/checkpointing or asynchronous memory execution.

Use explicit read/save wiring. The tested framework boundary is `langchain-core==1.6.6`, using an actual `RunnableLambda` sequence and two synchronous invocations. The sequence loads history, computes a deterministic synthetic response, then calls `save_context`. The second invocation sees the first saved output. The helper itself does not automatically intercept a framework's conversation.

```python
from langchain_core.runnables import RunnableLambda
from vibe_memory.langchain import VibeMemoryLC

with VibeMemoryLC() as memory:
    read_history = RunnableLambda(memory.load_memory_variables)
    history = read_history.invoke({"input": "database timeout"})
    # After your chain responds, save explicitly:
    memory.save_context({"input": "database timeout"}, {"output": "timeout set to 60s"})
```

`VibeMemoryLC` owns its SDK and now exposes repeatable `close()` plus context
management. Normal and exceptional exits close without deleting committed
records, suppressing caller exceptions or flushing indexes. Nonempty load/save
calls after close fail through the SDK closed guard. Metadata/empty no-op calls
are not promised to fail. Do not nest or share context lifetimes: each exit
closes the same instance. `clear()` remains explicit deletion, not close; save
and load remain usable after clearing an open helper. The alias
`VibeMemoryMemory` shares these methods. No automatic abandoned-instance cleanup
or broader async/framework compatibility is added. See [SDK lifetime](SDK_LIFETIME.md).

The OpenAI factory now supports the caller-owned pattern above while retaining
legacy hidden-SDK construction for compatibility. Existing adapter tests and
offline framework smoke adopted explicit lifetime on 2026-10-08; one legacy
factory creation test remains for compatibility. Other unmanaged owners and
constructor-failure cleanup remain separate tasks.

## Reranking

The production recall path calls `rerank_by_similarity`, which combines cosine similarity and RRF scores when enabled by the existing mode/backend conditions. It does not use the `Reranker` class. `Reranker` is a compatibility placeholder: it returns `candidates[:top_k]` with unchanged order/scores; an optional provider's query encoding is attempted and discarded, including a silent pass-through on encoding failure. It is not zero-cost if that provider performs work. No cross-encoder/LLM scorer classes exist in this module. They remain unimplemented; this repair corrects the claim rather than implementing or enabling speculative scorers.

## Reproduce the offline smoke

Install the two exact framework versions in a disposable environment along with this project and its normal dependencies, then from the repository run:

```shell
python -m experiments.adapter_framework_smoke
```

The script disables OpenAI tracing and blocks external socket connects, allowing only Windows asyncio's loopback wakeup connection. Disable LangSmith tracing in the environment as well (`LANGSMITH_TRACING=false`). The observed output reports seven tools, both workflows true, a scripted model, zero cloud model calls and the exact framework versions. This is a local smoke, not an external benchmark.

Local verification used a separate temporary pip `--target` directory, without changing project dependency declarations or the project environment's installed distributions. On Windows this requires `site.addsitedir(target)` to process pywin32's `.pth` paths; simply adding the target to `PYTHONPATH` was insufficient. A first all-connect block also rejected asyncio's internal socketpair; the final script allows loopback but still blocks external connects. No compatibility claim relies on either failed setup run.
