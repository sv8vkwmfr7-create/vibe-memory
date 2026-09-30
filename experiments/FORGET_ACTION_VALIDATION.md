# Explicit forgetting action — 2026-09-29

## Follow-up: actual SDK ingestion and derived-artifact trace — 2026-09-30

[Runner](forget_sdk_path_probe.py), [synthetic seed fixture](fixtures/forget_seed_fixture.json) and [report](../results/forget_sdk_path_probe.json) run existing SDK methods in three disposable file databases with TF-IDF. Inputs are one explicitly configured seed template, six dialogue messages and two single stores with deliberately identical `config` tags. There are no monkeypatches, direct atom inserts, production changes, real-data deletions, model downloads or paid calls. UUIDs/timestamps are generated normally; the report omits their values while checking actual ID relationships. Runner, fixture and seven relevant SDK files are pinned by SHA-256.

| Actual path | Observed source/deletion behavior | Boundary |
| --- | --- | --- |
| Configured seed bootstrap + SDK recall/inject | Persisted clone uses `source=seed_memory`. After `forget` succeeds, database atom count is 0 and the clone ID is absent, but an unpersisted `__seed__` template returns through cold-start augmentation and its old fact appears in the MAC prompt | Seed configuration is explicit/opt-in; default SDK without a seed path does not show this behavior |
| Same client bootstrap / reopen | Same-client second bootstrap adds 0 rows; reopening without seed config returns no old fact. Reconfiguring the seed path and explicitly bootstrapping restores a persisted clone with a new UUID | Bootstrap flag is per client; this is a demonstrated configured seed replay, not spontaneous default reimport |
| SDK batch chunking + deletion | Stores three assistant-centered atoms, all with the same session source string. After deleting the first, two remain; one carries the old fact in copied `context_before/after`, and SDK recall returns that structured context | Returned `content`/`summary` and the MAC prompt do not contain the old fact in this batch fixture; context retention does not establish final-answer misuse |
| SDK Episode aggregation | One episode is created from the three compatible-tag chunks. After deletion its summary retains the fact and `atom_ids` still references the deleted atom | Demonstrated Episode-table retention; the experiment does not show episode summaries entering core recall or the prompt |
| SDK replay of the same dialogue/session | The same messages generate fresh atom UUIDs and the fact returns to recall | Session ID alone neither identifies the individual source turn nor suppresses source replay |
| SDK auto merge after two stores | Identical tags trigger current cold-phase merge. Both parent rows disappear; the second store returns an atom ID no longer persisted. The live merged record names the immediate parent UUIDs in `source`, points `previous_version_id` to a removed parent, and retains only the first session ID | Merge selection here uses tag overlap; this is not evidence of semantic duplication or loss of all metadata in every merge |
| Deleting old parent ID / live merged ID | Old parent ID deletion returns false and merged fact remains recalled. Deleting the actual live merged ID succeeds and removes its recall | Explicit-ID deletion still works on the live row; parent-to-descendant source tracking is absent in this trace |

Two normalized reports are byte-identical (SHA-256 `688415f8a419a6618d4a39b9b9d6243af713a3cf01afcd36d841244db86daf34`). Targeted report-boundary test **1 passed in 0.61s**; full regression **446 passed in 134.50s**. It intentionally records current unresolved behavior, not a passing product-level forgetting guarantee. No new SDK/MCP/HTTP release-interface tests were added. This assistant-authored scenario is not independent user evaluation; dense models, final LLM answers, all agents/tenants, concurrent readers/queues, physical/WAL/backups and user time/price costs remain unverified. The private 96-row review remains paused.

### First implementation target after the trace

Prioritize the configured **seed route**, because old evidence already reaches a prompt with zero database rows. A database-insert-only guard cannot cover it. A seed-scoped pilot must associate both template and persisted clone with one stable source-record identity, persist suppression under tenant/agent scope when that source is explicitly forgotten, and consult it in both `bootstrap` and `augment_recall`. Test warmed template cache, reopen/reconfigure, new clone UUID, unrelated seeds and other-agent/tenant protection. Keep external seed files unchanged; file cleanup is a separate operation. Decide explicit source-forgetting versus single-live-atom deletion semantics before product integration; this trace changes neither API.

