# Review repair progress — 2026-09-30

This is a local repair record, not a release or a retrieval-quality benchmark.

## Batch 1a: configuration writes and safe deletion

- `vibe-init` now validates JSON object shape and TOML before changing configuration. Invalid files stop configuration instead of being replaced as empty files.
- Claude project configuration uses `.mcp.json`. When only the legacy `.claude/mcp.json` exists, its entries are copied to the new file; the legacy file is retained and reported for manual review.
- Existing configuration and instruction files are backed up as `<filename>.<unique-id>.bak` before changes. Writes use a flushed temporary file in the same directory and atomic replacement. Identical bytes are not rewritten; failed backup or replacement leaves the original file unchanged. Symlink destinations are refused.
- Codex command and arguments are escaped and parsed as TOML, including Windows paths and quoted values. An existing `vibe-memory` table is retained; a comment mentioning that name no longer prevents installation. Python 3.10 uses the conditional `tomli` dependency, while 3.11+ uses `tomllib`.
- SDK `forget` resolves exact IDs first, checks both tenant and agent ownership, and accepts a prefix only when it is at least eight characters and uniquely identifies an atom in that scope. Invalid input, missing IDs, ambiguous prefixes, and foreign ownership return `False` without deletion.
- MCP and OpenAI adapter deletion now delegate to this SDK contract; their first-prefix-match fallback has been removed.

Backups may contain sensitive configuration. Keep them private and restore deliberately; do not commit them. Atomic replacement protects individual files, not a multi-file transaction or concurrent external configuration editors. Generated configuration passing a parser is not proof that a real coding-agent session connected.

The original temporary regression run contained fixture mistakes; those were fixed before recording the functional red result: **15 failed, 15 passed, no fixture errors**. After implementation, the same 30 checks passed. Expanded configuration, deletion, real MCP stdio, adapter and doctor regression: **95 passed / 13.85s** on Windows/Python 3.12.14. Full local regression: **481 passed / 82.93s**, including 35 new checks and the pre-existing local experiment tests. This is not a published-commit CI count or independent memory-quality evaluation.

## Batch 1b: scoped history, GC and graph statistics

- Session queries now default to the storage tenant and accept an explicit agent filter. SDK `history` always supplies both tenant and agent; an empty session ID is no longer treated as “all sessions.”
- A shared `get_edges_by_agent` query checks the edge tenant and both existing endpoint atoms' tenant/agent. SDK active/pending edge counts, indexer graph counts, graph-size snapshots and GC sparsification use this query.
- Statistical/maintenance queries deliberately include cold and archived endpoints. Recall's active/warm-only edge query is unchanged. Orphan and inconsistent legacy edges are excluded, not physically deleted.
- Automatic Episode aggregation now uses the same scoped session query, preventing foreign atoms from entering an Episode when session names collide. Episode deduplication and general mixed-input builder behavior remain separate open issues.

After correcting synthetic fixture pairs to respect the existing unique endpoint-pair index, the final red run had **11 failures, no fixture errors**. The repaired and expanded isolation suite passed **14 checks / 6.45s**. SDK, tenant, GC, indexer and real MCP regression passed **136 checks / 13.44s** before the last three expanded checks were added. Final full local regression: **495 passed / 78.96s** on Windows/Python 3.12.14. These checks establish the tested isolation behavior, not independent retrieval quality or a published CI count.

This batch used a temporary shared SQLite database with two tenants and two agents, identical session names, active/pending/stale edges, malformed cross-scope edges, an orphan and cold/archived atoms. No cloud/model calls or production database migration were required. Trusted low-level all-edge APIs remain available; this is not a blanket claim that every storage method or mutation path now enforces SDK ownership.

## Batch 1c: update, migrate and link ownership

- SDK `update` and `migrate` require the atom's tenant and agent to match the instance. `link` requires both endpoints to match both values, including the case where both endpoints belong to another agent in the same tenant.
- `update` accepts only `content`, `summary`, `tags`, `scope`, `confidence`, `weight` and `decay_rate`. Unsupported fields raise `ValueError` before any mutation. IDs, ownership, sessions, partitions, timestamps, Episode references and version counters cannot be changed through arbitrary keyword arguments. Partition changes remain available through `migrate`.
- This also prevents a loaded owned atom's `id` being changed to another existing atom's ID before the storage UPDATE, which could previously overwrite the other row.
- MCP link failure guidance now describes the current tenant/agent requirement. A real stdio test verifies rejected foreign-agent links leave the physical edges table empty.

