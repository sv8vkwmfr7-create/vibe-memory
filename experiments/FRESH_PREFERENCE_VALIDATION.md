# Fresh preference validation preparation — 2026-09-28

Latest follow-up, 2026-09-29: [explicit forget-action validation](FORGET_ACTION_VALIDATION.md) ran twice on disposable synthetic data with matching reports. Original deletion holds across recall/restart; a manually planted copy remains and deliberate raw-storage reimport restores the original. Full regression 443 passed in 157.97s. This is not complete forgetting, independent relevance evidence or a production fix; no actual PersonaMem/user data was deleted.

## Current outcome: preceding-turn candidate not promoted

The frozen context-only MiniLM representation has now executed; see [protocol/results](PERSONAMEM_FACT_ALIGNMENT.md), [untimed report](../results/personamem_previous_context_probe.json) and [bounded timing](../results/personamem_previous_context_timed.json). All 3 baseline cases replay exactly; timed/untimed results match after removing timing. Own-preference 782 stays absent, other-person 988 stays absent, while the forget span goes 2/4→4/4 **with the old fact still first**. This is not a memory-quality improvement or forgetting implementation. No production promotion or follow-up window sweep.

Character input approximately doubles; encoding totals **4.63→6.93s**, warm-query median **13.23→13.48ms** across 15 observations/arm. Matrices remain 1,018,368 bytes/arm, not peak RAM. Characters count pre-tokenization strings; unchanged model max length 256 may truncate prior context. Bounded experimental timing is not full onboarding, an SLA, electricity or currency cost. Full regression **442 passed in 87.22s**, targeted **6 passed in 0.14s**. Existing construction/helpers reused, no dependencies/downloads/paid API/answers. Next: explicit forget-action loop in isolated synthetic data; independent relevance, natural-language target resolution, complete deletion/reimport prevention and official history integrity remain unfinished.

## Current interpretation: factual alignment supersedes positive-span assumptions

See [fact audit and frozen next experiment](PERSONAMEM_FACT_ALIGNMENT.md). Publisher metadata and original dialogues show first-three tasks are **others / implicit self preference / ask-to-forget**, not three positive user-preference targets. In the forget case MiniLM returns old fact 108 first and instruction 109 fifth. Earlier snippet-hit arithmetic stays unchanged but is not a success score; 988/782 are both span misses, not both lost user preferences. The direct-SQLite adapter did not execute the natural-language forget action or explicit-ID SDK deletion; this is not a demonstrated deletion-API bug. No independent human or final-answer judgment is claimed.

At the factual-audit stage only documentation changed, with **5 targeted checks passed in 0.13s** and the prior full **441 passed in 78.41s**. Its frozen candidate was then not executed; the actual execution and non-promotion result are now reported above. Preceding-turn context changes only MiniLM embedding texts, with original stored/returned turns and lexical/depth/fusion budgets fixed. This is exploratory exposed data, not independent validation, a forgetting fix or production promotion.

## Completed: full-corpus route positions, no ranking intervention

`--full-ranks` requires the original `--stage-reference` and reuses TF-IDF search, MiniLM `index_flat` and BM25 on the original **224/220/219** dialogue corpora. The returned core Top-5 is unchanged; only additional observations are saved to `results/personamem_full_rank_diagnostics.json`. All **3/3** original rows and previous stage traces replay exactly. Each full ranking's first five IDs must equal its actual captured route Top-5, otherwise the run fails. Only target ranks/scores, ranked counts and prefixes are recorded, not raw text or full unrelated ID lists. Full regression **441 passed in 78.41s**; targeted checks **5 passed in 0.13s**; the new small test first failed on the absent helper, then passed, and distinguishes positive scores, zero-score padding and unscored missing evidence.

| Persona | Nearest TF-IDF related-turn rank | Nearest MiniLM related-turn rank | Nearest BM25 related-turn rank |
| --- | --- | --- | --- |
| 988 | 53 | 38 | 93 |
| 782 | 75 | 22 | 65 |
| 730 (partial-hit control) | 1 | 1 | 1 |

All published related turns have positive scores in all three observed routes. BM25 returns 217/190/209 scored dialogue turns, while both semantic rankings cover all 224/220/219; a BM25 turn absent from its list must not be assigned a fabricated zero-score rank. MiniLM per-related-turn positions are 988:45/46/47/48 → **150/144/46/38**, 782:113/114 → **22/40**, and 730:107/108/109/110 → **9/1/5/6**. Full details and numeric scores are in the report.

