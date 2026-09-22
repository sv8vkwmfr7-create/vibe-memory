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

## Source-traceable, paraphrased cases

`experiments/causal_source_cases.json` freezes three separate cause → two symptoms examples, each with a separate unlinked remedy atom. The console-window, inactive-proxy-config, and stopped-poller stories are paraphrased from locally archived troubleshooting summaries; their exact page/heading mapping remains in the local Wiki, not in this public repository. This makes each proposed direction checkable against a source claim, **not** independently adjudicated causal truth. Questions, relevance/negative labels, and edge choices remain assistant-authored. No raw chat or private source text is included.

Run `python -m experiments.directional_holdout_probe experiments/causal_source_cases.json --json results/causal_source_cases_probe.json`. The report contains anonymous atom aliases only and records corpus SHA256 `88124e526f8d653884332f549b3ef9fbff324b6bf50965b87ded3a744c482fbd`. Conditions: 12 atoms, 3 reason questions, TF-IDF, precision mode, Top-5, no timing or production change.

| Strategy | Macro target Recall@5 | Questions with labeled negative hits | Ranking changes from baseline |
| --- | ---: | ---: | ---: |
| Baseline | 2/3 | 3/3 | 0/3 |
| Existing undirected bridge | 3/3 | 3/3 | 1/3 |
| Experimental directional chain | 2/3 | 3/3 | 0/3 |

All three directional diagnostics are `no_primary_outgoing_candidate`. The bridge recovers one missed cause but also returns labeled negatives on every question; these are candidate-list hits, not necessarily Top-1 mistakes. The small, assistant-curated set cannot establish quality improvement or a safe direction policy. `tests/test_causal_source_cases_probe.py` fixes the source-paraphrased graph shape and report boundary.

## Decision boundary

### Deliberately false-edge contamination

`experiments/causal_wrong_anchor_probe.py` replays the same frozen source-paraphrased 12-atom/3-query fixture, one query at a time. Each variant adds exactly two **deliberately false** cross-case `CAUSAL` edges from a cause labeled negative for that query to its two symptom atoms. The original source edges, atom texts, queries, and labels are unchanged. These false edges are adversarial test input, **not claims about the archived cases or observed production graph errors**.

Run `python -m experiments.causal_wrong_anchor_probe experiments/causal_source_cases.json --json results/causal_wrong_anchor_probe.json`. It records source SHA256 `88124e526f8d653884332f549b3ef9fbff324b6bf50965b87ded3a744c482fbd`, anonymous aliases, TF-IDF precision Top-5, and no timing. `directional_holdout_probe` now reports `negative_top1` separately from any negative appearing in the returned Top-5.

| Variant | Existing undirected bridge before → after | Experimental directional chain |
| --- | --- | --- |
| Console question, false proxy cause fork | Labeled negative Top-1: no → **yes** | No Top-1 change |
| Proxy question, false poller cause fork | No change in this case | No change |
| Poller question, false console cause fork | Target-cause Recall@5: **1 → 0** | Remains 0 |

The clean baseline already returns labeled negatives below Top-1, and the directional chain's lack of harm here is not evidence of benefit: it still cannot recover the missed poller cause in the unpoisoned fixture. This is a small, assistant-constructed sensitivity check, not an estimated real-world failure rate. The two harmed variants show why graph agreement alone is not sufficient to trust a causal anchor or make the bridge default-on.

Do not reverse existing stored edges, rename all old `CAUSAL` edges, or enable directional reranking by default based on these cases. A follow-up design must specify how cause → effect, diagnostic association, and resolution are represented and how edge provenance is verified. It then needs independent direction review and stronger incorrect-anchor guards; the paused 96-row relevance review remains unfilled and cannot substitute for causal-direction labels.