Functional red result: **15 failed, 9 passed**, without fixture errors. After repair, the 24 mutation checks and SDK/tenant/MCP/adapter regressions passed together: **132 passed / 17.31s**. One additional real MCP check was then added. Fixtures use synthetic atoms in a temporary shared SQLite database. Rejected operations compare database rows before/after; legitimate metadata updates, partition migration and owned links remain covered.

The first full run had **519 passed, 1 failed / 88.06s**: the existing SDK forgetting-path probe sometimes did not retain the target fact in its Episode summary. The probe failed 8/10 repeated runs. Diagnosis isolated equal timestamps and unspecified session row order: the scoped query added in batch 1b can use an index that orders timestamp ties by random atom IDs, not batch message position. The probe does not call update/migrate/link; its labels are deterministic, and no assertion was weakened.

A new fixed-timestamp three-atom regression failed with the wrong row order. Session reads now explicitly order by `created_at, episode_position, id`, preserving existing batch positions on timestamp ties. Isolation/mutation/forgetting-path checks then passed **40 / 8.33s**; the original probe passed **10/10** repeats. Final full local regression after this correction: **521 passed / 83.33s**, Windows/Python 3.12.14. This does not fix forgetting residue, Episode deduplication or general mixed-agent EpisodeBuilder behavior, nor establish independent memory quality.

Compatibility note: undocumented arbitrary/unknown update fields previously could be applied or silently ignored; they are now rejected. Trusted raw storage access and external concurrent ownership changes are not covered by these SDK checks. HTTP synchronization, authentication and production data migration remain separate work.

## Still open

1. HTTP production gateway, real browser validation and bounded concurrency/load evidence (local boundary repaired in batch 2).
2. Remaining privacy write-path/notification gaps, historical orphan audit/migration, complete derived-memory erasure, stable/bounded Episode identity and backpressure accounting (scanner fixed in 3a, graph lifecycle in 3b, affected Episode invalidation/live queue consumption in 3c).
3. Observability, supported-version compatibility, coverage and public documentation evidence.
4. MCP automatic edge-building policy and independently supported retrieval-quality improvements.

Batches 1a–1c did not change HTTP defaults; batch 2 intentionally requires HTTP authentication and explicit sessions. Retrieval defaults remain unchanged. No real configuration or user database was migrated. Python 3.10 execution, power-loss durability and real browser attack scenarios have not been verified.

## Batch 2: local HTTP security and synchronization

- Mandatory constructor/environment token, constant-time Bearer comparison, loopback-only binding, exact Host/Origin checks and no wildcard CORS. Only health/preflight are unauthenticated; data remains protected for allowed origins.
- Server-instance SDK/lock replaces class-shared memory/session state. Full session IDs round-trip explicitly; session end without an ID is rejected. SDK operations serialize under an instance RLock, outside network reads/writes.
- JSON object/framing/content-type checks, 1 MiB declared-body limit, 10-second socket timeout and generic internal errors. Standalone shutdown closes the connection after handler completion. Unknown link labels are rejected instead of silently becoming similar.
- Functional red: **9 failed**, no fixture errors. Expanded HTTP/adapter checks: **34 passed / 7.82s**. A real SQLite transaction interleaving test fails when the lock is disabled in a separate process and passes with the lock. Windows can reset an oversized upload when rejected without draining; the size-limit check sends only headers to prove rejection before body reads.

Compatibility and remaining limits are documented in `HTTP_SECURITY.md`; there are no new dependencies, real data migrations or model calls. These are local security regressions, not memory-quality evidence.

The first full run had **431 passed, 103 fixture errors / 88.46s** because Windows denied access to the default `pytest-of-ASYS` temporary directory. A targeted fixture-only run reproduced `PermissionError` before application setup. Using a checked, new unique repository-local `--basetemp` without deleting old directories yielded **534 passed / 92.40s**, Windows/Python 3.12.14. No test assertion was relaxed. No commit or push was performed.

