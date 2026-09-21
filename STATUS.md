# Project Status

> Last verified: 2026-09-21

Vibe Memory 0.3.0 is a beta-stage local-first agent memory library. The core SDK, SQLite storage, TF-IDF retrieval, CLI/session manager, and MCP stdio interface are covered by the current local test suite. Public benchmark and production-scale claims remain unverified.

### Causal position and intent diagnostic (2026-09-21)

`python -m experiments.causal_intent_probe /path/to/private-corpus.json /path/to/private-annotations.json --rankings results/directional_holdout_probe.json --json results/causal_intent_probe.json` reports graph positions and intent-specific answer recall without exporting private text or original atom IDs. On the frozen twelve-memory/eight-query holdout, assistant-labeled reason questions are **3/8**, each targeting a middle node; solution questions are **5/8**, each targeting a terminal node. Baseline, current bridge, and experimental directional chain each retrieve the annotated answer in **all 8/8** queries at Top-5. The intent/answer subset is a new assistant hypothesis, not independent ground truth. No automatic intent routing or production default changed. Full regression: **382 passed in 16.59s**.

The diagnostic now rejects a rankings report whose `corpus_sha256` differs from the input corpus bytes. Because anonymous `atom-i` aliases depend on atom order, reusing rankings with reordered atoms previously produced plausible but invalid metrics. The matching frozen corpus/report still runs; isolated optional-semantic-dependency regression: **385 passed in 15.58s**. This is an experiment integrity fix, not a retrieval quality improvement.

The stricter Top-1 check exposes a ranking gap: **2/3** reason questions and **2/5** solution questions place the annotated answer first, identically across all three strategies. An oracle supplied with the assistant intent label can stably prioritize middle/terminal nodes and reaches **8/8** on this holdout, but a public cross-issue counterexample promotes a labeled wrong terminal to Top-1. Position alone is therefore unsafe as a production reranker; the oracle is a diagnostic upper bound, not a deployable solution. Full regression: **383 passed in 15.75s**.

An experiment-only session proxy now restricts position promotion to the first baseline result's `session_id`. It restores **8/8** annotated Top-1 on the holdout and avoids the cross-session wrong-terminal guard, but a second public guard with a wrong first-session anchor still promotes a labeled negative. `session_id` is not an issue-family label, and both intent and holdout labels are assistant-authored. No production routing or default changed; **384 passed in 15.47s**.

### Directional rerank private holdout replay (2026-09-19)

`python -m experiments.directional_holdout_probe /path/to/private-corpus.json --json results/directional_holdout_probe.json` replays the frozen twelve-memory, eight-query Wiki-source holdout through baseline precision, the existing causal bridge, and the experiment-only directional chain. All three produced identical rankings on all eight queries: macro Recall@5 **1.00**, labeled precision@5 **0.40**, and labeled negative hits on **5/8** queries. The report contains only anonymous IDs and aggregate metrics; private text remains local.

Coverage diagnostics explain the zero ranking changes: every query had **3–5** common semantic/BM25 anchors, but all **8/8** primary semantic anchors had zero outgoing causal edges to a non-anchor candidate (`no_primary_outgoing_candidate`). The blocker is therefore relation orientation at the primary anchor, not too few common anchors or loss after fusion. This does not justify reversing the rule: the current holdout already retrieves every labeled answer and still lacks independent labels.

This result shows no regression and no benefit on the holdout. It does not validate a product integration: the labels and edges are assistant-authored, timing is intentionally excluded from the deterministic report, and the paused 96-row human review remains untouched. Production defaults remain unchanged. Two report-interface tests bring the full suite to **380 passed in 16.67s**.

### Directional causal-chain rerank probe (2026-09-19)

`python -m experiments.safe_relation_rerank_probe --json results/safe_relation_rerank_probe.json` compares the existing undirected causal bridge with an experiment-only rule requiring `primary anchor -> candidate -> second anchor`. Both recover all three fixed half-hit targets, while the directional rule avoids the current bridge's two negative Top-1 promotions in convergence and reversed-direction guards; a graph-free guard preserves baseline order. The dataset SHA256 is `ce51f0ad0aabfa866d3fa7d744c7a949b4dd1d65940cd106b153c0aafe04ea3c`.

These are assistant-authored deterministic synthetic cases, not independent labels or a public benchmark. The synthetic guards pass, but the rule is not eligible for a default change and remains outside SDK/MCP production code. Three new tests bring the full suite to **378 passed in 15.18s**.

Direction here means the direction of the supplied graph edge, not proven physical causality. The positive synthetic cases encode `symptom anchor -> cause candidate -> symptom anchor`, whereas the model/README define a causal `A -> B` as “A causes B”; same-session rule edges also follow chronology when a broad signal word appears. Resolve this edge contract and validate correctly oriented examples before interpreting the synthetic success as causal reasoning.

### Precision stage diagnostics (2026-09-19)

`python experiments/precision_stage_diagnostics.py --json results/precision_stage_diagnostics.json` runs five fixed assistant-authored synthetic cases through the production precision path while observing semantic, BM25, graph, RRF fusion, and final rerank stages. In all three causal half-hit cases the target is absent from semantic/BM25, ranks first in graph, ranks fifth after RRF, and is removed by the final similarity rerank. Explicit `causal_bridge` restores all three targets, but a jointly-wrong-anchor guard promotes a labeled negative to Top-1; a graph-free guard preserves baseline order. Therefore the bridge remains opt-in and production defaults are unchanged. The cases are development diagnostics, not independent labels or a public benchmark. Three new tests bring the full suite to 375 passed.

### Fixed 50/50 TF-IDF + BGE probe (2026-09-15)

`experiments/hybrid_embedding_probe.py` combines normalized TF-IDF and BGE vectors with a predeclared 0.5/0.5 cosine weight; it is experiment-only and does not add an SDK/MCP backend. The anonymized report is `results/hybrid_embedding_probe.json`. On the assistant-authored eight-question holdout:

