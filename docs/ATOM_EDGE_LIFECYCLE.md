# Atom deletion and merge boundaries

## Same-session automatic edge insertion

SDK single and batch writes use `insert_edge_if_missing`: SQLite's directed-pair unique constraint skips an existing pair without changing any columns, including manual labels and pending/stale state. Only an actual insert increments SDK edge metrics. Explicit `insert_edge`/SDK link and indexer replacement behavior remain unchanged. A conflicting ID on a different pair still raises, rather than silently swallowing unrelated constraints. This does not reconcile old history, change timestamp-tie ordering, or prevent the builder from recomputing all session pairs.

## Delete

`VibeStorage.delete_atom(id)` deletes all incoming/outgoing edges (including pending and stale) before deleting the atom, in one SQLite transaction. Failure rolls back both changes. SDK forget, GC eviction and partition deletion share this path. Unrelated atoms and edges are not removed. Malformed cross-owner edges incident to the deleted ID are also removed because retaining them would create orphans.

SDK ownership and unique-prefix checks remain required; raw storage is a trusted interface, not an authorization layer. These operations require a connection without an open caller transaction and reject it without committing/rolling it back. They do not serialize unrelated raw SDK/connection calls; the HTTP operation lock or the caller's coordination is still necessary.

This is not retrospective cleanup. Unrelated historical orphan edges are not deleted. Foreign-key enforcement is not turned on globally and no schema migration is performed. The same deletion path is tested with enforcement on and off.

## Merge

`merge_atoms(a,b)` in edge_builder only constructs merged content. It requires matching tenant, agent, partition and scope, preserves tenant/scope and keeps the existing first-parent session convention.

`VibeStorage.merge_atoms(merged, first_id, second_id)` uses BEGIN IMMEDIATE and one transaction for validation, new atom insertion, relation rewiring, and parent deletion. Both parents must exist, IDs must be distinct, merged ID must be new, ownership/partition/scope must match, and all incident edges must have valid same-owner endpoints. Failure restores the original database graph and removes the temporary merged row/index entries.

Incoming/outgoing directions are retained. Original edge ID, source, weight, decay rate, confidence, timestamps, status and version are preserved; endpoints and cross_partition reflect the replacement. Relations entirely inside the parent pair would become self-loops and are removed. Duplicate endpoint pairs with identical label/status retain the oldest created_at/id row rather than resetting decay or inventing a combined confidence. Different labels or statuses on a collapsed pair refuse the merge: the current schema cannot represent both. This is an explicit lossy deduplication policy for duplicate metadata, not preservation of every original edge row.

SDK automatic merging skips rejected incompatible/conflicting candidates and keeps both records. Successful store returns the surviving merged atom rather than the deleted incoming ID and invalidates the cold-start cache. Automatic-edge enablement and similarity thresholds are unchanged.

## Still open

### Historical administration boundary (2026-10-01 investigation)

A real temporary SQLite file containing an edge to an already-missing endpoint retained one orphan before and after SDK collect_garbage. Scoped GC joins both endpoints, so it cannot see this historical row. The new deletion transaction is preventive, not retrospective repair. Existing edges have no stale-transition timestamp; created_at/last_accessed cannot establish how long a row has been stale. GC marks status rather than physically purging rows. Neither finding is closed by this investigation.

Proposed next seam, awaiting user confirmation: a standalone administrator command, not an SDK/MCP tool. Preview opens an existing file read-only without initializing schema and reports missing-source, missing-target and both-missing edges. Existing cross-owner endpoints, self-loops and valid stale/pending history are not automatically deletion candidates. Both-missing edges have no recoverable agent ownership, so repair must be explicitly whole-file administration, not tenant-authorized SDK access. Reports should contain counts/opaque IDs, not atom content, and be treated as private.

Explicit apply must require an exclusive new backup destination, verified SQLite backup including committed WAL contents, and no deletion before backup succeeds. Select and delete only currently orphaned edges in one transaction; failed SQL must roll back, and reruns must be idempotent. No automatic startup cleanup, global foreign_keys change, atom/Episode deletion, STALE purge or VACUUM is proposed. Operators must quiesce writers and protect backup/report data. This is an acceptance design, not an implemented CLI or tested recovery promise.

STALE retention requires a separate explicit policy and reliable transition-time recording. Preserve legacy rows with unknown transition time rather than treating creation time as stale age. Retention duration, reactivation semantics and legacy migration must be decided before physical cleanup.

The merge transaction is not an atomic transaction for the entire SDK store: the incoming atom and earlier same-session edge writes may already be committed before merge is attempted. A later unexpected failure can leave that incoming atom stored. Version references and session attribution are not comprehensively rewritten. Removing an atom/edges is not proof of erasure from all derived memory or logs. Historical orphan auditing/migration requires separate backup and rollback planning, not an automatic startup deletion.

Tests use synthetic atoms and an in-memory database, including failed SQL triggers, foreign-key checks, ownership boundaries and forced SDK candidates. They validate storage lifecycle behavior, not the semantic correctness of automatic duplicate classification or independent memory quality.

