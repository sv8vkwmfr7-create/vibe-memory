# PersonaMem first-three factual alignment and next experiment — 2026-09-28

Follow-up 2026-09-29: the explicit-ID forgetting experiment has now run on isolated synthetic data; see [action validation](FORGET_ACTION_VALIDATION.md). Original deletion works through next/reopened recall, while a manually copied fact, incident edge row and deliberate storage reimport expose incomplete fact-level forgetting. No PersonaMem content was deleted and no production fix is claimed. The earlier next-step descriptions below are historical planning, superseded by that action result.

## Executed result: no promotion

The frozen preceding-turn representation actually ran. `personamem_adapter_smoke.py --previous-context` changes only MiniLM document-vector inputs using the existing `write_texts` helper; stored content/summary, BM25, route depth and returned original Top-5 stay fixed. Original baseline replays **3/3**; candidate BM25 lists are asserted unchanged, original stored content is rechecked, and timed query repeats must reproduce each arm's first ranking. The boundary test covers first-turn/session isolation and non-mutation. Full regression **442 passed in 87.22s**, targeted **6 passed in 0.14s**.

| Task | Baseline → preceding-context result | Decision |
| --- | --- | --- |
| 988, other person | Related-turn coverage 0/4 → 0/4 | No ownership-quality judgment inferred |
| 782, implicit own preference | Related-turn coverage 0/2 → 0/2 | No recall improvement demonstrated |
| 730, ask to forget | Coverage 2/4 → 4/4; old fact stays rank 1; instruction rank 5 → 2; confirmation absent → rank 4 | More related context is not forgetting success; no promotion |

All three final candidate rankings change, so the result is not a vacuous unchanged intervention. No answer generation or natural-language forget/explicit-ID deletion occurs. Do not infer final-answer misuse or universal failure of context-aware memory. The [untimed report](../results/personamem_previous_context_probe.json) equals the [timed report](../results/personamem_previous_context_timed.json) after removing only per-row timing. Untimed default has no timing fields. No new dependency, model download, paid API, production change or human labels.

Local timing on the three original corpora: supplied character count **463,961 → 933,330**, total corpus encoding **4,631.48 → 6,927.75ms** (about **50% more**), warm-query median across **15 observations/arm** (five per case, alternating order) **13.23 → 13.48ms**. Each arm's matrices total **1,018,368 bytes**, not process peak RAM. Encoding order alternates by case; the model is loaded before timers. Measurements exclude context-string construction, model load/download, SQLite writes and BM25 setup; query timers include experimental stage capture. Local background load is uncontrolled; do not infer a reproducible speed advantage, a p95 SLA, total onboarding or electricity/currency cost.

`encoded_characters` is a count of **supplied strings before tokenizer truncation**, not actual encoded tokens. The pinned cache's `sentence_bert_config.json` has `max_seq_length=256`; appended preceding context may therefore be truncated. Context coverage inside tokenized input was not audited, so this failure applies to the frozen append-only representation, not to every possible context scheme. No truncation-policy or window sweep follows this run.

Reproduce the untimed run (add `--include-timing` and use a separate output for costs):

```powershell
.\.venv\Scripts\python.exe -m experiments.personamem_adapter_smoke C:/Users/ASYS/.cache/vibe-memory-eval/personamem-v2-ed956dea --model-dir C:/Users/ASYS/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41 --stage-reference results/personamem_adapter_smoke.json --previous-context --json results/personamem_previous_context_probe.json
```

Next is a report-only explicit forgetting-action loop on an isolated synthetic fixture with known target IDs: observe before/after recall and possible derivative/reimport risks without adding production interfaces or deleting real user data. Merely retrieving a forget command is not executing it. Natural-language target resolution and verified complete forgetting remain separate; independent human validation and official data integrity remain unfinished. The protocol below is preserved as the pre-execution decision, not a current claim of pending execution.

## Verified scope

This is an assistant code/data audit of the already exposed first three rows, **not independent human labels** or an answer benchmark. The pinned CSV SHA-256, locally pinned history hashes, exact unique snippet mapping and `who`/`pref_type`/`updated` fields were rechecked locally. The full-rank report SHA-256 is `25eb0dfae3947d751a06e6c3166927997810569b5e769dc5476e709c8c0d6a74`. Official per-history integrity remains incomplete. No raw history, persona profile, answer or sensitive preference text is copied into this document.

Historical factual-audit turn: only documentation changed, existing targeted checks were **5 passed in 0.13s**, and the preceding full regression was **441 passed in 78.41s**. No model inference, download, paid API, final answer, production change or performance measurement occurred in that audit. The later candidate execution and current verification are reported above.

## Findings that change interpretation