The broader source plan also needs copied context lineage and Episode invalidation/rebuilding, not just content/summary atoms. Merge must preserve both source roots before deleting parents; a string of removed UUIDs is not durable source identity. The observed stale `store` return ID should be tracked as a separate SDK contract issue rather than silently worked around by parsing arbitrary source strings. Next is a narrowly scoped seed suppression pilot, with this unmodified-SDK trace retained as its baseline.

```powershell
.\.venv\Scripts\python.exe -m experiments.forget_sdk_path_probe --json results/forget_sdk_path_probe.json
.\.venv\Scripts\python.exe -m pytest -q tests/test_forget_sdk_path_probe.py
```

## Follow-up: source lineage and one transaction — 2026-09-30

[Runner](forget_transaction_probe.py) and [report](../results/forget_transaction_probe.json) use six local and two foreign-tenant synthetic atoms, four fixed edges and TF-IDF in one temporary file database. Two experiment-only tables store scoped root-source keys and their atom memberships. A child inherits its parents' root keys when inserted, so a copy of a copy and a two-source summary retain their ancestry. These keys are explicit fixture assertions, not automatically discovered or authenticated provenance. Production code is unchanged.

| Check | Observed result |
| --- | --- |
| Before deletion | Original, copy, copy-of-copy and mixed-source summary all recalled; scoped FTS matches 4 |
| Missing lineage / foreign-tenant parent / unknown source | Rejected with unchanged row snapshot |
| Inject failure after blocking source, deleting edges/atoms/lineage, before commit | All table rows restored; original recall and FTS results restored |
| Second connection attempts guarded write while first holds `BEGIN IMMEDIATE` | Receives `SQLITE_BUSY`; after deletion commits, the same-source write is rejected |
| Successful transaction and reopen | Four descendants and two incident edges removed; scoped FTS matches 0; two local calendar records, their edge and the foreign-tenant pair/edge remain |
| Same source, new atom ID, after reopen | Rejected by persisted source block |
| Unrelated source / same source key in another tenant | Both imports allowed |
| Old content deliberately assigned another root key / direct production storage write | Both accepted and recalled; complete forgetting remains unproven |

The mixed-source summary is wholly removed because it carries the deleted source; its unrelated information is not selectively redacted. The original calendar evidence remains. This is a conservative fixture policy with a visible cost, not evidence that all unrelated derived content is preserved. The two-connection schedule tests SQLite lock serialization, not concurrent load, crash/power-loss durability or distributed coordination. SQL atom deletion runs existing FTS triggers; semantic/BM25 recall is checked afterward and after reopen, not immediate process-memory erasure.

The existing SDK/storage operations commit each atom themselves, so this fixture uses minimal SQL inside one `BEGIN IMMEDIATE` transaction for source blocking, all incident-edge cleanup, atom deletion and lineage cleanup. Fixture import performs block checking, atom insertion and inherited lineage insertion under the same writer transaction. It rejects records without declared lineage. It does not alter SDK `forget`, nor exercise SDK store/batch/seed/merge/update or episode aggregation. Two report runs match byte-for-byte (SHA-256 `a7b405010522826ca888b42013cf865fa8a5fb7bf45c70a1f4e40e314cce61ed`); runner hash matches the report. Related experiment tests: **3 passed in 0.47s**; full regression **445 passed in 82.29s**. No models downloaded, paid calls or real user data deleted. Independent evaluation and user time/price costs remain open; the 96-row human review stays paused.

### Concrete integration design and remaining work