Configuration schema references: [OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli#configure-with-configtoml), [Claude project scope](https://code.claude.com/docs/en/mcp#project-scope).

## Batch 3a: scanner false positives and overlapping redaction

- Low-confidence generic-key/card patterns require explicit credential/card labels instead of unconditional long-string matches. Chinese phone boundaries reject substrings of longer ASCII identifiers/digit sequences while retaining Chinese-adjacent numbers.
- Overlapping matches are unioned in original-coordinate space and replaced once. Leftmost/longest-at-equal-start type labels the union; every original finding remains available. Adjacent matches remain distinct.
- Existing warn/block/exclusion/custom-pattern contracts are retained. WARN documentation now correctly states that findings are returned without automatic logging. Violations contain raw matches and must remain private.
- Initial test runs were interrupted because the new SDK fixture accidentally used automatic model selection. It was corrected to explicit TF-IDF. The final 14 checks, run against HEAD's original scanner in a separate process without changing the working tree, gave **7 failed, 7 passed / 0.11s**. Repaired privacy/injection/adapter/HTTP regression: **81 passed / 7.71s**. Full local regression: **548 passed / 127.32s**, Windows/Python 3.12.14, using a checked new repository-local temporary directory.

See `PRIVACY_SCANNER.md` for the intentional unlabeled-secret/card detection tradeoff, unscanned write paths and unchanged SDK notification contract. No damaged real records were restored, no retrieval defaults changed, no new dependencies introduced and no commit/push performed. Remaining lifecycle work is deferred to its own transaction-focused batch.

## Batch 3b: transactional atom deletion and merge rewiring

- Deletion removes all incident edges before the atom within one transaction, rolling back on failure. It works with foreign-key enforcement on/off, does not globally enable enforcement, and leaves unrelated/historical orphan rows untouched.
- A shared storage merge transaction validates ownership/partition/scope, rewires both directions, preserves edge metadata and removes internal self-loops. Same-label/status pair duplicates keep the oldest row; differing labels/status or malformed incident edges refuse merging. Atom/edge insertion statements are reused via private noncommitting helpers; public inserts retain their existing commit behavior.
- Pure merged-content construction now preserves tenant/scope and rejects incompatible parents. SDK skips unrepresentable merges without deleting parents, returns the surviving merged ID on success, and invalidates its cache. Both storage operations reject an open caller transaction without changing it.
- Initial run: **8 failed / 0.22s**, comprising four functional failures (deletion, rollback and SDK survivor ID) and four missing-new-storage-entrypoint failures. After implementation the original eight passed; expanded lifecycle, GC, SDK, tenant/ownership and real MCP checks: **192 passed / 17.63s**, including 15 lifecycle checks.

First full run: **562 passed, 1 failed / 92.98s**. The existing SDK forgetting-path probe asserted the now-repaired defect that the returned store ID was absent. Its pass-through insertion observer now captures the actual incoming parent ID; it checks both parents absent, returned ID present and equal to the live merged ID. Legacy result field is retained with its measured false value. Unfixed seed/context/Episode/provenance residual assertions remain unchanged. The updated trace and lifecycle tests passed **16 / 0.42s**. Final full rerun: **563 passed / 100.76s**, Windows/Python 3.12.14 with a checked unique repository-local temporary directory.

See `ATOM_EDGE_LIFECYCLE.md` for duplicate-edge policy and remaining Episode/queue/version/erasure gaps. No actual user data was deleted/merged or migrated, no cloud/model calls added, no new dependencies, no retrieval thresholds/defaults changed, and no commit/push performed.

## Batch 3c: affected Episode invalidation and live queue consumption

- Delete/merge transactions invalidate affected same-owner Episode rows and clear surviving member pointers; retaining the old summary with a shortened member list is not treated as safe. Rollback restores the Episode and pointers. Unrelated owners/rows are preserved; no historical migration or automatic rebuilding is performed.
- Indexer reloads live endpoints before classification, rejects missing/foreign/self pairs, uses current content, and rejects content/version changes during classification. A final short BEGIN IMMEDIATE compare-and-insert closes the check/insert gap for other database connections; model callbacks remain outside transactions.
- flush_all uses consumed-queue progress rather than edge count. Positive batch limits are explicit. Below-threshold input cannot evict valid full-queue work; other backpressure/accounting behavior is unchanged.
- Original 12 checks: **11 failed, 1 passed / 0.34s**, no missing-entrypoint/fixture errors. Original expanded lifecycle/indexer run: **46 passed / 0.25s**. Expanded lifecycle/GC/scope/MCP checks: **124 passed / 35.77s** before the final guarded insertion change. Final guarded-path checks, including 16 new lifecycle cases and the updated SDK trace: **51 passed / 0.58s**. Final full local regression: **579 passed / 135.40s**, Windows/Python 3.12.14, checked unique repository-local temporary directory.
- The old forgetting trace assertion that Episode text/references survive failed after the fix (**1 failed / 0.60s**); it now asserts zero affected Episodes and no deleted-ID/summary residue. Surviving context/seed/reimport observations remain asserted. This is a changed observed behavior, not removal of remaining forgetting checks.

See `ATOM_EDGE_LIFECYCLE.md` for linear membership-scan cost, conservative invalidation tradeoff, queued RAM retention and remaining identity/provenance/erasure limits. Tests use synthetic in-memory data/TF-IDF; no production database migration or model call is added. No new dependency, retrieval default change, commit or push.