| Persona / row | Verified publisher fields | Underlying evidence and observed Top-1 | Correct interpretation |
| --- | --- | --- | --- |
| 988 / 0 | `who=others`, `pref_type=anti_stereotypical_pref`, `updated=False` | Related span 45–48 is a prose-editing exchange about a named third person; audio/science context is indirect. MiniLM first result 121 concerns recommendations in another medium. | Not a positive first-person preference-recall case. Missing this span does not establish a lost user preference; retrieving it would not prove safe ownership attribution. |
| 782 / 1 | `who=self`, `pref_type=stereotypical_pref`, `updated=False` | Related span 113–114 is a writing/refinement task containing a clothing-accessory detail; query requests elegant outfit suggestions. MiniLM first result 53 concerns a different recommendation topic. | Relevant positive preference diagnostic, but preference is embedded in narrative, not stated as a standalone preference. Similar generic recommendation phrasing competes with the implicit fact. Representation/granularity hypothesis is plausible, not yet causal proof. |
| 730 / 2 | `who=self`, `pref_type=ask_to_forget`, `updated=True` | 108 contains the prior fact, 109 explicitly asks to forget it, 110 confirms. Unchanged MiniLM returns 108 first and 109 fifth. | The earlier snippet hit is not a personalization success. Returning the standalone old fact is a risk signal alongside a forget instruction, not proof of final-answer misuse. Command and confirmation retrieval must be separated from retrieval of the superseded fact. |

The publisher's related spans serve multiple task types, not one positive-gold turn-recall target. Historical **1/3 snippet-any-hit** and **0/3 full-span coverage** remain valid descriptive calculations, but **must not be aggregated or optimized as memory-quality success** across these rows. Rows 988/782 are both span misses; only 782 is the first-person positive case. Likewise the all-positive similarity scores do not mean that every related turn is a usable current preference.

The current adapter inserts every non-system dialogue turn directly into SQLite. It does not interpret `who`, update metadata or natural-language forget requests, and does not call `VibeMemory.forget`. The implemented SDK method deletes an explicitly identified atom and invalidates its cache; the audit did not exercise it. Therefore this finding concerns **an unimplemented ingestion/action step in this adapter**, not evidence that the explicit-ID deletion API is broken. Even an implemented deletion must cover derivative summaries/caches/graphs and prevent reimport; none of those guarantees are proved here.

## Frozen single-variable exploratory experiment

Question: Does preceding-turn context in the embedding representation make an implicit own-preference fact more retrievable, without hiding ownership/forget risks?

1. Reuse the cached CPU MiniLM, fixed first-three rows, original IDs, same full histories and original direct-SQLite store. Baseline replay must match the pinned smoke report. Retain the other-person and forget rows as risk diagnostics; do not discard them to improve a score.
2. Candidate change **only**: each original atom's embedding input is its role-prefixed current dialogue plus the immediately preceding non-system dialogue, explicitly labelled as previous context. First dialogue gets no predecessor; never include a system persona, benchmark query, reference snippet, answers or preference metadata. Do not infer conversation-pair/session boundaries that the adapter does not have. This preceding-turn rule is uniform, not targeted at evidence indices.
3. Reuse the previous-context construction pattern in `locomo_adjacent_context_probe.write_texts`, adapted to experiment-side embedding texts rather than MCP writes. Do not rerun the unrelated MCP experiment. Keep stored text/summary, BM25 index, route depth, graph/temporal behavior, fusion weights, model and query fixed. Both arms return at most **five original turns**, with no neighbour text expansion in returned context. Ranking, including similarity reranking, uses the paired representation; that is one representation intervention, not a claim that only the first stage changes.
4. Report all returned IDs and per-span positions. For 782, label span-hit/turn recall as an implicit-own-preference proxy, **not answer accuracy**. For 988, report third-person related-span presence without calling it user preference success or automatic harm. For 730, separately disclose standalone old-fact turn 108, instruction 109 and confirmation 110; retrieval of the command is not the same as reusing the deleted preference. These interpretations are assistant-audited and not independent labels.
5. Explicit timing mode: measure baseline/candidate corpus-encoding time, encoded character counts and vector bytes; alternate query-arm order and record repeated warm-query timing. No timing fields in the deterministic default report. Do not use one three-case p95 as a user SLA, equate vector bytes with process peak RAM, or claim electricity/currency cost without measurement. Cached model load/download cost and SDK/MCP onboarding are separate. API cost should stay zero.
6. Freeze this protocol before candidate execution. No window-length, weight or candidate-depth sweep; no generated preference summaries or model installation. This is label-informed **exploration on exposed data**, not a fresh validation. No production promotion on these three rows, even if 782 improves. Independent validation, ownership attribution, actionable forgetting, meaningful negative cases, full data integrity/mapping and user-cost gates remain prerequisites.

A failure to improve is useful evidence against this particular two-turn representation, not against all context-aware memory. Previous LoCoMo adjacent-context results used different data, representation and entry points and do not determine this outcome. At protocol freeze the actual candidate run was **not started**; it is now executed with the non-promotion outcome above.