| Method | Baseline Recall | Baseline labeled precision | Guarded Recall | Guarded labeled precision | Guarded negative-hit questions | Warm core recall p95 |
|---|---:|---:|---:|---:|---:|---:|
| TF-IDF | 1.00 | 0.40 | 1.00 | 0.667 | 0/8 | 2.93 ms |
| BGE | 0.9375 | 0.375 | 0.9375 | 0.575 | 2/8 | 40.79 ms |
| 50/50 hybrid | 1.00 | 0.40 | 1.00 | 0.667 | 0/8 | 41.81 ms |

The hybrid restored the TF-IDF result but produced no quality gain. Across the six public diagnostics it exactly retained the existing outcomes: four wrong-anchor guards still drop recall from 1.00 to 0, synonym candidate omission remains 0, and the positive control remains 1.00. One Windows CPU process measured first model load/encode at **4.59s**, working-set growth about **485.1 MiB**, and model files **183.3 MiB**. These are one-run small-corpus measurements, not a latency or memory SLA.

Decision: do not promote `hybrid` to the product interface. The minimum no-regression gate passed, but there was no measured relevance gain for roughly 14x warm latency plus model startup/memory cost. Three public hybrid-provider tests were developed red-to-green; the full baseline-compatible suite passed **356 tests in 15.44s** with optional semantic import isolated, while the real local BGE probe ran separately. Independent labels or a stronger reranker are required before another semantic promotion decision.

### Local BGE semantic model probe (2026-09-15)

The optional `sentence-transformers` dependency and `BAAI/bge-small-zh-v1.5` were installed locally for an experiment-only comparison. The model is stored under `models/bge-small-zh-v1.5` (ignored by Git), loads offline on CPU and returns 512-dimensional vectors. `experiments/semantic_model_probe.py` writes the anonymized comparison to `results/semantic_model_probe.json`; it does not change SDK/MCP defaults or upload model weights/private text.

On the assistant-authored eight-question holdout, BGE baseline Recall@5 was **0.9375** with labeled-positive precision **0.375** and negative hits on **5/8** questions; the guarded variant kept Recall **0.9375**, precision **0.575**, and negative hits **2/8**. This is not independent evaluation and did not fix the public wrong-anchor or synonym-candidate diagnostics. The code default remains `all-MiniLM-L6-v2`; use BGE only by explicitly selecting `embedding_backend="st"` and a local model path. The fixed hybrid comparison above also found no quality gain, so the next evidence step is independent labels or a stronger reranker rather than another default switch.

## Verified Baseline

### ID-only permutation: graph ties and neutral temporal votes

`python -m experiments.id_permutation_probe /path/to/private-corpus.json` varies only IDs across twelve fixed permutations, each with off/on fresh WAL clones and the same MCP call sequence. All 15 candidates remained eligible; candidate order changed. Before: query-1 budget half hits in **5/12** permutations (both flags). Query-ranked PPR seed order now controls stable equal-score discovery/ranking instead of UUID order; hash determinism retained. This alone reduced failures to one permutation. In that case, removing temporal votes restored the answer: every recency score was 1, but top-K selected an arbitrary five candidates to boost. Temporal now abstains when all input recency scores are equal; still ranks genuinely different recency values. No score weights, default graph hops or maintenance policy changed.

Both defect regressions red before/green after; additional mixed-recency guard passed. Full suite **323 passed in 17.30s**, English v3 default/explicit two-hop recall **0.808/0.984** unchanged. Final ID permutations: **24/24** query-1 full hits and macro budget Recall@5 **1.00 in every run**; original fresh-ID store/link replay **12/12** query-1 full hits (`results/id_permutation_probe.json`). This is one assistant-authored 15-memory debugging corpus, not independent labels or general ID-invariance proof. Precision half hits, partial temporal ties, seed-order ties, high-degree/full-graph cost and production chat quality remain boundaries. Existing DBs/private corpus/raw/client configuration unchanged; test DBs retained. Prior sections preserve historical observations, including ID-based graph tie handling now superseded.

### Stable graph ranking and high-degree SDK cost

Fixed unordered PPR restart iteration, added an atom-ID tie-break to graph ranks, and made trace seed selection deterministic. A six-hash-seed subprocess regression failed before the fix and passed after; **320 passed in 13.87s**. English v3 quality remains **0.808/0.984**. Frozen manually seeded database, fixed IDs/creation times/insertion order and alternating maintenance off/on: twelve runs previously varied, now **all complete rankings identical**, query-1 budget **12/12 full hits** (`results/frozen_replay_probe.json`). Current clock/last-access timestamps are not frozen, and this manual graph differs from store-built graphs.

Original store/link replay with newly generated IDs still produced **5/12** query-1 budget half hits after the fix (before: 6/12). Thus only same-input hash-order nondeterminism is fixed; new-ID tie/candidate ordering and precision half hits remain quality boundaries. No tuning of labels, weights, hops or maintenance policy; no independent chat-quality proof.

Actual SDK budget recall including trace/reinforcement on a uniform causal star (`experiments/high_degree_recall.py`, `results/high_degree_recall.json`): 1k/10k hub degree, five warm samples each, answer **5/5** both; p50 **16.893/179.419ms**, p95 **17.402/183.220ms**. Single-process in-memory synthetic workload, setup/warmup excluded; not disk/concurrency, stable timing or production SLA. Full scoped graph traversal remains a high-degree cost. Existing databases/private corpus/client configuration untouched, temporary DBs retained.

### Indexed seed-incident edges: scale regression

Reproducer: `python experiments/seed_filter_scale.py`; measurements in `results/seed_filter_scale.json`. Four seeds, 1007 atoms and 1k/10k/100k unrelated directed edges in memory; warmup/setup excluded, ten isolated filter samples. Baseline p50 **5.169/58.041/633.418ms**, fixed **0.071/0.070/0.068ms**; all four seeds retained. Retrieval-edge API optionally restricts to seed-incident edges while preserving endpoint scope checks and its unrestricted default. Two-edge seed connections only need incident edges. Endpoint indexes and edge-first checks avoid planner-selected live-edge scans and atom cross products. Direct incoming/outgoing queries also explicitly use their existing endpoint indexes; semantics unchanged.

