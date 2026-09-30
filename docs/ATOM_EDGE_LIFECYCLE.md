# Atom deletion and merge boundaries

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

The merge transaction is not an atomic transaction for the entire SDK store: the incoming atom and earlier same-session edge writes may already be committed before merge is attempted. A later unexpected failure can leave that incoming atom stored. Version references and session attribution are not comprehensively rewritten. Removing an atom/edges is not proof of erasure from all derived memory or logs. Historical orphan auditing/migration requires separate backup and rollback planning, not an automatic startup deletion.

Tests use synthetic atoms and an in-memory database, including failed SQL triggers, foreign-key checks, ownership boundaries and forced SDK candidates. They validate storage lifecycle behavior, not the semantic correctness of automatic duplicate classification or independent memory quality.

## Episode invalidation and queued indexing (batch 3c)

Within the same delete/merge transaction, affected Episode rows in each parent's tenant/agent are invalidated if their member list contains a parent ID or a parent's explicit episode pointer names them. Surviving same-owner atom pointers to those Episodes are cleared. The whole derived summary is removed, not merely an ID from its list, because the text can still contain the deleted fact. Unrelated/foreign Episodes remain unchanged; malformed cross-owner legacy memberships and already-missing historical parent IDs require separate auditing. Invalid scoped JSON can fail the operation, rolling it back rather than silently discarding data.

This is conservative cache invalidation, not immediate rebuilding. Surviving members remain stored and future normal aggregation can build a new Episode. Stable Episode identity, bounded repeated aggregation and complete source provenance are still open. The scoped JSON membership scan is linear in the owner's Episodes on each mutation; a normalized membership table/index is the upgrade path if measured costs warrant it.

Indexer consumption reloads live endpoints and enforces tenant/agent and distinct IDs before classification. It uses current content rather than queued snapshots. After classification it rechecks relevant content/version metadata. A final BEGIN IMMEDIATE compare-and-insert validates the serialized current snapshots and inserts the edge without an intervening other-connection writer. No model/network call holds that transaction. Missing, changed or foreign endpoints consume the candidate without creating an edge; merged parents are not transparently mapped to new IDs because an old relation judgment may no longer apply.

Invalid queued objects can remain in RAM until flush/clear/reset; the queue is not a secret-erasure or cross-process invalidation bus. General shared-connection concurrency still requires the existing HTTP operation lock/caller coordination. Raw insert_edge remains trusted and unchanged; the guarded insertion path is used by the indexer.

flush_all continues when a batch consumes candidates but creates zero edges and stops if the queue does not shrink, avoiding premature exit and unbounded no-progress loops. Batch limits must be positive integers. Low-similarity enqueue requests are rejected before full-queue eviction. Existing backpressure policies, accepted full-queue return values and accounting quirks are not otherwise redesigned.

The real SDK forgetting trace now checks that affected Episode rows and their deleted-atom references are gone. Its observations of retained survivor context, configured seeds and reimport behavior remain: this repair is not a guarantee of complete forgetting or independent answer-quality gains.
