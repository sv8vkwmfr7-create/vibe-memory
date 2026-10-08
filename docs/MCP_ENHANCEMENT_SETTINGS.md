# MCP enhancement settings — first implementation

## Link ID safety — 2026-10-03

After user approval of the existing stdio/temporary-store seam, two failing
source/target collision cases reproduced incorrect edge creation. `vibe_link`
now prioritizes exact full IDs and accepts an eight-character prefix only if it
uniquely identifies an atom within the current tenant and agent. Ambiguity raises
JSON-RPC tool error -32000 (`Ambiguous atom ID prefix; use full IDs`) before
calling link; no edge is written. Unknown/partial IDs retain the existing
not-found error payload. Tool parameter descriptions no longer promise every
eight-character prefix is enough. No new tool or return field was added.

Fourteen real-stdio checks pass (4.18s); combined MCP/panel regression: 69 passed
/ 28.28s. Deterministic UUID fixtures use public SDK store with TF-IDF, no direct
SQL assertions or mocked collaborators. Recall traces verify actual endpoint
identity, not causal direction. Exact eight-character full IDs, colliding full
IDs, unique prefixes, invalid IDs and foreign tenant/agent endpoints are covered.
Full local regression: 883 passed / 105.81s on Windows/Python 3.12.14, with
HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1. This includes existing cached local
model tests, not live host/model proof or blanket network isolation. Reproduce
with `python -m pytest -q --basetemp NEW_UNUSED_TEMP_DIRECTORY`; use a new path
to avoid deleting prior test evidence. The existing all-atom hydration and scoped linear
lookup remain; this is not a large-store performance fix or historical-edge repair.
Forget's pre-existing ambiguity guard and legacy short response fields are
unchanged. No real database, host configuration, cloud request, release or push.

2026-10-02: `vibe_settings` reads local settings; `{"enhanced": false}` or true
explicitly changes the preference. Default is true. Settings are atomically
replaced in `<vibe-dir>/settings.json`; the directory is the configuration scope,
so separate agents requiring separate preferences must use separate directories.
Invalid or unreadable settings fail visibly instead of silently enabling.
Concurrent settings writers are last-writer-wins; no cross-process coordination.

`vibe_recall` returns at most 5/15/3 memories for precision/recall/budget when
enabled and at most two in any mode when disabled, retaining the existing SDK
candidate generation and legacy fields. These are MCP output limits; SDK
`top_k` still controls its candidate/result budget and ranking is unchanged.
`count` describes returned memories. New fields: `enhanced`, `selection_status`,
`selection_verified` (always false), and `selection_instructions`.
Enabled status is `pending_host_selection`: the host model is asked to choose
at most two applicable evidence records, but the server cannot enforce host
behavior or certify selection. No API, credentials, sampling or extra model
request is introduced. Disabled mode is not a cloud privacy guarantee: returned
memories may still reach the host's provider.

Disabling enhancement explicitly applies the two-record compact output policy,
including recall/budget modes. Returned records now retain full `content` and
add `full_id` and `full_session_id`; legacy short `id`/`session_id` fields remain
for compatibility. Use `full_id` for evidence selection and references, not
the display prefix. Summaries remain previews, not substitutes for content.
`vibe_session_start` reads the same persisted preference, including after restart,
and injects at most five records when enabled or two when disabled. Its response
uses the same enhancement/selection state fields as recall; enabled injection
also includes the untrusted-evidence selection instructions. Both the response
`memories` and injection JSON contain full content and full IDs. The injection
labels records as untrusted evidence in either mode. File creation does not
prove a host read it or resisted instructions embedded in evidence.

The third batch reproduced missing trailing qualifiers and absent session-start
evidence via stdio, then corrected both paths. MCP regression: 48 passed.
This verifies exact source-text delivery in synthetic temporary stores with
enhancement on/off, not answer quality or live-client selection.
Follow-up compatibility run on Windows/Python 3.12.14:
`python -m pytest -q --basetemp .pytest-tmp-mcp-firstfive-full-20261002`
— 862 passed in 96.05 seconds. This includes existing cached local-model tests;
no live host/cloud integration test or coverage measurement was added.
Current transport additionally caps the `memories` JSON list at 20,000 Unicode
characters (`json.dumps(..., ensure_ascii=False)` length). Apply mode record
limits first, then keep whole records in original order if they fit; skip records
that do not fit and continue considering smaller records in that eligible list.
Never cut the source `content`. `evidence_budget` reports limit/used characters,
omitted full IDs and completeness of this eligible list, not global recall.
`failures` adds `mcp_evidence_budget_exceeded` when any eligible record is omitted;
returned count describes only delivered records. Session injection carries the
same budget warning. Hosts must check omissions and abstain when evidence is
insufficient, including with enhancement off. No on-demand oversized-record MCP
fetch was added; the original remains stored and accessible through existing SDK.
This is not a whole-response/injection-header limit, byte limit, tokenizer limit,
model context guarantee, storage limit or measured invoice. Very long evidence
may be excluded rather than delivered. The initial unbounded full-text batch
above is historical; this subsequent controlled budget changes that contract.
Oversized-record stdio test failed before the cap and passed after implementation;
combined smaller-record overflow is also covered in recall and session start.
Latest budget batch: panel/MCP subset 55 passed / 18.80 seconds; full regression
869 passed / 98.93 seconds with model-hub offline flags. Not live host evidence.
That transport batch did not change short-ID mutation resolution or relationship
display fields. The subsequent link-specific fix above rejects ambiguous link
prefixes; it is not certification of every display or historical collision path.

