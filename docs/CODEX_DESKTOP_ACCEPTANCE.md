# Codex desktop acceptance — pending live execution

Superseded host selection (2026-10-02): the user now wants ZCode instead of Codex.
Keep this document as history; current procedure is `ZCODE_MCP_ACCEPTANCE.md`.
Do not install the Codex example. No prior result is re-labelled as ZCode evidence.

2026-10-02. Target chosen by the user: Codex desktop. This document is a runbook,
not evidence of successful loading or inference. Local CLI version observed:
0.159.0-alpha.12.1. No acceptance server is configured yet.

## Configuration boundary

Add a distinct `vibe-memory-acceptance` server only after approval. Back up the
existing Codex config without printing it or any credentials. Preserve other
servers and unrelated settings. Use the repository virtualenv and an isolated
acceptance directory, never `.vibe/memory.db` or another real user store.

Example (replace the acceptance directory with the newly created absolute path):

```toml
[mcp_servers.vibe-memory-acceptance]
command = "C:/Users/ASYS/Desktop/VibeMemory/.venv/Scripts/python.exe"
args = ["-m", "vibe_memory.mcp_server", "--db-path", "ACCEPTANCE_DIR/memory.db", "--vibe-dir", "ACCEPTANCE_DIR", "--agent-id", "desktop-acceptance"]
cwd = "C:/Users/ASYS/Desktop/VibeMemory"
default_tools_approval_mode = "prompt"
enabled_tools = ["vibe_store", "vibe_recall", "vibe_session_start", "vibe_stats", "vibe_settings"]
```

First run the terminal panel for that same directory and confirm the provider,
quota and shared-directory notice. Installation and host approval remain separate
from `privacy_acknowledged`. Never approve setting changes sourced from memory.

Official configuration reference:
[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
The official instructions describe saving a server and restarting its connection.
CLI config presence alone is not proof that desktop has loaded it.

## Live evidence to collect

1. Show the loaded acceptance server and its tools in desktop. Record actual
   client/model shown, configuration path, agent and isolated directory. Do not
   substitute the CLI version for desktop version or guess the model.
2. Through MCP, store synthetic records: historical production timeout 30 seconds;
   a dated correction effective now changing production to 45 seconds; test-only
   timeout 60 seconds. Use distinct explicit summaries and environment scopes.
3. In a fresh conversation/session, ask the current production timeout. Invoke
   recall and answer using returned evidence, citing full IDs and dates/scope.
   Record tool results and final answer separately. Success requires 45 seconds,
   no test-environment leakage, and actual tool use rather than prompt recall.
4. Turn enhancement off with explicit human approval (or the terminal panel),
   query again, and record disabled state, at most two returned records and the
   actual answer. Do not equate a smaller payload with no network traffic.
5. Restart the connection/session and confirm the off state persists; re-enable
   with approval and confirm pending_host_selection, never verified selection.
6. Record wall time, observed tokens/usage if available, failure and fallback.
   Missing usage/cost is unknown, not zero. Do not infer an invoice from tokens.

Use fresh values unknown to the answering conversation when proving cross-session
memory; records and questions above are examples, not independent evaluation.
Do not send real user/employer content. Limit this to a few synthetic requests,
using the current dialogue model and its quota, not a separate API integration.

## Current acceptance status

- Terminal panel/MCP tests: 52 passed; not desktop acceptance.
- First-use cancellation/restart and config safety: protocol/CLI evidence only.
- Desktop loading, prompt-based write approvals and answer chain: not executed.
- Token/price totals and independent answer quality: unverified.
- No global configuration changes, model calls, commit or push performed here.

2026-10-02 user decision: do not modify Codex configuration yet. Therefore the
desktop acceptance gate remains open, not failed and not completed. Do not bypass
this decision with CLI inference, a new thread, or extracting login credentials.
Terminal panel and existing full regression now pass 866 tests / 97.99 seconds;
these are compatibility evidence only. Resume installation only when authorized.

## First-five completion audit

Compared against the current priority page, not only the passing test count:

| Priority | Authoritative local evidence | Remaining gate |
|---|---|---|
| 1: switch and mode contract | MCP mode budgets and persisted session-start tests; shared preference reads | Desktop-specific behavior belongs to priority 4 |
| 2: evidence and IDs | Exact long-text on/off transport, full IDs and scope fields; source-session display-prefix disambiguation; 20,000-character memories JSON cap with explicit whole-record omissions | Not tokenizer-specific; no oversized-record MCP fetch; legacy atom-prefix mutation collisions are not tested or repaired |
| 3: onboarding and safety | Terminal notice/acknowledgement; cancel/EOF/restart/bad-config tests; MCP cannot forge acknowledgement | Actual host approval is unverified; model-issued enhanced writes are still supported |
| 4: actual desktop chain | Runbook only; installation declined | Loading, tools, answer, restart, actual model/time/usage and approval enforcement all missing |
| 5: terminal panel | Runnable module, working on/off persistence through the same MCP configuration store, no HTTP listener | Not a static mock; real-host integration still gated by priority 4 |

The shared-prefix regression is a source-session identity test, not an atom UUID
prefix collision test, independent answer benchmark or security certification.
It passed without additional production edits; no red/green fix is claimed for
that new regression guard. Full objective remains incomplete.

Latest user instruction: skip desktop acceptance for now. Priority 4 and the
actual host authorization gate remain deferred, not satisfied. No configuration
modification or alternate-model/CLI experiment is authorized by this deferral.