English v3 recall unchanged **0.808/0.984**. Final tiny MCP replay budget macro recall off/on **1.00/1.00**, precision **0.90/0.90**; earlier on-run query-1 half hit did not recur in this run, but variability is not established fixed. Precision query-0/query-1 remain half hits. No weight/default-hop/maintenance policy changes, no existing DB/private corpus changes. These are filter-stage synthetic measurements, not full recall latency, high-degree graph, disk/concurrent workload, statistical stability or production guarantees; unrestricted PPR still reads the scoped graph.

### MCP label validation and two-edge causal seed retention

Fixed two independent defects: reconstructed replay passed internal Chinese enum values to the English public MCP label interface, which silently downgraded unknown labels to `similar`; direct-only seed filtering discarded seeds connected through a nonlexical causal intermediary. MCP now rejects unknown labels, replay converts enum names, and seed filtering additionally retains seeds supported by two valid causal edges (same agent/tenant, active/warm endpoints, weight*confidence >= 0.05, respecting the configured connectivity threshold). No weights, default candidate hops or maintenance defaults changed.

Both public regression tests reproduced the defects before the fixes. Full suite: **318 passed in 12.95s**. Fresh corrected replay (`results/mcp_session_replay_fix.json`): original budget query-0 retrieves **2/2** labels with maintenance off and on; macro Recall@5 **1.00/0.95**, precision **0.40/0.38**. Precision mode macro recall is **0.90/0.90**. Label conversion alone did not resolve query-0. English v3 quality remains default budget **0.808**, explicit two-hop **0.984**. This is a tiny assistant-authored debugging corpus, not independent or raw-dialogue evidence; remaining half hits are not causally attributable to maintenance.

Additional scope-wide edge materialization has unmeasured large-graph cost. Ten maintenance calls succeeded, but one maintenance round trip took **59.452ms** and on boundary-to-session responses ranged **11.154–66.030ms**; no imperceptibility claim. Existing databases/private corpus/client configuration untouched. The next section preserves the historical, incorrectly label-mapped replay and is **not evidence of correctly replayed causal edges**.

### Reconstructed incident corpus: MCP session and idle-boundary replay

`python experiments/mcp_session_replay.py /path/to/private-corpus.json` replays the local corpus through actual MCP subprocess store/link/session-start/recall calls into two fresh WAL files, off then on. Report `results/mcp_session_replay.json` contains only ordinal IDs and metrics; private corpus text is not committed. The local corpus has 15 memories, 10 assistant-authored questions and manual causal edges reconstructed from five incident summaries: **not raw dialogue, independent labels or held-out evaluation**. Original timestamps, tenant scope and lifecycle are not reconstructed: all supplied atoms are treated as currently available to one test agent. This is not equivalent to the earlier cutoff-aware two-hop retrieval evaluation.

| Mode | Off / on macro Recall@5 | Off / on macro precision | Off / on recall round-trip p95 ms |
|---|---|---|---|
| precision | 0.85 / 0.85 | 0.34 / 0.34 | 3.516 / 3.577 |
| default budget | 0.80 / 0.80 | 0.32 / 0.32 | 4.422 / 4.803 |

**10/10** maintenance calls after the previous response and before new session start truncated and observed WAL zero; maintenance stage **4.783–9.135ms**, round trip **4.922–9.294ms**. Boundary-to-session response (including maintenance when on) was **4.891–7.911ms off**, **10.154–17.394ms on**. These are single-run tiny-corpus measurements, not statistically stable timing or user perception. Session-start recalled ten memories but injection relevance/LLM answers were not scored. Neither macro recall changed under maintenance, but budget **query-0 returned zero relevant memories**, and three precision questions retrieved only half the labels. This step records that quality gap; it does not fix it, retune weights or claim reliable answer quality. Full regression **316 passed in 13.06s**. Default remains off, private corpus/existing DBs/raw/client configuration untouched; temporary DBs retained. Next: diagnose the zero-hit query using frozen labels and verify any general fix separately, before claiming real-chat improvements.

### 100k MCP maintenance on/off comparison

Replay `python experiments/mcp_maintenance_comparison.py`; full events in `results/mcp_maintenance_comparison.json`. One dense Chinese 100k seed was cloned via SQLite backup into four fresh WAL DBs, off/on/on/off order, default auto-checkpoint in all. One warm-up and one MCP store before each of 30 rounds; off pipelines ping then budget recall (top_k=5), on pipelines checkpoint then the same recall. No concurrent writer, external locks, held snapshots, graph or concurrent formal tests. Seeding/initialization/warm-up excluded from pair timing. A preliminary script used a nonexistent FTS table name and failed its post-run check; after correction all four reported runs restarted from fresh clones of the read-only generated seed.

| Order | Manual maintenance | Anchor hits | Queued pair p95/p99 ms | Sampled WAL peak bytes |
|---|---|---:|---|---:|
| 1 | off | 30/30 | 359.687 / 387.883 | 4194192 |
| 2 | on | 30/30 | 365.629 / 372.770 | 251352 |
| 3 | on | 30/30 | 420.447 / 428.038 | 251352 |
| 4 | off | 30/30 | 327.047 / 329.046 | 4218912 |

**120/120** anchor hits, **60/60** maintenance success with reported WAL zero; all four SQLite and both external-content FTS integrity checks passed. Checkpoint stage ranges: **6.055–10.611 / 5.836–9.413ms**; checkpoint response p95 **8.711/8.705ms**. After load: **316 passed in 12.75s**. No product policy changed.

Pair timing includes the first request plus queued recall, not isolated recall. The sampled WAL reduction (~4.2MB to 0.25MB) is specific to this sequential small-write workload; off also lacked the earlier concurrent soak's cumulative growth. On pair p95 was ~366–420ms versus off ~327–360ms. Two short runs/configuration do not establish stable causal timing or zero user-visible impact; the full difference cannot be attributed solely to checkpoint duration. Sampling is not a hard WAL maximum. No LLM/UI, user perception, multi-process or long-duration MCP claim; default remains off, test DBs retained and existing data/client configuration untouched. Next: realistic cross-session relevance/whole-call cases and idle-boundary maintenance evaluation.