The intended guarantee is that evidence from an explicitly forgotten source and its registered descendants cannot be recalled or silently restored by importing that old source again. A new, intentional user statement may create new evidence under its own source identity; forgetting does not imply a permanent text/keyword ban. The fixture's relabeling bypass reuses old evidence without preserving identity, and demonstrates why identity must be owned by the ingestion system.

| Existing path, confirmed in code | Required integration behavior |
| --- | --- |
| `sdk.store` and `sdk.store_batch` → `storage.insert_atom` | Ingestion owns stable source-record identity and preserves it on replay; insert and scoped suppression check share a transaction |
| `coldstart.bootstrap` → `storage.insert_atom` with a fresh UUID | Preserve source identity independently of cloned atom UUID; consult suppression before seed reinsertion |
| `sdk._auto_build_edges` → merged insert + two deletes | Merge unions all root sources and writes new lineage before atom replacement, in the same transaction |
| `sdk.update` → `storage.update_atom` | Content updates carry validated provenance and suppression checks, rather than bypassing an insert-only guard |
| Episode summaries and `atom_ids` | Record summary lineage; delete or rebuild affected summaries from surviving evidence before serving them |
| Recall caches / cold-start cache / queued indexing | Invalidate after committed deletion and coordinate in-flight reads/queued work; verify another client's warm recall cannot serve old evidence |

Keep root-source records scoped by tenant and agent and retain opaque suppression metadata when content is deleted. Source IDs are not tenant/agent authorization tokens. Caller ownership checks, imported origin validation, source replay identity, deletion preview/confirmation and handling of legacy records lacking lineage must be defined before integration. Do not silently assume legacy sources are complete or manufacture their lineage from keywords. A shared storage transaction boundary must replace internal per-row commits for the integrated operation; this experiment does not implement that refactor.

At this transaction-experiment stage, the next proposed check was the actual SDK seed/batch/merge/episode trace, now executed above. Its findings prioritize a seed suppression pilot. Separate agent scope, stale caches/queues, multi-source summary policy and concurrent replay remain release checks. Physical/WAL/backup erasure and deletion of external raw/seed files remain separate unverified requirements.

```powershell
.\.venv\Scripts\python.exe -m experiments.forget_transaction_probe --json results/forget_transaction_probe.json
.\.venv\Scripts\python.exe -m pytest -q tests/test_forget_transaction_probe.py
```

## Follow-up: known-ID deletion plan — 2026-09-30

The experiment-only [runner](forget_plan_probe.py) and [report](../results/forget_plan_probe.json) use a disposable synthetic TF-IDF SQLite database. The fixture names one original ID and one manually authored derivative ID, plus an unrelated pair; it plants one incident edge and one unrelated protected edge. No real provenance discovery or user-data deletion occurs. A missing target is rejected before mutation. The runner then records both known IDs in an experiment-only suppression table, deletes the observed incident edge by ID, and invokes the existing SDK `forget` once per named atom. This sequence is **not atomic** and is not a production importer or API.

| Check | Observed result |
| --- | --- |
| Before action | Both targets recalled; 2 target rows, 2 unrelated rows, 1 incident edge, 1 protected edge |
| After action and after reopen | Neither target recalled; 0 target rows and incident edges; both unrelated rows and protected edge retained |
| Guarded import by old ID or declared source ID | Both rejected; unrelated records still retrievable |
| Import with a new ID and no source metadata | Accepted and recalled: the same fact is restored |

Two runs produced byte-identical JSON reports. Targeted experiment test **1 passed** and full regression **444 passed in 101.71s**. The test checks these boundaries, not deletion of every derivative. This establishes a narrow, explicitly enumerated cleanup in this fixture; **complete fact-level forgetting remains unproven**. The tombstone check can be bypassed by an importer that does not use it or lacks trustworthy lineage. Physical/WAL/backups, real generated derivatives, graph reachability, concurrent writes, all tenants/import paths, natural-language target selection, final-answer behavior and user time/price costs remain unverified. Production SDK/MCP defaults are unchanged; there are no paid calls or new downloads. The private 96-row human review remains paused.

