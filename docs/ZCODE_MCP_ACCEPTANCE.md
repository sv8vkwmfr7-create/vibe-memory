# ZCode TUI MCP acceptance — connected, inference incomplete

2026-10-02: the user changed the requested host from Codex to ZCode. Use the TUI
as previously requested; do not silently substitute headless `--prompt` calls.
Codex configuration remains untouched. The user subsequently approved isolated
ZCode configuration and requested Start Plan free quota only; no paid fallback.

## Locally verified integration surface

- `zcode --help` reports 0.16.9 and `/mcp list|status|connect|disconnect`.
- Installed npm launcher: `zcode-app-cli`, package version `3.14.4-30`, described
  as an unofficial terminal client. Package version and runtime help version are
  different identifiers, not proof of a successful MCP connection.
- Installed CONFIGURATION.zh-CN.md and cli-config.cjs identify
  `C:/Users/ASYS/.zcode/cli/setting.json` as CLI runtime settings.
  Desktop preferences and provider/login files are separate and will not be edited.
- Installed setting.example.json and bundled runtime schema use `mcp.servers`.
  A stdio entry accepts `type`, `command`, `args`, `cwd` and optional `env`.
  This is not Codex TOML or an unverified `mcpServers` copy-paste.
- Only setting keys/server names were inspected; no login/provider credentials
  were read or printed. Before installation, CLI settings had no named MCP servers.

## Isolated entry (installed after approval)

Merge only the new server into the existing JSON after approval; back up the
original first, preserve unrelated fields, and create a fresh acceptance directory.
Replace `ACCEPTANCE_DIR` below with its absolute path; never use the real `.vibe`
database. Validate JSON without printing the complete private settings file.

```json
{
  "mcp": {
    "servers": {
      "vibe-memory-acceptance": {
        "type": "stdio",
        "command": "C:/Users/ASYS/Desktop/VibeMemory/.venv/Scripts/python.exe",
        "args": ["-m", "vibe_memory.mcp_server", "--db-path", "ACCEPTANCE_DIR/memory.db", "--vibe-dir", "ACCEPTANCE_DIR", "--agent-id", "zcode-acceptance"],
        "cwd": "C:/Users/ASYS/Desktop/VibeMemory"
      }
    }
  }
}
```

Complete the local VibeMemory terminal notice/confirmation for that directory
before using user data. Restart/reload the TUI as necessary; use `/mcp list`,
`/mcp connect vibe-memory-acceptance`, and `/mcp status` to observe actual loading.
Do not assert live connection from schema validity alone. Use build/interactive
approval, not yolo; the actual approval UI and classification still need verification.
Never change the shared default model to carry out this test. Record the model
actually shown in the TUI; earlier GLM-5.3-Flash selection may be stale.

## Acceptance sequence

1. Observe server connected and tool discovery; record actual TUI/model version.
2. Store a few synthetic dated production/test facts via MCP. No employer/user
   content. In a fresh session ask the current production fact; require actual
   recall and an answer citing full IDs, checking effective date and environment.
3. Explicitly turn enhancement off (human terminal panel or approved MCP change),
   query again, and verify disabled state with at most two returned whole records.
4. Restart the connection/session, verify persisted state, then restore on with
   approval. Pending-host selection must not be labelled verified selection.
5. Preserve actual tool outputs and answer separately. Record time and observed
   usage; missing token/cost data is unknown, not zero. Respect the 20,000-character
   memories JSON budget and omissions. Stop after a few requests, not a new large
   coding-TUI benchmark. No separate API credentials or model calls are needed.

## Observed result and free-quota boundary (2026-10-02)

- Backed up CLI settings to
  `C:/Users/ASYS/.zcode/cli/setting.json.vibe-memory-20261002-d40b1937406a4fbc801747efd26a37f2.bak`,
  added only the acceptance entry, and verified all pre-existing fields unchanged.
  `ACCEPTANCE_DIR` is `C:/Users/ASYS/Desktop/VibeMemory/.zcode-acceptance-20261002-e2e`.
  The assistant operated the approved terminal notice: enhanced on, acknowledgement
  saved. This is not independent human-UI or host-approval evidence.
- Actual TUI `/mcp list`: `vibe-memory-acceptance`, connected, stdio, 9 tools.
  TUI version 3.14.4-30; runtime 0.16.9; build mode. The selected model was
  `account:zai-individual-coding-plan/GLM-5.3-Flash`, not a verified Start Plan route.
- One synthetic store prompt failed at the model stage before any tool execution:
  error 1113, `Insufficient balance or no resource package. Please recharge.`
  Observed duration approximately 1 second; displayed session tokens 0 is not
  proof of zero billing. No store/recall/answer/off/restart acceptance passed.
- User requested Start Plan free quota. `/model list` exposed only GLM-5.3 and
  GLM-5.3-Flash under the individual Coding Plan; `/help login` describes Coding
  Plan setup only. No Start Plan selection is currently visible in this TUI.
  Do not assume changing model names changes the quota route or manually forge
  account entitlement. Stop inference until a genuine free-quota route is verified.
- [Official model-connection documentation](https://zcode.z.ai/en/docs/configuration)
  describes account trial quota and provider-page quota status; live eligibility
  and remaining quota must be checked in the user's app. Installed provider docs
  distinguish runtime-managed `start-plan` and `individual-coding-plan` access;
  personal config must not override account access. No credential extraction,
  account/default-model change, recharge, or independent API fallback was performed.

Current status: actual MCP connection and discovery passed; model-backed
end-to-end and authorization gates remain open, pending usable free quota.

User decision (2026-10-02): preserve Start Plan routing and real-host acceptance
as deferred TODOs and move on. Do not retry inference or change host configuration
while deferred. Resume only when the genuine free-quota route is verified; keep
the connected-tool result separate from unfinished answer/approval/cost evidence.