### Explicit opt-in MCP maintenance

MCP `--wal-maintenance` explicitly enables WAL for the selected file and exposes a ninth tool, `vibe_checkpoint`, with optional finite non-negative `drain_timeout` (default 1 second). Without the flag the original eight tools remain, checkpoint calls are unknown-tool errors, and the current journal mode is untouched. No scheduler, background thread or client configuration change is added. Ordinary tools enter one controller operation, including direct storage short-ID reads; nested SDK calls reuse admission. Checkpoint executes outside that operation to avoid self-draining. This sequential stdio server cannot process another request during maintenance: later requests wait in its input stream. External connections/processes remain uncoordinated and may produce busy. The drain budget is not a total pause/I/O deadline.

TDD: the first public CLI/protocol test failed because the flag was unrecognized, then passed after wiring. Four real-subprocess regressions cover opt-in truncation with preserved recall, default tool unavailability, an external retained SQLite snapshot returning busy and recovery after release (plus short-ID link/forget), and invalid budget error followed by usable tools. **34 MCP tests pass; full regression 316 passed in 15.05s.** Whole-tool concurrent gating is not separately established by sequential MCP tests; controller concurrency remains covered by existing SDK tests.

Replay `python experiments/mcp_maintenance_smoke.py`; `results/mcp_maintenance_smoke.json` uses a fresh temporary DB with two synthetic English memories and 30 pipelined checkpoint-then-recall rounds. **30/30** maintenance calls truncated, observed WAL zero, and **30/30** recalls retained the 60-second answer. Checkpoint round-trip p50/p95/p99: **5.132/10.956/20.020ms**. Time from sending both requests to receiving the queued recall (maintenance plus recall, not isolated recall latency): **6.121/12.454/23.020ms**. Initialization/seeding excluded; no other workers or external locks. This establishes enabled-entry protocol replay, not a 100k MCP result, maintenance-free comparison, user perception or LLM/UI chat. No existing DB changed; temporary DB retained. CLI/HTTP maintenance integration and HTTP thread/session risks remain outside this change.

### Application-entry inventory and cross-session smoke (before MCP wiring)

Historical inventory below motivated the MCP change above; its missing MCP controller/trigger and proposed implementation are no longer current. CLI/HTTP findings remain unimplemented. The counts and timings belong to that earlier smoke run.

Local MCP stdio subprocess verification (`results/mcp_interaction_smoke.json`) initialized the server, started a session, stored a summary plus highlight at session end, started another session and recalled the exact 60-second API timeout answer. Two memories were recalled; measured end/start/recall round trips were **7.527/6.263/2.177ms**, with cold initialization **278.786ms**. These are individual tiny-corpus calls, not latency percentiles or an LLM-chat result. MCP/session-manager regressions: **54 passed in 6.43s**; replay with `python -m pytest tests/test_mcp.py tests/test_session_manager.py -q`. The 312-test total above belongs to the preceding endurance verification, not a new full-suite run here.

Application inventory: MCP `run_server`, HTTP `VibeHTTPServer.__init__`, and CLI `SessionManager.__init__` construct SDK instances without a maintenance controller or maintenance trigger. Thus the default entries do **not** expose enabled-maintenance behavior. MCP also resolves short IDs using direct storage reads in `vibe_link` and the `vibe_forget` fallback; any future coordination must cover those reads together with the complete tool operation. HTTP dispatches multiple request threads through one class-level SDK/session state; controller integration alone would not establish safe per-thread connections or session isolation. HTTP was inspected, not runtime-verified in this step.

Next implementation seam: explicit opt-in MCP maintenance wiring and an explicit trigger, keeping default tool behavior/default-off unchanged and coordinating whole tool operations including direct storage reads. Then measure protocol round trips with maintenance enabled. Do not simulate that feature by monkeypatching the entry or describe SDK-only load as actual chat. Real model/UI interaction still needs a selected client workflow and remains unverified. No existing memory database or client configuration was changed.

### 30-minute SDK maintenance endurance check

`results/disk_soak_sdk_maintenance_30min.json` records a fresh synthetic 100k WAL database running for 1800.464 seconds (seeding excluded), two independent SDK readers and one explicitly coordinated raw CRUD writer holding a write lock for 50ms per cycle. Replay: `python experiments/disk_soak_benchmark.py --scale 100000 --seconds 1800 --checkpoint-strategy sdk-coordinated`. Full regression before load: **312 passed in 12.56s**; no formal tests or benchmarks ran concurrently during load. Only benchmark instrumentation changed: checkpoint events now retain pre-maintenance WAL size.

**8974/8974** anchor hits; reader p95 **434.085/428.814ms**, p99 **464.066/462.783ms**, including admission waiting. The writer completed **32426** insert/update cycles and **32298** deletions (~18.0 cycles/s), with cycle p95/p99 **54.603/68.659ms**. Post-join retained IDs/content, SQLite and both external-content FTS integrity checks passed; final TRUNCATE returned [0,0,0] and observed WAL zero.

All **174** checkpoints started before the 1800-second deadline succeeded and observed WAL zero; the 175th started at the deadline and is excluded from runtime success counts. Sampled WAL peak: **57,980,792 bytes**. Ten-minute phase peaks were **50,700,752 / 57,980,792 / 48,121,632 bytes** (58 runtime samples each), showing no cumulative growth at the sampled points. Drain/checkpoint duration was **42.519–501.056ms**, p50/p95/p99 **358.501/441.386/462.225ms** (linear percentiles). Reader percentiles are whole-run aggregates, not time-window tail stability proof.

Skipped reinforcement remained **8637/8974 (~96.2%)**; successful retrieval does not prove reliable learning updates. This single local synthetic run is not a hard WAL/pause bound, real-chat quality test, hour-scale endurance, multi-process coordination or power-loss proof. Maintenance remains opt-in/default-off; no SDK policy or background scheduler changed. Next: inventory actual application accesses and test user-visible maintenance pauses in realistic interactions before enabling it.

### Explicit SDK WAL maintenance