## Episode invalidation and queued indexing (batch 3c)

Within the same delete/merge transaction, affected Episode rows in each parent's tenant/agent are invalidated if their member list contains a parent ID or a parent's explicit episode pointer names them. Surviving same-owner atom pointers to those Episodes are cleared. The whole derived summary is removed, not merely an ID from its list, because the text can still contain the deleted fact. Unrelated/foreign Episodes remain unchanged; malformed cross-owner legacy memberships and already-missing historical parent IDs require separate auditing. Invalid scoped JSON can fail the operation, rolling it back rather than silently discarding data.

This is conservative cache invalidation, not immediate rebuilding. Surviving members remain stored and future normal aggregation can build a new Episode. Batch 3d below bounds normal SDK rebuilds; complete source provenance remains open. The scoped JSON membership scan is linear in the owner's Episodes on each mutation; a normalized membership table/index is the upgrade path if measured costs warrant it.

## Bounded SDK Episode rebuilding (batch 3d)

The builder rejects mixed tenant/agent/session inputs and duplicate atoms. An Episode ID is a UUID5 derived from tenant, agent, session and its first member ID. It is stable for the same leading member, including appending to that topic group; changing the leading member or regrouping can change identities. This is not permanent identity across deletion/merge/topic changes.

SDK aggregation atomically replaces only the current owner's session Episode snapshot, including clearing obsolete groups and persisting member pointers. A BEGIN IMMEDIATE transaction compares the complete live atom snapshot before replacement; changed input refuses replacement without destroying old rows. SQL failure restores rows and pointers. Existing usage/community metadata survives when the stable ID matches. Original atom positions are retained to avoid reordering timestamp ties. Fewer than three session atoms retain the existing SDK aggregation threshold and clear obsolete groups.

No schema migration or startup cleanup occurs. Old random-ID Episodes are replaced only when their owning session is rebuilt; their old per-Episode statistics are not transferred to newly identified groups. Raw insert_episode remains append-only and can reject duplicate IDs. get_episodes_by_session remains a trusted, unscoped storage reader, not an authorization API. Same-connection calls still require caller coordination.

This bounds stored groups by the current topic segmentation, not runtime by a fixed limit: every SDK rebuild reads/sorts the entire session and rewrites the derived snapshot, even when unchanged. Incremental computation, complete erasure/provenance and backpressure counters are separate work. No network/model call or retrieval-default change is introduced.

Indexer consumption reloads live endpoints and enforces tenant/agent and distinct IDs before classification. It uses current content rather than queued snapshots. After classification it rechecks relevant content/version metadata. A final BEGIN IMMEDIATE compare-and-insert validates the serialized current snapshots and inserts the edge without an intervening other-connection writer. No model/network call holds that transaction. Missing, changed or foreign endpoints consume the candidate without creating an edge; merged parents are not transparently mapped to new IDs because an old relation judgment may no longer apply.

Invalid queued objects can remain in RAM until flush/clear/reset; the queue is not a secret-erasure or cross-process invalidation bus. General shared-connection concurrency still requires the existing HTTP operation lock/caller coordination. Raw insert_edge remains trusted and unchanged; the guarded insertion path is used by the indexer.

flush_all continues when a batch consumes candidates but creates zero edges and stops if the queue does not shrink, avoiding premature exit and unbounded no-progress loops. Batch limits must be positive integers. Low-similarity enqueue requests are rejected before full-queue eviction. Batch 3e below fixes return values and accounting without changing the eviction policies.

## Backpressure results and accounting (batch 3e)

Full-queue DROP_OLDEST and a successful DROP_LOWEST replacement return True and count exactly one discarded old candidate. DROP_LOWEST rejects equal/lower scores; BLOCK retains its existing non-waiting refusal behavior. Rejected full-queue offers return False and count one discarded incoming candidate. Positive integer queue capacity and known strategy names are required; zero/negative/fractional/bool capacities and unknown names raise ValueError.

enqueued_count counts new admissions, including replacements, not duplicate offers or updates. enqueue_batch counts successful offers, including duplicate successes and candidates that can be evicted by later offers in the same batch; it is not final queue growth. processed_count counts consumed candidates, even stale/failed/zero-edge work. dropped_count includes evictions, full-queue incoming refusals, compacted and cleared work, but excludes below-threshold input and duplicate updates. Therefore enqueued_count alone does not equal processed + dropped + queued when incoming full-queue offers were rejected. Counts reset with reset; no additional telemetry fields or policy changes are added.

These are sequential/caller-coordinated queue semantics, not a new thread-safe or persistent work queue. Queue bounds do not cap candidate atom snapshot size or guarantee total RAM. Classification failures remain consumed without retry, and existing downgrade diagnostics are separate work.

The real SDK forgetting trace now checks that affected Episode rows and their deleted-atom references are gone. Its observations of retained survivor context, configured seeds and reimport behavior remain: this repair is not a guarantee of complete forgetting or independent answer-quality gains.