This rejects the narrow explanation “no lexical match at all” for these particular related spans. It also shows that an observed semantic/BM25 cutoff of 10 or 20 would still miss both zero-hit spans. It does not prove a representation bug, truthful preference recovery, graph/temporal intervention outcome, or that deeper candidates survive fusion and final selection. No cutoff sweep, new returned ranking, new answers or quality fix was performed. Nearest-span rank is not a recommended cutoff. Full semantic rankings reuse the already encoded corpus; graph expansion, larger fusion pools and any reranker can have different costs and need explicit profiling. This run has **no timing, memory, electricity or user-cost measurement**.

```powershell
.\.venv\Scripts\python.exe -m experiments.personamem_adapter_smoke C:/Users/ASYS/.cache/vibe-memory-eval/personamem-v2-ed956dea --model-dir C:/Users/ASYS/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41 --stage-reference results/personamem_adapter_smoke.json --full-ranks --json results/personamem_full_rank_diagnostics.json
```

Next: inspect the query-to-related-span factual alignment and turn granularity before freezing one representation or candidate-depth intervention. Any rule chosen after inspecting these labels is exploratory; independent validation must use untouched cases under the same final Top-5 budget, disclose harmful/preference failures, and measure setup/query/memory costs. Official history integrity, all-row mapping and private human review remain unfinished. Existing helpers and cached model were reused under the minimal-change skill; no dependency, download, paid API, production change or fabricated human label was added. Diagnosis-only stages continue; minimising the corpus and applying a fix remain deferred because this task observes unchanged ranking competition.

## Completed: unchanged miss-stage diagnosis

The adapter's optional `--stage-reference` captures existing retrieval stages and requires exact equality with the original smoke report after removing only the added traces. `results/personamem_stage_diagnostics.json` records reference SHA-256, **3/3 replay matches**, four route lists, fused/final lists, each related turn's ranks, fused-first-five coverage, and the frozen re-fusion inputs. No raw query/history text is copied into the report. Existing `STAGES`, `loss_stage`, `_rank` and `_recall_with_stages` are reused; no production code or dependency is changed. Full regression **440 passed in 75.20s**; targeted checks **4 passed in 0.13s**. Passing software checks are not a retrieval-quality fix.

| Persona | TF-IDF / MiniLM zero-hit location | Frozen re-fusion evidence input |
| --- | --- | --- |
| 988 | All four related turns absent from every route Top-5, before fusion | None |
| 782 | Both related turns absent from every route Top-5, before fusion | None |
| 730 (partial-hit control) | Turns 108/109 retained; 107 absent before fusion; 110 BM25 rank 4, fused rank 6, absent from final five | 108/109 in both lists; 110 only in BM25 |

For 988/782, **weight changes over the same input lists cannot retrieve a turn outside their union**. This is a ranking-set constraint, not proof of a specific underlying representation failure. The deeper reason (query/turn mismatch, granularity, candidate depth, model representation or related-span annotation) remains undetermined. For 730:110, presence in fused Top-10 but absence from final Top-5 does not prove demotion from fused Top-5 or that disabling reranking improves overall quality.

Diagnostic loop: actual unchanged model execution reproduced all three original results exactly; a desired-hit assertion for the first two rows failed with `Reproduced: personas 988 and 782 have no related-snippet turn in MiniLM final Top-5`. Stage classification then distinguishes before-fusion, fusion cutoff and final selection; a small unit test covers these distinctions, temporal-route evidence and fused-rank-6 versus fused-first-five. The new test first failed on the absent helper and passed after implementation; that red/green verifies diagnostic logic, **not a retrieval fix**. Full histories were intentionally retained, since minimising distractors changes ranking competition. This is diagnosis-only: fix/intervention phases are deferred, the original quality failure remains reproducible, and no default is eligible.

```powershell
.\.venv\Scripts\python.exe -m experiments.personamem_adapter_smoke C:/Users/ASYS/.cache/vibe-memory-eval/personamem-v2-ed956dea --model-dir C:/Users/ASYS/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41 --stage-reference results/personamem_adapter_smoke.json --json results/personamem_stage_diagnostics.json
```

Full-corpus semantic/BM25 ranks have now been observed above without altering returned Top-5. These exposed three rows cannot establish generalisation or answer accuracy. Official per-history integrity, all-row mapping, meaningful preference/contradiction checks, independent validation and explicit setup/query/memory/cost measurements remain unfinished. No download, paid API, final-answer generation, human labels or user-cost claim was added in this diagnosis.

## Completed: pinned real-data adapter smoke

`personamem_adapter_smoke.py` ran the fixed first three text-validation rows using TF-IDF, cached CPU MiniLM and the previously frozen equal-weight RRF (k=60, mixed MiniLM final Top-5 + positive BM25 Top-5, final five). The MiniLM list is not a pure semantic route. No parameters or production code changed; existing mapper/scorer/ranking helpers were reused, with no dependency added. Full software regression: **439 passed in 79.35s**.