`WALMaintenance(db_path)` is now exported alongside `VibeMemory`. Pass the same controller to each same-file SDK instance via `wal_maintenance=controller`; the default is `None`, and no scheduler, maintenance thread or default journal/timeout change is introduced. The application explicitly calls `controller.checkpoint(drain_timeout=1.0)`. SDK initialization and all public operations participate in a reentrant, process-local admission gate. Nested SDK operations already admitted on the same thread continue during draining; independent SDK instances retain independent SQLite connections. This does **not** make one SDK/connection safe to share concurrently.

Maintenance closes admission, drains active operations, then attempts TRUNCATE using a separate existing-file SQLite connection (`mode=rw`, timeout=0). SDK connection settings are untouched. A drain timeout skips the checkpoint rather than extending the pause with a fallback checkpoint. Concurrent maintenance returns immediately; all success/error/timeout paths restore admission. External BUSY/LOCKED codes, including errors while reading journal mode, are reported as busy; other SQLite failures propagate. Memory/URI paths are rejected, mismatched SDK paths are rejected before opening a new database, and non-WAL maintenance fails explicitly without switching modes. Missing databases are not created by maintenance.

| Report status | Meaning |
|---|---|
| `truncated` | SQLite TRUNCATE succeeded at the checkpoint; not a permanent space bound |
| `drain_timeout` | Admitted operations did not finish in time; checkpoint skipped |
| `maintenance_busy` | Another maintenance call is already draining/checkpointing |
| `busy` | SQLite encountered an external lock or could not complete truncation |

Reports include the native checkpoint tuple (or `None` if unavailable), observed `wal_bytes_after`, and `elapsed_ms`. `drain_timeout` is a waiting limit, **not** a hard total pause/SQLite I/O deadline. No queue or reinforcement retry is added. All accesses bypassing SDK methods—including raw storage, caller-managed transactions, directly invoked indexer/GC/cold-start modules, or external reflectors—must be wrapped in `with controller.operation():` for their entire database operation/transaction. Do not call checkpoint inside that scope: it raises rather than waiting on itself. Calls from other processes, other controllers or uncoordinated connections cannot be drained; external snapshots can still prevent truncation. Controller setup must happen before creating concurrent SDK instances, and the database file/path must not be replaced during use.

Nine real-file integration tests cover successful maintenance with recall preserved, blocked SDK writes draining, delayed recall and nested injection, drain timeout/admission recovery, initialization gating/default non-participation, retained external read snapshots, explicit validation/error recovery, no missing-file creation, and exclusive-lock reporting. Full regression: **312 passed**; English v3 default/explicit-two-hop Recall@5 remain **0.808/0.984**. No private or existing user database was modified. Replay the SDK integration load with `python experiments/disk_soak_benchmark.py --scale 100000 --seconds 60 --checkpoint-strategy sdk-coordinated`; SDK readers join automatically, while the raw CRUD writer explicitly scopes each whole cycle. Historical experimental comparisons below are not measurements of this new controller.

SDK-controller mixed-load result (`results/disk_soak_sdk_maintenance.json`): 100k dense atoms, 60.378 seconds, two automatically coordinated SDK readers plus one explicitly scoped raw CRUD writer. **299/299** anchor hits, 1100 write cycles/972 deletions, post-join CRUD/SQLite/FTS checks passed. All five checkpoints started before the 60-second deadline returned TRUNCATE success and observed WAL size zero; sampled peak **47,668,432 bytes**. Runtime drain/checkpoint stages were **151.280–396.609ms**, reader p95 **444.659/434.051ms**, p99 **504.611/580.609ms**. Skipped reinforcement remained **286/299 (~95.7%)**. The sixth checkpoint began at the load deadline and is not counted as a runtime success. This single short run establishes controller integration, not improved overall tails, reliable reinforcement, a hard pause/space bound or long-term stability. Only fresh synthetic temporary DBs were used; no formal benchmark or test suite ran concurrently during the mixed-load phase.

## Runtime checkpoint comparison (historical experiment)

The soak CLI accepts `--checkpoint-strategy passive|truncate|coordinated`; passive remains the default. See `results/disk_checkpoint_comparison.json`. Each sequential run used a fresh 100k dense WAL database, two independent SDK readers, one CRUD writer holding the write lock 50ms per cycle, and 60 seconds of load.

| Strategy | Sampled WAL peak bytes | Runtime TRUNCATE success | Calls / anchor hits | Reader p99 ms | Write cycles |
|---|---:|---:|---:|---|---:|
| PASSIVE | 265340392 | not attempted | 305/305 | 420.791 / 423.221 | 1125 |
| TRUNCATE, 500ms lock wait | 263696512 | 0/5 | 307/307 | 419.057 / 431.841 | 1119 |
| Cooperative drain + TRUNCATE | 47408872 | 5/5 | 307/307 | 437.132 / 441.897 | 1101 |

Coordinated mode closes admission for all three experiment workers, waits at most one second for active calls/cycles to finish, then attempts TRUNCATE with a 500ms diagnostic-connection busy timeout. A drain timeout falls back to PASSIVE and always reopens admission. Admission waiting is included in reader and writer latency. Runtime drain/checkpoint episodes lasted 170.569–323.201ms; successful checkpoints observed WAL size zero before resuming workers. The sampled peak was ~82.1% below this baseline, with ~2.1% fewer write cycles and slightly higher reader tails. Skipped reinforcement remained 292/307, so this is not reliable learning delivery.

All three runs passed CRUD, SQLite and both external-content FTS integrity checks, and post-join truncation. The checkpoint event at/after 60 seconds is not counted as a runtime success. Full regression: 303 passed. Single runs are not statistically stable timing comparisons: baseline briefly overlapped the 11.72s pytest run, and instrumentation expanded between runs. Ten-second sampling is not a hard WAL maximum, the busy timeout is not a total execution deadline, and no production/hour-scale/multi-process guarantee is established.