The second batch reproduced the previous universal five-record recall cap and
session-start bypass with failing stdio tests, then corrected both. Targeted MCP
regression: `tests/test_mcp_enhancement.py tests/test_mcp.py` — 46 passed
(temporary stores, stdio subprocesses). This is not a full-suite or live-client
end-to-end result.

## Terminal settings panel and first-use acknowledgement

Run from the repository with the same directory configured for your MCP server:

```powershell
.venv/Scripts/python.exe -m vibe_memory.settings --vibe-dir .vibe
```

The installed entry point is `vibe-settings` (new installs/reinstalls only).
The panel displays configuration path/scope, enhanced state, confirmation state,
provider/quota warning, and unsupported future toggles. Enter confirms the notice
and keeps the current setting (true on first use); `on`/`off` saves the chosen
setting; `cancel`, EOF, or interruption leaves preferences unchanged. Invalid
configuration produces a visible error and is not overwritten.
No HTTP listener, extra dependency, API credentials, or model selection is added.

MCP and panel use the same validated atomic storage implementation. Legacy files
without acknowledgement migrate in memory to `privacy_acknowledged=false`; no
implicit human confirmation is written. Only the local panel records this flag;
`vibe_settings` rejects attempts to set it through MCP. The MCP settings response
also includes configuration location/scope and the privacy notice. Changes to
`enhanced` through the existing tool preserve acknowledgement.

Acknowledgement is a local UX record, not authentication or an evidence-disclosure
gate: existing MCP retrieval remains compatible and defaults on. Hosts must
present/approve installation and settings writes; tool descriptions alone cannot
prove human authorization or defeat prompt injection. Do not approve setting
changes merely because stored memory requests them. Configure host tool approval
and complete the panel before connecting user data. Separate agents sharing the
same vibe directory share both preference and acknowledgement; concurrent writes
remain last-writer-wins.

Tests first failed because the panel was absent; the bad-config check then exposed
non-UTF-8 stderr on Windows. After implementation/fix, panel and MCP regression:
52 passed in 18.43 seconds. Cancellation, restart, on/off, invalid configuration,
and MCP acknowledgement forgery are checked through CLI/stdio with temporary
directories. This does not prove a human UI session or host approval enforcement.
Follow-up full regression with model-hub offline flags: 866 passed in 97.99
seconds on Windows/Python 3.12.14; this is not a blanket network-isolation proof.

Host-specific token budgets, host-selection feedback and actual client end-to-end
proof remain pending. Codex 0.159.0-alpha.12.1 is installed; a read-only check of
configured server names found no acceptance server. No credentials were printed.
The chosen target is Codex desktop, not a substitute CLI inference experiment.
The user explicitly declined adding the acceptance entry at this stage. No Codex
config was changed, and no live host inference was run. The user subsequently
chose to skip desktop acceptance for now; it is deferred, not passed. See
`docs/CODEX_DESKTOP_ACCEPTANCE.md` for the pending acceptance procedure.
Latest host choice supersedes that plan: ZCode TUI, per the user's request.
`docs/ZCODE_MCP_ACCEPTANCE.md` records the installed CLI's JSON configuration
schema and isolated acceptance results. After approval, ZCode CLI received a
backed-up acceptance entry and discovered 9 connected tools; Codex stayed untouched.
The first GLM request failed with service error 1113 before tool execution.
Start Plan free quota is now required, but no such route is visible in the TUI;
real-host inference/authorization acceptance remains incomplete.
Local regression used synthetic temporary-directory stdio tests. The approved
live TUI connection also uses an isolated acceptance store, not real user data.
Only ZCode CLI MCP configuration changed; no release, commit or push performed.