Dataset: [PersonaMem-v2](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2), CC-BY-4.0, publisher LLM-generated data. Revision [ed956dea41521fc4499acbc63f966e0fd3c053ba](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/commit/ed956dea41521fc4499acbc63f966e0fd3c053ba) was verified against the official commit page. Mirror files were obtained with certificate verification enabled. The downloaded `benchmark/text/val.csv` has **2,061 rows / 27 columns**, 17,474,290 bytes; SHA-256 `a47a7dd3879de5e282c6d15266437ed44cf69c0c93c79634645dbd73d655b29a` matches the [official file page](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/blob/main/benchmark/text/val.csv). The card's 2,600 validation-row description is not the actual count in this pinned file.

CSV and three required histories total **17,991,954 bytes**, stored outside Git at `C:/Users/ASYS/.cache/vibe-memory-eval/personamem-v2-ed956dea`. Individual history SHA-256 values are saved in `results/personamem_adapter_smoke.json` and enforced by the runner, but **have not been independently checked against official per-file hashes**. Local hashing, metadata agreement and exact related-snippet matching do not establish whole-history mirror equivalence.

| CSV row / persona | Original snippet indices | Stored dialogues | TF-IDF / MiniLM / fusion snippet-turn recall |
| --- | --- | --- | --- |
| 0 / 988 | 45, 46, 47, 48 | 224 | 0 / 0 / 0 |
| 1 / 782 | 113, 114 | 220 | 0 / 0 / 0 |
| 2 / 730 | 107, 108, 109, 110 | 219 | 0.5 / 0.5 / 0.5 |

Mapping coverage is **3/3**, no exclusions or replacement rows. All three system persona profiles were excluded; **663** user/assistant dialogues were stored. Every arm has snippet-any-hit **1/3** and whole-snippet coverage **0/3**. This smoke shows no fusion improvement; it is not a definitive quality comparison or official answer score. Related spans include generic openings and are not minimal preference-fact gold labels.

Queries are parsed with `ast.literal_eval`, not `eval`; query options, correct answers, preference metadata and reference snippets are never added as memories. Original message indices are preserved. Each case uses an isolated direct-SQLite store, synthetic microsecond ordering, no causal edges and unchanged warm core `precision` Top-5. This is not SDK/MCP end-to-end. No final answers, paid API, human review, model download or user-cost measurement occurred. These three rows are now exposed and must not be called untouched after future tuning; private 96-row review remains paused and candidate defaults remain ineligible.

Reproduce:

```powershell
.\.venv\Scripts\python.exe -m experiments.personamem_adapter_smoke C:/Users/ASYS/.cache/vibe-memory-eval/personamem-v2-ed956dea --model-dir C:/Users/ASYS/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41 --json results/personamem_adapter_smoke.json
```

The no-tuning stage diagnosis is now completed above. Full official history integrity and all-row unique-mapping coverage remain prerequisites for a predeclared definitive comparison; user-cost measurement and independent validation remain separate promotion gates. The preparation failures below describe the earlier state, not current data unavailability.

## Completed: frozen local preference counterexamples

Final software regression: 438 passed in 76.43s; targeted scoring/mapping checks: 2 passed in 0.12s. Quality failures below remain; this does not make the external evaluation complete.

`preference_rank_negative_cases.json` freezes four assistant-authored cases before first execution: paraphrased concise-writing preference, changed interface theme, decaffeinated-drink preference versus generic/other-person advice, and negated spicy-food preference. SHA-256: `c316df401802d53f24df86f05b2a3bff76751c6a400ea07703a58fc6d90e3b05`. These are diagnostics, **not independent labels or an external benchmark**. Other-person remarks are distractors in the same stored scope, not multi-tenant tests.

`preference_rank_negative_probe.py` actually encodes these documents using cached CPU MiniLM weights SHA-256 `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db`. It reuses unchanged precision recall, stage capture and the frozen final-rank RRF (equal weights, k=60, both lists Top-5, final five). Answers and labels are scorer-only; no old/current routing is added.

`results/preference_rank_negative_probe.json`: original MiniLM and candidate each retrieve target **2/4**, put target first **0/4**, and put known negative first **2/4**. Writing and mild-food targets remain absent. For the theme case re-fusion elevates the obsolete dark preference to first; in the drink case generic coffee advice stays first while the preferred tea is returned lower. Membership/order really changes, so this is not a vacuous unchanged-negative check. Finding correct preference alongside contradiction does not prove safe personalized answering. The candidate is not eligible for defaults.

