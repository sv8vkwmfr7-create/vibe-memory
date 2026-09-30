# Privacy scanner boundaries

`MemoryDefense.scan(content)` returns `(cleaned_content, violations)`. Default `redact` rewrites detected spans. `warn` returns findings without rewriting or automatic logging; `block` lets `scan_before_store`/SDK reject detected content. Findings contain original matched text: never log or publish them as safe metadata.

## False-positive repair

Generic long keys now require an explicit `api_key`/`access_key` label and separator. Card numbers require `credit_card`, `card_number`/`card_no`, 银行卡 or 信用卡 labels with a separator. A bare hash, timestamp or long order ID no longer matches solely because of length. Chinese phone numbers cannot be embedded in a longer ASCII identifier/number; numbers next to Chinese text remain detectable. Existing known API-key prefixes, credentials, email, IP, JWT and ID patterns are retained.

This trades unlabeled generic-secret/card detection for fewer destructive false positives. Do not treat an absence of findings as proof that content is safe. A standalone 11-digit order number resembling a phone may still be a false positive. The scanner is not comprehensive DLP or a validator of real phone/card/ID ownership. Custom `patterns` can add application-specific detection; exclude_patterns remains supported.

All matches use original offsets. Redaction unions overlapping intervals and replaces each union once; adjacent intervals remain separate. The marker uses the leftmost match's type (longest first for equal starts), not a claim of one exclusive classification. The findings list retains every original match and offset. This prevents nested matches from corrupting surrounding content or exposing fragments.

## Integration limits

SDK `store` now scans content, explicit summary and both context fields before persistence, default summary truncation, embedding and automatic edge classification. SDK `update` scans supplied content/summary after ownership and allowed-field checks and before modifying the atom/version. These entrypoints share the configured scanner, retain redact/warn/block and custom/excluded-pattern behavior, and raise count-only errors without raw matched text. Invalid scanned text types fail before writing. No new return envelope is introduced.

SDK `store_batch` preflights every input message content on copies before chunking, truncating summaries or copying context. Generated atom content/summary/contexts are also checked before any row is written. In block mode any detected message rejects the entire batch, including user-only or otherwise non-ingested messages; this is an intentional conservative preflight policy. Defense rejection leaves no batch atoms/edges/Episodes or store-count increments. It is not a general atomic-batch guarantee for later database/edge/aggregation failures. Original caller messages are not rewritten.

This covers the listed SDK text paths, not every stored field or source. Explicit tags, scope metadata, session/agent/source identifiers and trusted raw storage/chunker APIs remain outside this boundary. Seed loading/bootstrap is covered by batch 3g below. Existing unchanged fields, historical Episodes/contexts/embeddings, logs/backups and old records are not scanned or migrated. Newly generated content may still exceed the heuristic detector's coverage; warn intentionally permits detected text. End-to-end user notifications and metadata/all-writer privacy policy remain open work. SDK store still returns an atom; the scanner's existing findings contain raw matches and must never be logged as safe metadata.

## Seed loading and bootstrap (batch 3g)

ColdStartManager uses the shared text preflight for seed content and explicit/default summary before caching templates or cloning them. Direct managers default to redact; SDK managers receive the configured defense instance. WARN intentionally permits matches and BLOCK rejects the entire load before any seed is persisted. Unknown partitions fail explicitly. Metadata such as tags and identifiers is not newly scanned; this does not sanitize the source JSON on disk.

The additive seed_bootstrap table records (tenant, agent, SHA256 of canonical full seed document). Seed clones and the completion marker commit in one BEGIN IMMEDIATE transaction. Other connections serialize their check/insert; a failed insertion rolls back all clones and the marker. An open caller transaction is refused without committing or rolling it back. Identical documents survive restart/reformatting without duplicate injection. Deleting a clone does not remove its completion marker, so the same configured version will not recreate it by bootstrap.

Changing any document data creates a new identity and can inject the full new seed set, not a per-item diff or replacement of old versions. The manager retains its existing once-per-instance guard: hot reload or changing defense/path after initialization is not supported by this repair. Previously bootstrapped databases have no markers; the first new bootstrap can add a set alongside historical seeds. No old seeds are deduplicated/migrated automatically. Markers hold no seed plaintext but their hashes are not secret-proof anonymization.

Batch 3h below prevents completed versions from augmenting recall via templates. Durable initialization markers are still not per-fact suppression, complete erasure or a forgotten-fact registry. Historical seed cleanup, metadata policy and all-writer enforcement remain separate work. Tests use synthetic temporary seed files/databases; no real seed corpus was loaded or migrated.

## Completed-version template suppression (batch 3h)

Before adding template atoms, augmentation checks the scoped durable bootstrap marker for its loaded document digest. A completed version never supplies fallback templates: persisted records are its only recall source, before and after forgetting. This also avoids duplicate template copies while persisted records exist. Other connections and restarted managers check the same marker instead of relying on a per-client memory flag. Failed deletes retain the persisted record and do not change the completed-version policy.

Uninitialized versions retain existing template augmentation. Different tenants/agents and changed documents have separate markers; a new document version can again expose or inject a fact, even if an older version was forgotten. Legacy seeds without markers, trusted raw writers, unchanged caller-held templates, cached object contents, historical context/version/provenance, logs/backups and physical database bytes are not erased. load_seed_memory/get_seed_atoms still expose loaded templates to trusted callers; this gate applies to augmentation/SDK recall/injection, not a secure RAM wipe.

This intentionally changes fallback behavior for the entire completed seed set, not fuzzy per-fact suppression. No new schema, forget flag or tombstone registry is added. An indexed marker lookup occurs during fallback checks; concurrent SDK recall/forget on a shared connection still needs existing coordination, and this is not general cross-process recall/delete linearizability. Main retrieval mode/threshold defaults remain unchanged. No real seed file or user database was cleaned or migrated.

Previously damaged stored content is not restored automatically. No real database migration or secret corpus evaluation was performed. Tests use synthetic strings, TF-IDF and an in-memory database; they establish the tested false-positive/overlap behavior, not independent retrieval-quality gains or complete privacy coverage.
