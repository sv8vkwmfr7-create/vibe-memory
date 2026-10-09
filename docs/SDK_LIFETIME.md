# SDK resource lifetime

`VibeMemory` owns its SQLite connection. Prefer a context manager:

```python
from vibe_memory import VibeMemory

with VibeMemory("my-agent", "memory.db", embedding_backend="tfidf") as memory:
    memory.store("timeout set to 60 seconds", session_id="chat-1")
```

Alternatively, call `memory.close()` in `finally`. Closing is repeatable.
Normal and exceptional context exits close the connection; caller exceptions
are not suppressed. A closed instance cannot be entered again or used through
SDK methods: these raise `RuntimeError("VibeMemory is closed")`. Create a new
instance to reopen a database. Committed records remain available on reopen;
an in-memory database does not survive closure.

Close uses the existing maintenance admission then per-instance lock, matching
other SDK operations. The `with` body is not one transaction or one held lock.
Do not nest or share context lifetimes: each exit closes the same instance.

Close does **not** call `flush_index`, run an LLM, checkpoint WAL, clear the index
queue, or commit caller-managed transactions. Pending edge candidates exist
only in memory and are not restored on reopen. To process them, explicitly use
`flush_index` before closing; a single flush is batch-limited. Direct access to
`storage`, `indexer`, or other collaborators bypasses the SDK lifetime contract.

This adds no destructor or automatic cleanup for abandoned instances.
Once storage construction succeeds, later SDK initialization failures close
that connection before propagating the initialization error. Successful
construction transfers ownership to the SDK as before. This does not cover
failures inside the storage constructor itself or undo schema initialization.
LangChain helper ownership now delegates to this SDK close/context contract;
see [adapter contracts](ADAPTER_CONTRACTS.md). Storage-constructor failures,
OpenAI legacy factory callers, remaining process owners and forced termination are
separate work. Existing OpenAI factory return type
and its seven functions are unchanged; no model-facing close tool is added.
The OpenAI factory can now borrow this SDK using `create_vibe_tools(memory=memory)`;
keep the whole tool workflow inside the SDK lifetime. It never takes ownership
of that borrowed SDK. Legacy factory calls without memory remain unmanaged.

## Regression seam

`tests/test_sdk_lifetime.py` uses temporary synthetic databases and public SDK
close/context/store/history interfaces. Default/WAL cases cover repeated close,
rejected post-close use, persistence on reopen, normal/exceptional context exits,
and no ResourceWarning after collection of explicitly managed instances.
Public-constructor invalid-backend cases also cover failure cleanup in default
and WAL databases, exact backend error preservation, existing records on reopen,
and successful writes after the failed startup.
No private-method calls, SQL assertions, internal mocks or paid model calls.
ResourceWarning absence alone on older Python versions is not causal proof.