No new downloads, model installation, paid API calls or final answers. This is actual core-model execution, not SDK/MCP end-to-end. Onboarding latency, working set and electricity are unmeasured; do not turn process duration into user cost. Production code stays unchanged and the 96-row human review stays paused.

Reproduce with the project interpreter and pinned cache path:

```powershell
.\.venv\Scripts\python.exe -m experiments.preference_rank_negative_probe --model-dir C:/Users/ASYS/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41 --json results/preference_rank_negative_probe.json
```

## One-source research: choice of new data

- PersonaMem-v1's published schema has multiple-choice answers, context cutoff and reference-distance metadata, but not direct gold turn IDs or a gold snippet field. It cannot directly supply our turn-evidence score. This is a schema-based inference, not a claim that no alternative annotations exist anywhere. [Publisher repository](https://github.com/bowen-upenn/PersonaMem#file-format).
- PersonaMem-v2 publishes text history links and `related_conversation_snippet`, with preference ownership/update metadata. Its card says the data are LLM-generated and not all manually verified; license is **CC-BY-4.0**. Use the wording “project-unused publisher-generated external data”, not “independent human evaluation”. [Publisher card](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/blob/main/README.md), [actual viewer/schema](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2).
- The official distance routine matches only the first snippet content by substring and takes the first occurrence. Distance 0 can also mean failed mapping; it is not a reliable absolute evidence index. This conclusion follows code inspection. [Publisher preparation code](https://raw.githubusercontent.com/bowen-upenn/PersonaMem-v2/main/data_generation/prepare_benchmark.py).
- The history builder prepends a system persona profile. Exclude system profiles from retrievable dialogue, while preserving original indices. [Publisher context builder](https://raw.githubusercontent.com/bowen-upenn/PersonaMem-v2/main/data_generation/contexts_builder.py).

## Historical preparation: evidence-mapping gate, before real-data smoke

`personamem_evidence.evidence_indices` requires one exact full contiguous role/content match. Empty, absent, duplicated, partial substring, wrong-role, multimodal and system-profile snippets fail. It returns original absolute indices, not indices from a filtered dialogue. Unit checks use synthetic messages only; they are not a smoke on downloaded PersonaMem data.

The Windows PowerShell and project stdlib HTTPS requests to the official dataset-server endpoint both failed with transport/TLS unexpected EOF. A requests-based diagnostic was unavailable because that optional package is not installed; no package was installed. The web reader could verify publisher documentation, but the split API was unavailable there too. No real benchmark/history files were downloaded, no content hashes/revision were pinned, and **no PersonaMem score exists**. Do not bypass TLS verification, change the user's network configuration, or mistake accessible documentation for runnable local data.

## Frozen next-step boundary

1. Obtain a verified publisher revision and matching text benchmark/history files outside Git. Download only required linked histories; never guess a filename from persona ID or ingest the entire multi-GB repository. Save license/attribution, exact revision, bytes and SHA-256; verify any mirror against publisher metadata before treating it as equivalent.
2. Perform fixed first-N **adapter smoke**, explicitly separate from benchmark scoring. Validate text-only schema, full unique snippet mapping, role/content, and query placement after history; exclude system persona and never ingest query options, correct answers, preferences or reference snippets as additional memory. Do not silently repair missing/ambiguous mappings. Report candidate count, each exclusion reason and mapping coverage.
3. Publisher snippets are related conversation spans, not minimal fact-bearing turn labels. Report whole-snippet coverage and clearly labeled snippet-hit/turn-recall diagnostics; do not call a match on a generic opening factual preference retrieval or official PersonaMem answer accuracy.
4. Freeze definitive selection before inspecting retrieval results: all eligible rows of a pinned text benchmark split, same 32k history path per row, all failures/exclusions disclosed, three paired arms (TF-IDF, unchanged MiniLM, frozen rank fusion) and equal final Top-5 budget. PersonaMem remains external publisher-synthetic evidence; foundation-model overlap and label quality are unknown. No parameter tuning on benchmark labels.
5. Measure setup/encoding and warm query costs with explicit timing mode, separately from model/download cost. Complete preference/contradiction negative checks and independent/human validation before promoting a default. Final-answer evaluation needs a separate protocol; do not mix multiple-choice scores with retrieval metrics.

At preparation time the blockers were real data availability and a verified complete mapping. The first-three smoke has now removed the small-subset availability blocker; official history integrity, full mapping coverage, meaningful preference-quality evidence and measured user cost remain unfinished. There is no need to fabricate human labels or keep tuning LongMemEval.