Reproduce with `.\.venv\Scripts\python.exe -m experiments.forget_plan_probe --json results/forget_plan_probe.json` and `.\.venv\Scripts\python.exe -m pytest -q tests/test_forget_plan_probe.py`. At this stage the next proposed step was a durable-lineage/transaction experiment, now executed above. Production enforcement on every importer and separate realistic, independently reviewed cases still remain open. Do not turn this fixture into keyword-based or automatic user-data deletion.

## Actual controlled execution

`experiments/forget_action_probe.py` runs the existing SDK `forget` and `recall` against a disposable file SQLite database with TF-IDF. It manually inserts three assistant-authored synthetic atoms: original preference, a derivative copy, and an unrelated fact, plus one fixed similarity edge. IDs and timestamps are fixed. No actual user data, PersonaMem sensitive content, LLM generation, model installation or paid API is involved. Fixture import deliberately uses storage, not the SDK chunk/merge pipeline; this is not an MCP/HTTP end-to-end test or independent preference evaluation.

The original must actually be retrieved with warmed semantic/BM25 cache keys before the action; otherwise the runner fails. It calls `forget('original')`, observes the next recall, closes/reopens the SDK and database, then deliberately reinserts the original source through storage. Two independent temporary-database runs produced **exactly equal reports**. The minimal experiment test first failed on the missing runner, then passed: **1 passed in 0.64s**. Full regression **443 passed in 157.97s**; software regression is not evidence of complete forgetting. No production implementation or SDK/MCP interface tests were added; the test checks this experiment's report boundaries.

## Results

| Phase | Original row/recall | Manually copied fact | Incident edge rows | Index-cache boundary |
| --- | --- | --- | --- | --- |
| Before action | Present / retrieved | Retrieved | 1 | Both keys contain original |
| Immediately after forget, before recall | Deleted; API returns true | Not targeted | Not measured separately | Old semantic/BM25 keys still retained |
| Next warmed recall | Absent / not returned | Still retrieved | 1 | Both refreshed keys exclude original |
| Reopened database/client | Absent / not returned | Still retrieved | 1 | Fresh recall excludes original |
| Direct source reimport | Present / retrieved again | Still retrieved | 1 | Refreshed keys include original again |

Deletion of the explicitly identified original is effective in this fixture, including the next recall and restart. Cache-key change refreshes the retrieval indexes at the next query; it is not immediate process-memory erasure. A retained incident row does not by itself prove reachable graph leakage. The derivative copy is deliberately planted, not evidence that a real summarizer created or leaked it. Direct reimport is an intentional bypass, not a claim that every importer resurrects records.

**Complete fact-level forgetting is not demonstrated.** Single-atom deletion does not remove the independently stored copy, clean the observed incident edge row or prevent the demonstrated raw-source reimport. No natural-language target resolution was implemented or tested. Physical SQLite/WAL/backups, seed-memory files, real summaries/episodes, dense model vectors, all graph paths, cross-agent/tenant ownership, concurrency, final answers and user costs are unverified. These findings do not mean the explicit-ID deletion API failed; they narrow the guarantee it actually provided here.

## Reproduction and next step

```powershell
.\.venv\Scripts\python.exe -m experiments.forget_action_probe --json results/forget_action_probe.json
.\.venv\Scripts\python.exe -m pytest -q tests/test_forget_action_probe.py
```

The report contains only fixed synthetic IDs and bounded observations; its runner-source SHA-256 pins the fixture/logic. No timing fields or performance/cost claims. Temporary synthetic databases are removed after closed connections; real user data and production defaults are untouched. The private 96-row human review remains paused.

At this baseline stage, the next proposed experiment was an explicit plan for known original/derived IDs and incident edges plus importer-side suppression. That experiment has now run; see the 2026-09-30 section above. Neither stage authorizes keyword-based or automatic deletion of real user data. Natural-language confirmation, persistent provenance and retention semantics still need separate design decisions before product integration.