The original cooperative implementation measured in this section is an explicit **experiment option only**. The newer SDK controller is documented above and measured separately; these historical numbers do not establish its performance. Production use requires all database users to participate in coordination and an agreed pause/space budget; an uncoordinated connection or long snapshot can still prevent truncation. Never delete WAL/SHM files to reclaim space. See [SQLite WAL checkpoint starvation](https://www.sqlite.org/wal.html) and [checkpoint modes](https://www.sqlite.org/pragma.html#pragma_wal_checkpoint).


Atom reinforcement now uses `storage.reinforce_atoms`: one scoped metadata-only UPDATE and commit for the batch, with current weight increment/clamp and access_count increment in SQL. It does not mention content/summary, so the existing UPDATE OF text FTS triggers do not run. Current rows are read within the same write transaction and replace returned SDK atoms only after successful commit. This preserves concurrent text edits and avoids lost access increments; other tenants/agents and non-active/non-warm rows are excluded. Atom batches are atomic; graph-edge reinforcement remains separately committed and the existing zero-wait BUSY/LOCKED skip policy is unchanged.

Isolated comparison (`experiments/reinforcement_write_benchmark.py`, `results/reinforcement_write.json`) recreates the former full-row path versus the new batch on 1000-atom fresh WAL files, 100 batches of five atoms, with test-only auto-checkpoint disabled. WAL writes were 36,593,872 versus 412,032 bytes (~98.9% lower); batch p95 3.616 versus 0.698 ms. All five access counts reached 100 and both FTS integrity checks passed. This is a reinforcement-only write-amplification benefit, not a claim about mixed CRUD WAL peaks, hard WAL bounds, or delivery of skipped reinforcement.

Same-condition 100k/300s mixed-load repeat (`results/disk_soak_atomic.json`) completed 1359/1359 anchor hits, 5532 write cycles/5404 deletions and all CRUD/SQLite/FTS consistency checks. Skipped reinforcement remained 1341/1359 (~98.7%); SDK p95 was 584.303/600.536 ms and p99 759.520/766.741 ms, sampled WAL peak 1,268,655,152 bytes, truncating to zero after load. These single-run mixed-workload tails/peak did not improve; the isolated benefit must not be generalized. Persistent writer pressure still prevents reliable delivery under the intentionally non-blocking policy. No queue, retries or default checkpoint/lock-wait changes were introduced.

Final verification is **303 tests passed**. A pre-existing timing-sensitive two-hop candidate test failed during verification; a fixed-time regression reproduced the cause: an already-selected causal neighbor in the lexical tail could be removed when adding another graph neighbor. Graph retention now includes selected neighbors and removes duplicates before trimming the lexical portion, preserving the total budget. Fixed English v3 default/explicit-two-hop Recall@5 remain 0.808/0.984. This graph fix does not affect the no-graph soak conditions.

100k dense WAL-file mixed-load soak (`experiments/disk_soak_benchmark.py`, `results/disk_soak.json`) ran for 300.240 seconds with two independent SDK readers and one CRUD writer. Reader calls/hits were 754/754 and 751/751 (1505/1505 combined); p95 was 409.465/410.174 ms and p99 417.579/419.588 ms. The writer completed 5617 insert/update cycles and 5489 deletions, with a deliberate 50ms write lock each cycle. No worker exception occurred; post-join retained writer content/IDs, SQLite and both external-content FTS integrity checks passed. Default auto-checkpoint plus test-monitor PASSIVE calls every ten seconds were used, with no explicitly held reader snapshot. Seeding is excluded, barrier startup included.

**Capacity boundaries remain:** 1484/1505 calls (98.6%) skipped some/all reinforcement under this deliberate lock pressure. `recall()` now exposes the boolean `reinforcement_skipped` so skipped learning is not inferred from successful recall. Sampled WAL peak was 1,098,346,712 bytes (~1.10GB), even with 30 PASSIVE checks; last checkpoint reported [0,266589,266176]. After workers stopped, TRUNCATE returned [0,0,0] and WAL size was zero. This is a passed five-minute recall/consistency reproduction, not a bounded-WAL, reinforcement-delivery, production, multi-process or power-loss guarantee. No new retrieval/consistency failure was observed, so no additional core workaround was applied. Results depend on this repeated whole-query, no-graph corpus and lock-heavy workload; 10s samples are not a hard peak bound. Temporary test DB is retained locally.

SDK reinforcement contention is fixed (`results/disk_pressure_after.json`, v2). Only post-retrieval reinforcement temporarily uses busy_timeout=0, restores the original setting in finally, rolls back a failed reinforcement transaction, and skips remaining reinforcement on primary BUSY/LOCKED codes (including extended variants). Other OperationalErrors are re-raised. Copies are reinforced so a failed update does not mutate returned atoms. Existing caller transactions cause reinforcement to be skipped without commit/rollback. Successful earlier per-atom commits are not undone if a later reinforcement fails; skipped updates are not queued for retry. This does not make shared SDK instances thread-safe or guarantee non-blocking core retrieval/initialization.

Three regressions cover write-lock fast return, reinforcement after release, readonly error propagation, and caller-transaction preservation; **299 tests pass**. Six-second write-lock reproduction now returns the anchor with no SDK error in 0.563 ms, versus about 5486 ms then BUSY before. 1k/10k dense disk old answers remain 10/10; SDK warm p95 is 7.596/36.123 ms, not a general latency improvement. Prior disk-pressure-v1 results below are historical failure evidence; the CLI now requires successful SDK hits under the lock.

Historical disk-pressure-v1 (`results/disk_pressure.json`) measured full SDK separately from lower-level recall. Under a six-second write lock, SDK reinforcement failed after about 5.5 seconds; this was fixed by the delivery described above. Its expected-error CLI criterion is also historical: the current disk-pressure-v2 script requires successful SDK recall under the lock. A held-reader snapshot with test-only auto-checkpoint disabled pinned 12,479,512 WAL bytes, then truncated successfully after release. These prior seconds-long results are not endurance or power-loss proof.

WAL recovery validation (`experiments/wal_recovery_validation.py`, `results/wal_recovery.json`) now covers held read/write transactions, competing writer rejection, snapshot retention, a pinned TRUNCATE checkpoint and successful truncation after releasing the reader. A child process is killed only after acknowledging one committed atom plus a pending update; reopening preserves and recalls the committed content, discards the pending update, and passes SQLite plus both external-content FTS integrity checks. **296 tests pass**. No core defaults or transaction API changed. This deterministic single-run validation is not a long-duration load benchmark, power-loss/torn-I/O proof, or shared-SDK concurrency guarantee. Test-only connections disable auto-checkpoint and set zero busy timeout to observe blocking without timing assumptions.

Explicit SQLite journal configuration is available through both SDK and storage: `journal_mode=None` leaves the current database mode untouched; lowercase `wal` and `delete` are opt-in. Invalid options are rejected before file creation, unavailable modes fail rather than silently downgrade, and failed mode setup closes the connection. WAL reopens preserve stored memory and the persisted mode. Seven new tests and the full **294-test** suite pass. The disk benchmark now uses this public configuration seam; a fresh 10k WAL run completed 400 CRUD cycles and 400/400 anchor recalls with SQLite/FTS integrity checks passing. No synchronous or timeout defaults changed. This does not prove shared-instance thread safety or crash recovery.

Disk multi-connection validation (`experiments/disk_concurrency_benchmark.py`) uses a fresh temporary file DB, 10k seed atoms, two independent writer connections (200 CRUD cycles each) and two recall-reader connections (200 calls each), synchronized at a barrier. Both DELETE and WAL runs had zero worker errors, 400/400 anchor hits, correct post-join edited/deleted candidate sets, and successful SQLite plus external-content FTS integrity checks. Reader p99 was 480.591/282.235 ms under DELETE versus 6.106/7.179 ms under WAL. Writer p99 was 22.166/21.544 versus 35.437/51.524 ms; WAL is not a universal speedup. Results are single-run, selective synthetic thread workloads, not long-duration/process/crash/production proof. Only benchmark-owned temp DBs change journal mode; core defaults and existing memory DBs are unchanged. Concurrent use of a single shared SDK/connection is not tested. CLI failures return nonzero. Temp databases are retained locally for inspection; public results redact their paths.

High-match Chinese candidate selection now uses `bm25(atoms_trigram)` before recency, rather than newest-row-only truncation. A public recall regression keeps an older exact answer ahead of 250 verbose full-query matches while excluding foreign tenant/agent and archived atoms. In `chinese-dense-v1`, old-answer Top-5 hits changed from 0/10 to 10/10 at 1k and 10k; the fixed implementation also achieved 10/10 at 100k. This quality fix costs scoring all matches: warm p95 at 10k rose from 1.783 to 24.587 ms, and fixed 100k p95 was 323.531 ms. The prior 6.426 ms selective-query result is not a high-match-rate SLA. English candidate ordering is unchanged, and existing English/pilot quality remained unchanged. Equally relevant matches can still be resolved by recency; old memories are not unconditionally preferred.

Chinese candidate scaling now uses a native SQLite FTS5 trigram external-content index with insert/update/delete triggers and a tenant/agent recency index for candidate backfill. Existing databases backfill the trigram index at first open. Queries with Chinese runs of at least three characters use indexed trigrams; two-character-only queries or unsupported SQLite builds keep LIKE. English uses unicode61 as before. The previous Chinese LIKE paragraph below records the earlier implementation.

`experiments/chinese_scale_benchmark.py` measures serial in-memory Chinese retrieval with tracemalloc enabled, 20 repeats of one selective query and no graph edges. At 1k/10k/100k atoms, warm p95 changed from 16.923/113.272/918.594 ms to 6.038/6.249/6.426 ms; the old answer was in Top-5 for 20/20 calls at each scale. At 100k, process working set after recall rose from 96.91 to 140.50 MB; Python recall allocation peak stayed 0.63 MB. Working sets are process-wide and scales share a process, not isolated per-store memory. Synthetic results do not establish disk/concurrency/high-match-rate performance. Legacy migration smoke, edit/delete/reopen and short-query tests passed. Local reconstructed pilot quality remains BM25 0.85, TF-IDF 0.90, budget 0.85; English v3 remains 0.808/0.984.

Chinese lexical retrieval now uses dependency-free CJK character bigrams in TF-IDF/BM25. CJK budget queries use the tenant/agent-scoped LIKE candidate fallback because unicode61 does not segment Chinese into matching bigrams; candidate hydration stays bounded but SQL scan cost increases. Budget TF-IDF zero-score padding no longer counts as semantic graph seeds. A 131-atom regression retrieves an old Chinese answer beyond the 100-candidate cutoff. On a local 5-incident/10-question document-reconstructed debugging set, Recall@5 changed: BM25 0.25→0.85, TF-IDF 0.60→0.90, two-hop budget 0.45→0.85. These assistant-authored labels/edges are not independent held-out evidence and the private corpus is not published. English synthetic v3 quality remains 0.808/0.984 (one/two hops). Large Chinese corpus latency and synonym understanding remain unverified.

External session retrieval evaluation is available via `experiments/session_evaluation.py`; see `experiments/SESSION_EVALUATION.md`. It uses query cutoffs and human relevance labels, compares empty retrieval/BM25/TF-IDF/two-hop budget, and prints IDs/metrics rather than corpus text. Only an explicitly synthetic interface smoke has run; no real corpus or Agent answer-quality evidence is available yet. Corpus snapshots and anonymized IDs must be reviewed before use. This preparatory addition does not change the core retrieval path.

PPR and recall traces now load only active edges whose two endpoints are active/warm memories in the seed agent/tenant scope. Foreign-agent, foreign-tenant and archived bridge nodes cannot influence PPR scores. Mixed-scope seeds raise ValueError; warm memories and a seed tenant different from the storage default remain supported. This avoids materializing other scopes' edges, but does not cap the current scope's graph size or SQL scanning time. The v3 quality sweep is unchanged (0.808 one hop, 0.984 two hops); this run's p95 was 8.760 / 8.719 ms, so no speedup is claimed.

Candidate expansion now caps depth at two hops, returned edge rows at `2 * candidate_limit` per hop, and frontier nodes at `candidate_limit`. A 500-neighbor regression retains the strongest causal answer within 10 candidates. The v3 quality sweep remains 0.808 for one hop and 0.984 for two hops; SQL scanning/sorting and full PPR traversal still have no strict time bound. High-fanout truncation can omit weaker paths and is not a lossless graph search.

The 2026-09-13 v3 retrieval run removes query-word leakage from graph-only answers. Budget fusion now respects connectivity-rejected semantic seeds across lexical lists. On the same v3 corpus, default one-hop/20% Recall@5 improved from 0.792 to 0.808 (p95 5.771 ms); explicit two-hop/20% reached 0.984 (p95 5.816 ms). One hop remains the default. Candidate hydration is bounded, but graph edge traversal is not a strict execution-time budget. These are synthetic regression results, not held-out production evidence. Full tests passed with a fresh `--basetemp` directory, avoiding inaccessible old Windows pytest temp files.

| Item | Result |
|------|--------|
| Platform | Windows, Python 3.12.14 |
| Test command | `python -m pytest -q` |
| Test result | **287 passed, 0 failed** |
| Coverage | **74%** aggregate (previous run; not remeasured this round) |
| Package version | 0.3.0 |

The reproducible local retrieval ablation (`experiments/retrieval_benchmark.py`) uses 1,000 synthetic atoms and 100 fixed queries. One Windows + Python 3.12.14 run measured: TF-IDF noise 40.00%, PPR with all labels 27.40%, and PPR with precision labels plus seed filtering 0%; p95 latency was 0.130 ms, 1.056 ms, and 0.901 ms respectively. These are synthetic regression numbers, not public-benchmark or production claims.

The SDK scale/visibility baseline (`experiments/scale_visibility_benchmark.py`) uses serial in-memory SQLite with TF-IDF, automatic edge building and Episode aggregation disabled. Budget recall hydrates at most `max(100, top_k * 20)` active/warm candidates selected through persistent SQLite FTS5, replacing low-priority text candidates with indexed one-hop causal neighbors when available; `LIKE` remains the compatibility fallback. The v3 baseline runs 20 deterministic recalls so cold and warm latency are explicit. At 1,000/10,000/100,000 atoms, cold recall was 5.459/4.371/11.613 ms and warm p95 was 1.614/1.724/1.688 ms. Write throughput was 10,734/11,080/10,025 ops/s and sampled post-commit direct-read visibility remained 100%. This is not a concurrent, disk-backed, provider, or production workload result.

The v2 retrieval ablation includes the complete budget pipeline. On the fixed 1,000-atom/100-query corpus, causal-neighbor candidate replacement, graph-weighted RRF, and removal of the duplicate TF-IDF rerank raised Precision@5/Recall@5 from 0.720/0.648 to 0.796/0.796. MRR remained 1.000, noise fell from 28.0% to 20.4%, and p95 latency moved from 5.387 ms to 5.679 ms. These are synthetic regression results, not general product claims.

Coverage does not follow the MCP subprocess, so `mcp_server.py` appears as 0% even though 30 JSON-RPC subprocess tests exercise that public interface.

## Capability Status

| Capability | Status | Evidence boundary |
|------------|--------|-------------------|
| Python SDK + SQLite | Verified locally | SDK and storage tests pass |
| TF-IDF/BM25/PPR retrieval | Verified locally | Unit/integration tests and the local 1k/100 ablation pass; public benchmark pending |
| CLI and SessionManager | Verified locally | 24 tests pass |
| MCP stdio | Verified locally | 30 subprocess tests pass on Windows after explicit UTF-8 configuration |
| HTTP/LangChain/OpenAI adapters | Integration-tested | Local tests pass; production use not measured |
| External LLM/semantic providers | Experimental | Mock/interface tests exist; real-provider reliability is not benchmarked |
| Reflect/Knowledge Pages/vibe-init | Experimental | Implemented, but coverage and production evidence are incomplete |
| Multi-tenant/GC/backpressure | Experimental | Unit tests pass; serial SDK scale baseline exists, but concurrent, disk-backed, and edge/episode load tests are pending |

## P0 Progress

- [x] Establish the real test baseline: 265 original tests, now 276 with PPR, cache, sparse retrieval, BM25, bounded candidates, whole-term FTS, and graph-neighbor coverage.
- [x] Fix Windows MCP UTF-8 interoperability.
- [x] Add this canonical status page.
- [x] Add deterministic worked-example tests for PPR semantics.
- [x] Publish a reproducible retrieval benchmark with hard negatives and ablations (`experiments/retrieval_benchmark.py`).
- [x] Reuse the SDK semantic document matrix across recalls with automatic ID/version invalidation.
- [x] Replace cold-start full atom hydration with a tenant-scoped SQL count query.
- [x] Replace full-corpus dense TF-IDF scoring with a sparse inverted index and candidate-only reranking vectors.
- [x] Reuse the BM25 index across recalls and rebuild it after content changes.
- [x] Restrict BM25 query scoring to matching term postings while preserving reference scores and ordering.
- [x] Bound `budget` recall hydration with tenant/lifecycle-scoped storage candidates; keep precision/recall modes unchanged.
- [x] Replace `LIKE` as the primary candidate backend with trigger-synchronized SQLite FTS5; retain `LIKE` as a compatibility fallback.
- [x] Replace low-priority text candidates with bounded one-hop causal neighbors in `budget` mode, weight the filtered graph signal in RRF, and skip its duplicate TF-IDF rerank.
- [x] Add the full budget pipeline to the fixed retrieval ablation so candidate quality is visible beside latency.
- [x] Measure write/recall latency and write-after-read visibility at 1k/10k/100k atoms (`experiments/scale_visibility_benchmark.py`).
- [ ] Add concurrent, disk-backed, multi-tenant, and edge/episode load measurements.

## Current Evidence Gaps

- The reported 20% → 0% noise reduction comes from a small private experiment and is not yet a general product claim.
- LOCOMO and LongMemEval have not been run.
- The scale result is serial and in-memory with automatic edge/episode work disabled; there is no concurrent multi-tenant or production workload report.
- Real external-provider latency, cost, failure, and fallback behavior are not benchmarked.

The next milestone should improve evidence and correctness rather than add another integration surface.
