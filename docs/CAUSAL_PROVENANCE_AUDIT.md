# Causal edge provenance audit

Status: in-memory runtime audit and targeted new-edge attribution fix, 2026-09-22. No schema migration, historical edge rewrite, SDK/MCP ranking default change, or new ranking rule. Terms are defined in [CONTEXT.md](../CONTEXT.md).

## What persisted metadata can and cannot say

An `Edge` stores `from_atom_id`, `to_atom_id`, `label`, `source`, `confidence`, and `status` (`vibe_memory/models/memory_atom.py`). SQLite persists those fields (`storage/sqlite_store.py`). There is **no persisted field for the producer path, fallback occurrence, source passage, causal-role assignment, or human-verified direction**. `source` has only `rule`, `llm`, and `learner`; it is not a causal verification state. `confidence` affects graph traversal and bridge eligibility, but is not a calibrated probability that the arrow is physically correct.

In-memory, offline probes against the public APIs produced:

| Entry point and fixed synthetic input | Persisted/resulting edge | Why this is not verified cause → effect |
| --- | --- | --- |
| `build_same_session_edges([symptom, remedy])`, with “update”/“fix” signal words | symptom → remedy, `CAUSAL`, `source=rule`, `confidence=0.9` | The arrow follows atom order. The later remedy addresses the symptom; it did not cause that earlier symptom. |
| `IncrementalIndexer.enqueue(new, old, 0.9); flush()`, two cross-session atoms with “fix” | new → old, `CAUSAL`, `source=rule`, `confidence=0.7` | The indexer fixes direction by newness, not by causal roles. |
| `VibeMemory.link(a, b, CAUSAL)` with default parameters | a → b, `source=rule`, `confidence=0.7` | This is a caller assertion, yet `source=rule` is also the default for automatically generated edges. |
| `IncrementalIndexer` with an `LLMEdgeClassifier` whose provider always raises `LLMError`, `max_retries=0` | Before fix: new → old, `CAUSAL`, `source=llm`, `confidence=0.4`; classifier `classify_fallback=1`. Standard SDK path after fix: `source=rule`. | The old value credited a failed model call. The fix records the per-decision source for new SDK-generated edges only. |

The probes use an in-memory SQLite store and synthetic text; they neither inspect user memory databases nor estimate the frequency of misoriented edges. The standard SDK now passes a source-aware classifier result to the indexer: successful model classification persists `llm`, rule fallback persists `rule`. The legacy two-value callback remains supported and cannot communicate per-decision fallback; callers using that older callback may still have ambiguous source attribution. Existing stored edges are unchanged. Even after the fix, a filter such as “trust `source=llm` and high confidence” would be unsound: model success is not direction verification, and the first row shows that even `confidence=0.9` can describe chronology or treatment rather than physical causation. See [CAUSAL_DIRECTION_AUDIT.md](CAUSAL_DIRECTION_AUDIT.md) for retrieval-level wrong-anchor sensitivity.

## Verification contract before a directional ranker

For each candidate causal edge, a reviewer needs the two claims, the claimed cause/effect roles, the original source passage or event reference, how the edge was produced (including fallback), and a direction verdict: **verified cause → effect**, **diagnostic association**, **resolution relation**, **temporal adjacency**, or **unresolved**. A reviewer must be able to mark the proposed arrow false without deleting the underlying memories. An unreviewed or missing reference remains unresolved; it must not be silently promoted to verified because of `source`, `confidence`, graph agreement, or two shared anchors.

This is a proposed evaluation/data contract, **not a field already supported by the SDK**. The existing 96-row paused relevance pack does not ask reviewers to judge arrow direction and cannot satisfy it. No independent direction verdicts were collected in this audit. Until there are independently reviewed edges and wrong-anchor negatives, directional rule design and default-on bridge activation remain deferred.
