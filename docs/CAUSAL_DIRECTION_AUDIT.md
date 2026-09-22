# Causal edge direction audit

Status: experiment evidence, 2026-09-22. No stored edges were migrated and no SDK/MCP default changed. The terms used here are defined in [CONTEXT.md](../CONTEXT.md).

## Contract and current producers

The intended meaning of `CAUSAL: A → B` is that A causes B (`vibe_memory/models/memory_atom.py`). A diagnostic pointer from a symptom to a suspected cause, a later treatment, and a chronological continuation are different relations.

| Source | Actual direction and classification | Causal direction established? |
| --- | --- | --- |
| Same-session rule (`edges/edge_builder.py`) | Earlier atom → later atom; a signal word in either atom assigns `CAUSAL`, including words such as “then” and “fix”. | No. The rule establishes order, not cause → effect. |
| Cross-session rule/indexer (`edges/edge_builder.py`, `indexer.py`) | New atom → existing atom; signal words can assign `CAUSAL`. | No. The indexer does not orient by the classified cause. |
| LLM classifier (`llm/edge_classifier.py`) | Prompt treats “follow-up” or “continuation” as causal; indexer still stores new atom → existing atom. | No reliable direction guarantee. |
| Explicit SDK edge (`sdk.py`) | Caller chooses source, target, and label. | Only if the caller supplies verified semantics. |
| Existing synthetic positive cases | Symptom anchor → cause candidate → symptom anchor. The cause text also includes a proposed action. | No. The first arrow contradicts cause → effect. |

These are code-path findings, not a count or quality estimate for existing user data. Historical `CAUSAL` labels cannot be reinterpreted or reversed safely without auditing their provenance and content.

## Controlled public replay

`tests/test_causal_direction_contract.py` uses the fixed public `safe_relation_rerank_cases.json`. For the three positive cases it preserves every query, atom text, answer label, and negative label, changing only the edges to `cause → anchor-0` and `cause → anchor-1`. The test calls the existing `safe_relation_rerank_probe.run()` report interface with TF-IDF, precision mode, and Top-5.

| Edges for three positive cases | Baseline target Recall@5 | Existing undirected bridge | Experimental directional chain |
| --- | ---: | ---: | ---: |
| Legacy symptom → cause → symptom | 0/3 | 3/3 | 3/3 |
| Cause → two symptoms | 0/3 | 3/3 | 0/3 |

The experimental rule requires `primary anchor → candidate → second anchor`; it does not promote a cause that points to both symptom anchors. A second guard changes the existing wrong-bridge example to a wrong candidate → two anchors and confirms the current directional rule does not promote that negative to Top-1. That guard does **not** prove a reversed rule would be safe: two anchors can support the same wrong cause. The examples and labels are assistant-authored synthetic diagnostics, not independent or real-session evidence. No timing is measured.

## Decision boundary

Do not reverse existing stored edges, rename all old `CAUSAL` edges, or enable directional reranking by default based on these cases. A follow-up design must specify how cause → effect, diagnostic association, and resolution are represented and how edge provenance is verified. It then needs a separate direction-labeled evaluation with incorrect-anchor guards; the paused 96-row relevance review remains unfilled and cannot substitute for causal-direction labels.
