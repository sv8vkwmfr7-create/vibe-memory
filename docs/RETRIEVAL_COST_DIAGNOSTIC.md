# Retrieval cost diagnostic — 2026-10-01

## Metadata cache-key tradeoff — 2026-10-08

The local content-digest repair avoids unnecessary TF-IDF/BM25 rebuilding but
adds per-query hashing. Fixed-ID/time isolated old/new package copies (only
cache-key expression differs), 1k/10k synthetic in-memory public SDK/storage,
precision/recall and two reversed-order repetitions: 272 timed calls, all
136 paired returned ID/order/content/confidence sequences equal, no failures.
No profiler/tracer in latency calls; four additional allocation-only recalls.

10k confidence-update recall medians: precision 183.15→24.50ms, recall
186.00→24.95ms. Unchanged warm medians: precision 17.72→23.47ms, recall
17.19→23.98ms. Thus roughly 86.6% improvement on metadata-triggered refits
comes with roughly 32.5–39.5% warm-query slowdown on this fixture, not overall
acceleration. One traced precision run/version records 650,048 extra retained
Python bytes after first recall/GC; metadata-call incremental peak falls from
16,127,951 to 6,286,818 bytes. Not total memory, peak RSS or a leak test.

Next reduce unchanged-query overhead, preserving public mutation visibility
and corpus ordering/membership. No production change in this measurement turn;
original source and all earlier unrelated work retained. Two repetitions,
uncontrolled host load and one query per phase do not establish a production
SLA or independent relevance benefit. Disk/dense/graph/100k limits remain open.
Protocol, raw JSON cells, ranges and source/report hashes:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/metadata-comparison-20261008-a/REPORT.md`.

## Scoped trace-read optimization — 2026-10-04

### High-degree star follow-up

The same harness now accepts `--graph-shape star` (chain remains default), with
public storage fixture checks for edge count and the star's common origin.
1,000 atoms, 999 outward edges from the target anchor, six calls per config:
warm median precision 37.82ms, recall 109.16ms; graph-free 7.01/8.42ms.
All 24 calls hit the anchor without degradation failures. This is a high-degree
single star, not an arbitrary dense graph or independent ranking benchmark.

Separate cProfile replay completed, exit 0. Aggregate across all 24 calls:
retrieval 1.780s, PPR 1.082s, PPR's edge read 0.074s, trace edge read 0.100s,
seed-filter edge read 0.102s. Cumulative values overlap and must not be summed.
Two additional edge reads (0.012s) are fixture validation, not retrieval.
PPR computes transitions and normalization repeatedly each iteration; this is
the next measured optimization target, not grounds for capping graph degree or
reducing recall. Per-call reuse of unchanged transition data could preserve
the walk, but mathematical/ranking regression must precede a performance claim.
Follow-up production change now reuses each visited node's transition list and
strength sum only within one PPR call. Keeps edge order, strength multiplication,
walk arithmetic, iteration cap and convergence unchanged; no degree cap or
cross-query cache. Existing closed-form/determinism/tenant/projection/direction
subset: 106 passed / 4.41s. Star cProfile before/after PPR cumulative
1.082s→0.439s, all 24 output-ID sequences and anchor counts unchanged. Profiled
star recall warm medians 226.77→108.76ms; precision 47.88→47.80ms. Single
uncontrolled runs with profiling overhead, not a stable end-to-end guarantee.
The cache retains extra tuples for visited-node transitions (up to O(edges))
until the call ends, trading temporary memory for repeated computation; memory
incremental cost is not yet isolated against the old implementation. Post-change
full regression completed: 989 passed / 121.73s, exit 0, Python 3.12.14 with
offline model-hub flags and a fresh `.tmp-ppr-transition-full-20261004` root.
The earlier full coverage reports predate this PPR change and are not current
coverage proof for it.

Separate warm public-SDK tracemalloc diagnostic, in-memory TF-IDF star, one
measured call per mode/scale after warm-up: 1k precision/recall peaks
1,270,961/1,685,362 bytes; 10k peaks 14,028,865/19,187,130 bytes. All four calls
hit the anchor without degradation. Equal fixture timestamps, fixed IDs, no
model call. These are whole-call traced Python allocations, not cache-only
overhead, process RSS, native allocations, disk measurements or a memory cap.
Initial harness omitted required MemoryAtom.summary and exited before measurement;
corrected harness produced the stated data, not a product repair. Both diagnostic
and regression original sessions exited normally, with no timeout restart.
Artifacts:
`results/graph_disk_cost_1k_star.json`,
`results/graph_disk_cost_1k_star_profiled.json`,
`results/graph_disk_cost_1k_star.prof`. No memory ceiling was measured.
Post-change: `results/graph_disk_cost_1k_star_transitions.json` and `.prof`.

The current local worktree changes only `build_trace` edge acquisition: use the
existing indexed `get_retrieval_edges(..., atom_ids=seed_ids)` instead of reading
all live scoped edges. Every trace inspected below needs a seed endpoint; the
unique directed endpoint-pair index prevents row order from selecting a different
label for the same pair. Graph-walk inputs, scoring, direction interpretation and
the storage scope/lifecycle guards are unchanged. No cross-query cache is added.

Two cProfile runs of the same 1,000-atom disk TF-IDF high-match fixture (24 calls,
precision/recall, zero/999 chain edges) recorded trace edge-read cumulative time
of 0.074s before and 0.002s after. PPR edge reads remained about 0.073/0.074s.
These cumulative measurements include profiling overhead and host variation;
they are not a stable end-to-end speedup or a production SLA. All 24 result-ID
sequences and anchor-hit counts matched exactly. The benchmark does not record
trace dictionaries, so this comparison alone does not prove trace equivalence.

Existing `test_m2.py` and `test_retrieval_projection.py`: 22 passed / 1.65s.
The original projection tests exercised public SDK graph recall, live/warm
lifecycle, owner isolation and trace endpoint identity. A subsequent expansion
of that existing SDK test covers all eight edge labels in precision/recall and
asserts both returned trace dictionaries, including label, depth and explicit
0.65 confidence, over two recalls. Projection plus causal direction/signal
regressions: 61 passed / 3.19s. This preserves the existing navigational trace
contract; a reverse walk does not prove reverse causation. Multi-path/high-degree
graphs are not covered. The 975-test full run below predates this test expansion.
Fresh full regression: 975 passed / 120.45s, exit 0, Python 3.12.14,
model-hub offline flags, `--basetemp .tmp-trace-full-20261004`. This includes
local uncommitted tests, not hosted CI or independent quality evidence.
The 10,000-atom post-change measurement completed with exit 0. The original
session was polled without restarting. Before/after warm medians (five samples):

| Mode | Edges | Before ms | After ms |
|---|---:|---:|---:|
| precision | 0 | 49.09 | 53.07 |
| precision | 9,999 | 209.46 | 147.50 |
| recall | 0 | 53.98 | 54.53 |
| recall | 9,999 | 175.99 | 129.63 |

All 24 returned-ID sequences and hit counts matched the original report, with
six anchor hits in each configuration. Graph-bearing warm medians decreased
29.6%/26.3% in these individual runs; graph-free runs did not improve. These are
uncontrolled sequential runs, not repeated A/B trials or a guaranteed speedup.
The post-change run overlapped part of the full regression, so host contention
also differs. Comparison artifacts: `results/graph_disk_cost_10k_report.json`
and `results/graph_disk_cost_10k_incident.json`. The single chain does not cover
high-degree graphs or establish a memory ceiling. Trace content equivalence
still needs broader evidence beyond the subsequent direct-edge label checks.

Artifacts: `results/graph_disk_cost_1k_profiled.json`,
`results/graph_disk_cost_1k_incident.json`, and their `.prof` files. The harness's
`production_changed: false` means that the harness itself does not mutate source
or real databases; it is not evidence that this checkout has no production-code
changes. This optimization remains local and uncommitted. Dense-backend memory,
large/high-degree graphs, independent quality and real-host acceptance remain
open; do not close the original performance rows from this single fixture.

Source: pushed `53cfcb649a547d9f23767c8c6eca72b7661e2af9`, plus documentation-only local changes. Windows, Python 3.12.14, SQLite 3.53.1. One fresh process for each scale/mode; synthetic in-memory SQLite, TF-IDF, public SDK store/recall, auto_build_edges=False, auto_episode=False, no graph edges, top_k=5. No real memories, model download, cloud inference or retrieval-default change. This is diagnostic evidence, not an independent benchmark or completed performance fix.

Each fixture has one anchor `连接池耗尽导致接口超时，释放连接后恢复正常`, followed by N-1 memories `日常维护记录编号{i}，桌面主题颜色和背景图片设置完成`. Query: `接口超时如何修复连接池`. One cold and ten repeated warm calls include SDK reinforcement. All nine cases hit the anchor 11/11 with no degradation failures. Budget returns one result, precision/recall five; equal anchor hits do not establish equal completeness/precision or final-answer quality.

## Observations

Working-set values below are MiB despite the existing helper's `mb` name. A thread samples about every 5ms; this is sampled process working set, not an exact allocation/peak attribution. Short calls have very few samples. No tracemalloc; timing includes sampling overhead and uncontrolled host load. Fixture preparation is excluded from query latency but included in pre-recall memory. Cold excludes interpreter startup/fixture creation. Ten warm samples and one query are insufficient for a production tail-latency SLA.

| Atoms | Mode | Cold ms | Warm p50 ms | Warm p95 ms | Before MiB | Sampled peak MiB | After MiB | RSS samples |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | budget | 7.734 | 1.545 | 1.817 | 38.48 | 39.68 | 39.68 | 3 |
| 1,000 | precision | 39.886 | 10.036 | 12.567 | 38.33 | 46.68 | 46.68 | 10 |
| 1,000 | recall | 50.770 | 12.315 | 17.925 | 38.33 | 46.73 | 46.73 | 11 |
| 10,000 | budget | 13.906 | 1.617 | 1.980 | 47.33 | 48.45 | 48.45 | 3 |
| 10,000 | precision | 576.493 | 217.070 | 276.675 | 47.70 | 112.82 | 109.61 | 82 |
| 10,000 | recall | 558.980 | 216.422 | 281.394 | 47.43 | 118.26 | 109.30 | 83 |
| 100,000 | budget | 21.948 | 1.741 | 2.482 | 141.33 | 142.43 | 142.43 | 4 |
| 100,000 | precision | 6348.518 | 6688.231 | 8056.678 | 141.29 | 840.53 | 731.26 | 944 |
| 100,000 | recall | 17246.237 | 6851.987 | 8702.513 | 141.59 | 839.18 | 737.91 | 1503 |

Fixture store seconds, same row order: 0.135, 0.135, 0.137, 1.467, 1.547, 1.480, 20.965, 25.238, 52.163. Variation shows host conditions are not controlled: do not infer that recall configuration alone explains its slower cold run. Per-mode processes avoid inherited caches, not all environmental variation.

A separate 10,000-atom warm precision cProfile call took 0.247s (profiling overhead included). get_atoms_by_agent cumulative 0.220s; _row_to_atom cumulative 0.173s, 10,005 calls (10,000 corpus plus five reinforced results); json.loads cumulative 0.084s, 20,010 calls. Cumulative times overlap, do not add them. This identifies hydration/deserialization as a measured hotspot for this sparse-query fixture, not a universal bottleneck. Source confirms non-budget modes materialize the whole owner's corpus even with semantic/BM25 cache hits.

## Direct dense encoding is a separate path

Fresh processes, TfidfProvider.fit followed by encode, documents `token{i:05d} shared context`, same sampling method. No SDK recall, model or graph:

| Batch | Shape / dtype | Output MiB | Fit ms | Encode ms | Before / sampled peak / after MiB |
|---|---|---:|---:|---:|---|
| 1,000 | 1000×1002 / float64 | 7.645 | 9.837 | 11.440 | 36.48 / 44.33 / 44.33 |
| 10,000 | 10000×5000 / float64 | 381.470 | 74.092 | 263.947 | 41.88 / 423.53 / 423.53 |

100,000×5000×8 bytes would be 4,000,000,000 bytes (about 3,814.7 MiB) for output alone: arithmetic projection, **not a measured batch**. Approximately 3.7GiB physical memory was available during this diagnostic, so that batch was not attempted. Normal TF-IDF search uses sparse postings; its small final-candidate reranking does not encode the entire corpus. Dense semantic backends and graph-bearing corpora remain unmeasured here. Do not close the dense-backend cost row or claim a 4GB normal-recall allocation.

## Reproduction

Run the following Python code with the project virtual environment from the repository root. Keep HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1. This is a one-off diagnostic harness, not a new production interface or pytest test seam. Execute each child sequentially to avoid benchmark workers competing with each other.

```python
import subprocess, sys
worker = r'''
import sys, time, json, threading
from vibe_memory import VibeMemory
from experiments.chinese_scale_benchmark import working_set_mb
from experiments.scale_visibility_benchmark import _summary
n, mode = int(sys.argv[1]), sys.argv[2]
m = VibeMemory(agent_id='mode-cost-diagnostic', db_path=':memory:', embedding_backend='tfidf')
old = m.store('连接池耗尽导致接口超时，释放连接后恢复正常', session_id='old', auto_build_edges=False, auto_episode=False)
for i in range(n-1):
    m.store(f'日常维护记录编号{i}，桌面主题颜色和背景图片设置完成', session_id='background', auto_build_edges=False, auto_episode=False)
rss = [working_set_mb()]; stop = threading.Event()
def sample():
    while not stop.wait(.005): rss.append(working_set_mb())
t = threading.Thread(target=sample, daemon=True); t.start()
times, hits, failures, counts = [], 0, [], []
try:
    for _ in range(11):
        start = time.perf_counter()
        r = m.recall('接口超时如何修复连接池', mode=mode, top_k=5)
        times.append((time.perf_counter()-start)*1000)
        hits += old.id in {a.id for a in r['atoms']}
        failures.extend(r['failures']); counts.append(len(r['atoms']))
    rss.append(working_set_mb())
finally:
    stop.set(); t.join(); m.storage.conn.close()
print(json.dumps(dict(n=n, mode=mode, cold_ms=times[0], warm_ms=_summary(times[1:]), before=rss[0], peak=max(rss), after=rss[-1], rss_samples=len(rss), hits=hits, failures=failures, counts=counts)))
'''
for n in (1000, 10000, 100000):
    for mode in ('budget', 'precision', 'recall'):
        p = subprocess.run([sys.executable, '-c', worker, str(n), mode], text=True, capture_output=True, encoding='utf-8', timeout=600)
        print(p.stdout)
        if p.returncode:
            raise RuntimeError(p.stderr)
```

Dense reproduction: create the above literal token documents, call TfidfProvider.fit(documents) outside encode timing, retain `vectors = provider.encode(documents)` until taking the final RSS sample, and report vectors.shape/dtype/nbytes. Profile reproduction: prepare 10,000 SDK fixture atoms as above, warm precision once, then enable cProfile around one more recall and sort pstats by cumulative time. These diagnostic variations do not add assertions to existing tests.

## Repair direction and gates

Prioritize avoiding repeated full object hydration/JSON decoding, not replacing precision/recall with budget. Any index/snapshot design must preserve scope, active/warm filtering, ranking inputs, temporal/graph behavior, deletion, updates and visibility of other-connection commits. Caching mutable atoms without invalidation is not an acceptable fix. First verify an existing public store/recall mutation/visibility test boundary; compare result IDs/order and degradation behavior before measuring gains.

Keep both original performance rows open. Follow-up needs selective and high-match queries, meaningful graph density, dense local-model measurements, cold/warm/write-invalidated paths, disk databases and repeated runs with controlled conditions. No paid model request occurred, but CPU/RAM time and electricity are not zero cost. This run does not establish user onboarding time or a hardware/currency price.

## Current baseline repeat — 2026-10-03

HEAD remains `53cfcb649a547d9f23767c8c6eca72b7661e2af9`; the working tree includes unpublished MCP/settings/tests and documentation changes. This repeat made **no retrieval, SDK, MCP or test changes**. Windows, Python 3.12.14, SQLite 3.53.1; HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1, explicitly selected TF-IDF. These flags do not constitute system-wide network isolation. No cloud inference, downloaded model, real user database, client configuration change, commit or push.

Reused the reproduction block above without introducing a new production API or benchmark framework. All nine fresh child processes ran sequentially with the same synthetic fixture, in-memory SQLite, owner, query, top_k=5, no edges/automatic edges/Episode, one cold and ten warm SDK calls including reinforcement. Preparation/startup are excluded from latency. The RSS sampler, units, interpolation and sample-size limitations described above still apply. Fixture store time was not measured in this repeat.

| Atoms | Mode | Cold ms | Warm p50 ms | Warm p95 ms | Warm p99 ms | Before MiB | Sampled peak MiB | After MiB | RSS samples |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | budget | 7.246 | 1.361 | 1.722 | 1.827 | 37.59 | 38.79 | 38.79 | 3 |
| 1,000 | precision | 37.378 | 9.582 | 11.367 | 12.313 | 37.89 | 46.11 | 46.11 | 9 |
| 1,000 | recall | 38.351 | 9.280 | 11.497 | 12.626 | 38.19 | 46.38 | 46.38 | 9 |
| 10,000 | budget | 8.035 | 1.474 | 1.708 | 1.739 | 47.12 | 48.25 | 48.25 | 3 |
| 10,000 | precision | 358.491 | 110.966 | 115.455 | 116.041 | 46.96 | 110.09 | 110.09 | 50 |
| 10,000 | recall | 360.563 | 108.448 | 113.315 | 114.227 | 47.01 | 109.78 | 109.12 | 50 |
| 100,000 | budget | 12.209 | 1.444 | 1.732 | 1.784 | 141.34 | 142.47 | 142.47 | 4 |
| 100,000 | precision | 3999.140 | 1438.982 | 1488.131 | 1508.514 | 141.31 | 833.64 | 735.96 | 475 |
| 100,000 | recall | 4053.069 | 1457.209 | 1475.010 | 1475.660 | 141.04 | 852.76 | 734.79 | 483 |

Baseline anchor hits: 11/11 in each cell, 99/99 total; failures empty. Budget consistently returned one atom, precision/recall five. This is one assistant-authored sparse-query diagnostic, not an independent quality benchmark. The old 8.06/8.70-second warm p95 and current 1.49/1.48-second observations remain separate historical measurements: uncontrolled host conditions and no retrieval implementation change mean **no optimization speedup can be claimed**. Do not use these small-sample percentiles as an SLA or a hard pytest time threshold.

### Main-thread profiling and rejected instrumentation

The first warm profiling attempt included the background RSS sampler and produced internally inconsistent cumulative times with sampling functions present. Its phase attribution was rejected, not averaged into the results. The nine non-profiled baseline cells above are retained. Subsequently removed the RSS sampler/thread entirely from the worker and profiled only the recall call: two fresh 10,000-atom precision runs, each one unprofiled cold call then one profiled warm call. A separate fresh process profiled its cold call, then made one unprofiled warm call. All six calls hit the anchor, returned five atoms and reported no failures. cProfile adds overhead; profiled timings are not interchangeable with the baseline table.

| Measurement | Warm run 1 | Warm run 2 | Cold run |
|---|---:|---:|---:|
| Profile total seconds | 0.174576 | 0.169601 | 0.710404 |
| Profiled wall ms | 174.620 | 169.645 | 714.332 |
| get_atoms_by_agent calls / cumulative seconds | 1 / 0.156996 | 1 / 0.152194 | 1 / 0.143878 |
| _row_to_atom calls / cumulative seconds | 10,005 / 0.125072 | 10,005 / 0.119801 | 10,005 / 0.107574 |
| json.loads calls / cumulative seconds | 20,010 / 0.059964 | 20,010 / 0.058178 | 20,010 / 0.045658 |
| reinforce_atoms calls / cumulative seconds | 1 / 0.002301 | 1 / 0.002295 | 1 / 0.002278 |
| TF-IDF provider.fit calls / cumulative seconds | 0 / absent | 0 / absent | 1 / 0.364098 |
| BM25Strategy.fit calls / cumulative seconds | 0 / absent | 0 / absent | 1 / 0.171396 |

Warm get_atoms_by_agent accounts for approximately 90% of each profile total and includes its row-conversion/JSON children: cumulative rows must **not be added together**. Each profile converts the full 10,000-row corpus plus five reinforced results and decodes tags/scope twice per row; `_row_to_atom` does not deserialize embedding vectors. Cold provider.fit contains TFIDFVectorizer.fit (one call, 0.363925 seconds), not an additional independent cost to sum. Cold index construction is material; warm index reconstruction and reinforcement are not the dominant measured costs for this fixture.

Source pointers: `vibe_memory/retrieval/ppr.py` non-budget stage 0 calls `get_atoms_by_agent` before TF-IDF/BM25 cache checks; `vibe_memory/storage/sqlite_store.py:253` selects/fetches all owner rows and `:846` converts them. This supports prioritizing repeated full hydration, not claiming SQL alone or JSON alone explains all latency. RSS is process-wide and combines the database, sparse indexes, hydrated atoms, retained Python allocations and other state; no separate memory attribution was performed. Avoid promising that a hydration fix removes the entire 834/853 MiB peak. Dense backends, graphs, disk/concurrent writes, selective versus high-match queries, independent relevance and end-to-end host costs remain unmeasured here. The direct dense-encoding subsection above was **not rerun**.

### Next repair boundary, not yet implemented

1. Confirm the existing public SDK mutation/visibility test seam, using only temporary synthetic databases. Before optimization, capture output IDs/order, current metadata, scope/lifecycle/tenant/agent filtering, graph/temporal behavior and degradation; cover store, content/metadata update, deletion, repeated reinforcement and commits from a second connection. Define measurable structural reduction in repeated hydration, not a machine-dependent timing assertion.
2. Make the smallest change supported by those tests to avoid repeated full atom conversion. Investigate lightweight retrieval data plus selected-record hydration/reuse of existing indexes, without assuming a mutable full-object cache is safe or adding a speculative cache framework. Fresh weights/access/lifecycle/scope and cross-connection visibility must remain correct. Preserve precision/recall candidate semantics; budget substitution or truncating the corpus is not the fix.
3. Rerun the same baseline and non-sampling profiler, then mutation/visibility and full regressions. Report cold/warm/write-invalidated performance separately and only attribute a gain under comparable conditions. Follow with disk, graph and local dense measurements before closing the original performance review rows.

This turn produced diagnostics/documentation only. The prior 883-test regression belongs to the short-ID repair; no new full regression was run or claimed here. Original review counts remain 44 closed / 9 excluded / 12 open; Start Plan and real ZCode host acceptance remain deferred.

## Sparse retrieval projection implemented — 2026-10-03 follow-up

This section supersedes the previous turn's **not yet implemented** status, not its measurements. The human approved tests through existing public SDK store/recall/update/forget/history/link and storage interfaces, synthetic temporary databases only, no private-method tests, direct SQL assertions or latency hard thresholds. No cloud calls, real database migration, new dependency, MCP tool/field/default change, client configuration, commit or push.

### Minimal implementation and resource-contract red/green

`VibeStorage.get_recall_documents` reads all active/warm rows for the current tenant/agent, preserving created_at ordering, with only id/version/content/created_at. TF-IDF non-budget recall uses these immutable lightweight records for the complete sparse corpus, existing TF-IDF/BM25 keys and temporal ranking; full atoms are loaded on demand for seeds, fused candidates and returned evidence. Each loaded full atom is checked for owner and active/warm lifecycle. The per-call map is discarded, not a persistent mutable-atom cache. Fresh projection/selected-record reads preserve mutations between calls without inventing an invalidation framework. Budget, non-TF-IDF/dense backends and fallback_vector_topk retain their prior loading paths. SDK signatures, ranking formula, corpus coverage, reinforcement and existing index-cache rules are unchanged.

Production diff is two files, 44 added / 7 removed lines. There is still an O(N) projection, temporal scan and existing index retention/construction cost. On-demand SQL reads are not a new transaction snapshot: overlapping commits during one query are not claimed to provide globally atomic answer consistency. Selected objects are current when loaded; calls after completed commits are covered. Dense retention/encoding, disk/large-graph workloads, high-match queries, degraded strategies and historical data repairs are not universally certified by this sparse fixture.

Added `tests/test_retrieval_projection.py` through the approved interfaces. First two allocation-contract cases failed at 5,174,881 / 5,174,721 bytes for 3,000-atom warm precision/recall. The 3 MiB contract is a deliberately generous **Python traced temporary-allocation budget for this exact fixture**, not process RSS, latency or a product-wide memory cap. After projection both pass; separate fresh diagnostic processes measured 1,508,104 bytes each. Tracemalloc overhead is not mixed into latency/RSS baselines. Further public-interface safeguards cover same-instance/second-connection update, fresh text/summary/tags/scope/confidence/decay/weight, reinforcement counters, caller mutation of returned objects, subsequent store/forget/history, tenant/agent isolation, active/warm versus cold/archived, full context and graph-trace endpoints. Trace identity is not causal direction verification.

Initial combined run: 30 passed / 18 setup errors in 30.40s, caused by Windows WinError 5 on the default pytest temporary directory, not failing product assertions. Did not delete or change that directory. Reran in a new unique repository-local temporary root: **102 passed / 11.57s**, including all eight new cases plus SDK, causal bridge, scope, failure-observability and WAL regression modules. Full regression result is recorded below when complete; no new coverage or hosted CI result is claimed.

Final regression: **891 passed / 122.54s** on Windows/Python 3.12.14, rich environment including existing cached optional-model tests; **102 passed / 5.38s** for the same relevant subset on the existing isolated Python 3.10.11 / SQLite 3.40.1 environment. Verified that the 3.10 run imported this checkout before its installed-package copy. Both used model-hub offline flags and fresh unique pytest roots, not proof of universal network isolation. No new coverage, Python 3.11/3.13 or hosted matrix run. The earlier 883-pass short-ID result remains historical.

### Controlled 10,000-atom old/new comparison

Used separate fresh sequential child processes with the same existing reproduction fixture/query/modes/top_k/one-cold-ten-warm calls/RSS sampler. The baseline injects the unmodified recall function obtained from `git show 53cfcb649a547d9f23767c8c6eca72b7661e2af9:vibe_memory/retrieval/ppr.py` into the current SDK **in that diagnostic child only**; no checkout file changes or real data. Other SDK/storage behavior stays current. Since retrieval/ppr.py had no preexisting worktree change before this batch, this isolates this retrieval change rather than older MCP fixes. Fixtures use deterministic UUID(int=1,2,...) and SDK store timestamps starting 2026-10-03 12:00 with successive microseconds, so IDs and created_at ordering match between children. These are synthetic clock/random boundary controls; reinforcement remains real. This is not a new production mode or retained test mock.

An initial two-process trial with uncontrolled UUID/time values produced a result-order mismatch and was rejected as an equality comparison. It is not counted as validated improvement/equality; all four fixed-fixture pairs below subsequently matched full result IDs **and order on each of the 11 calls**. Each child hit the anchor 11/11, returned five and had no failures: 88 calls total in the accepted paired comparison. Machine background load remains uncontrolled and pairs always ran baseline first; small samples, one query and two repeats do not establish a universal speedup or SLA.

| Mode / repeat | Baseline cold ms | Projection cold ms | Baseline warm p50 / p95 ms | Projection warm p50 / p95 ms | Baseline / projection sampled peak MiB |
|---|---:|---:|---|---|---|
| precision / 1 | 374.069 | 292.095 | 111.941 / 118.762 | 20.509 / 33.818 | 110.27 / 110.82 |
| precision / 2 | 384.730 | 286.210 | 116.388 / 120.019 | 20.940 / 33.287 | 110.08 / 110.63 |
| recall / 1 | 372.589 | 304.626 | 112.628 / 120.900 | 21.605 / 32.623 | 110.22 / 111.21 |
| recall / 2 | 371.659 | 285.419 | 110.391 / 117.868 | 20.242 / 32.424 | 111.21 / 110.09 |

Warm p95 decreased approximately 71.5–73.0% in these pairs. Process peaks at 10k did **not** consistently decrease; index construction/retention remains, unlike the separately measured warm temporary Python allocation reduction. Do not relabel all retained RSS as atom hydration.

### Same original nine-cell harness after implementation

Re-executed the unchanged reproduction block above, including its ordinary random IDs and real store times. No paired ID/order equality claim is made for this table versus the earlier independently generated fixtures; the controlled comparison above supplies that bounded evidence. All nine cells again hit the anchor 11/11, 99/99 total, failures empty, budget one result versus precision/recall five. One cold/ten warm calls, no graph/dense model, in-memory database and sampling limitations remain unchanged.

| Atoms | Mode | Cold ms | Warm p50 ms | Warm p95 ms | Warm p99 ms | Before MiB | Sampled peak MiB | After MiB | RSS samples |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | budget | 9.485 | 1.444 | 1.796 | 1.922 | 37.86 | 39.07 | 39.07 | 3 |
| 1,000 | precision | 29.696 | 2.281 | 4.832 | 6.007 | 37.80 | 44.91 | 44.91 | 5 |
| 1,000 | recall | 30.754 | 2.170 | 4.081 | 5.110 | 37.82 | 44.89 | 44.89 | 4 |
| 10,000 | budget | 8.495 | 1.442 | 1.863 | 2.016 | 46.88 | 48.00 | 48.00 | 3 |
| 10,000 | precision | 288.684 | 20.980 | 31.235 | 31.412 | 47.10 | 110.20 | 110.20 | 23 |
| 10,000 | recall | 288.951 | 20.576 | 33.976 | 34.584 | 47.35 | 111.09 | 109.86 | 23 |
| 100,000 | budget | 12.661 | 1.401 | 1.760 | 1.893 | 141.29 | 142.54 | 142.54 | 4 |
| 100,000 | precision | 3011.750 | 371.583 | 440.173 | 444.792 | 141.32 | 736.03 | 732.36 | 203 |
| 100,000 | recall | 3025.799 | 367.788 | 421.262 | 424.524 | 140.86 | 737.75 | 734.08 | 204 |

100k observations now show warm p95 0.440/0.421 seconds, cold approximately 3.01/3.03 seconds and sampled peaks 736.03/737.75 MiB. Earlier same-day 1.488/1.475 seconds and 833.64/852.76 MiB are historical observations, not a controlled 100k causal estimate. After-call RSS remains approximately 732/734 MiB: retained-index memory and cold construction are still important unfinished costs. No budget substitution, truncated precision/recall corpus or independent relevance claim.

### Non-sampling warm profile after implementation

Fresh 10k precision process, one unprofiled warm-up then one main-thread profiled recall, no RSS sampler or tracemalloc. Profile total 0.044133 seconds, wall 46.447ms including profiler overhead. `get_recall_documents` one call / 0.031458 cumulative seconds; `_row_to_atom` **10** calls / 0.000556 cumulative seconds; `json.loads` **20** calls / 0.000425 cumulative seconds; `reinforce_atoms` one call / 0.002256 cumulative seconds. No fit/get_atoms_by_agent call in this profile. Full atom conversion/JSON counts fell from the earlier 10,005/20,010 to 10/20 on this fixture; remaining full-corpus projection is now a measured hotspot. Cumulative rows overlap and must not be summed. The two profile-flow calls and four separate allocation-flow calls all hit the anchor, returned five and had no failures.

### Remaining gates

Keep original review counts **44 closed / 9 excluded / 12 open** and both broad performance rows open: this implements one sparse-hydration subtask, not the dense, disk, large-graph, high-match or overall latency/memory work package. Next measure cold/index retention, disk and write-invalidated paths with useful queries before adding more caching. Start Plan and ZCode host E2E/authorization/usage remain deferred. No model replacement is justified by this structural optimization.

## Disk / mutation / retained allocation follow-up — 2026-10-03

Diagnostics only this turn: no production/test-source change, new dependency/model, user data/client configuration change or commit/push. Reused public SDK/storage and existing `_summary` / `working_set_mb` helpers in disposable Python child processes, not a new benchmark framework. The previous 891-pass full regression remains historical; reran the existing eight projection cases: **8 passed / 1.67s**, Python3.12.14, fresh unique pytest root and model-hub offline flags. No new full regression/coverage/host E2E. The quality failure below is not covered by those passing tests and is explicitly unresolved.

### Disk method and observed results

Four sequential fresh child processes, each a new retained synthetic file database, n=10,000, TF-IDF precision/recall top_k=5, no graph/auto edges/Episode. Existing SDK `journal_mode='wal'` option used only for the temporary fixture; observed WAL, synchronous=2 (FULL), page_size=4096, cache_size=-2000, wal_autocheckpoint=1000. This does not change defaults or cover DELETE journal mode. Cold means first query without an instance index, **not** cleared OS/disk caches. There is no concurrent writer stress in this probe: a second independent connection commits each operation before the reader's next call.

Anchor: `连接池耗尽导致接口超时，释放连接后恢复正常`. Selective backgrounds: `日常维护记录编号{i}，桌面主题颜色和背景图片设置完成`; all-match backgrounds: `接口超时连接池维护记录编号{i}，连接资源配置记录`, i=0..9998. Initial query `接口超时如何修复连接池`. Each of five phases has one first call and ten repeated warm calls, including SDK reinforcement, total **220 disk calls**. Latency excludes fixture preparation and mutation time, includes recall reinforcement; sampled before/after working set is **not peak RSS**. No profiling or tracemalloc in these latency runs. Uncontrolled host load, one repetition, one query per phase and ten warm samples: no production SLA or controlled journal comparison.

Phase order: initial; second connection updates anchor content to `cometkey 接口超时由连接池耗尽导致，释放连接修复`, tags=['updated'], scope={'service':'orders'}, query `cometkey 接口超时修复`; metadata-only update confidence=0.6 and scope={'service':'orders','environment':'production'}, same query; second connection stores `pulsarkey 接口超时恢复方案，专用测试记录` in session 'added', query identical to that text; second connection forgets that full ID, repeats that query and checks reader history('added') empty. Unique markers are synthetic **visibility controls**, not a user-facing quality fix. Every call returned five and reported no degradation. Assertions verify expected updated/stored IDs in the middle phases, deleted ID absent in every final call and deleted session history empty.

| Workload / mode | Phase | First ms | Warm p50 ms | Warm p95 ms | Warm p99 ms | Target hit or deletion checks |
|---|---|---:|---:|---:|---:|---|
| selective / precision | initial | 325.496 | 23.229 | 36.033 | 36.373 | anchor 11/11 |
| selective / precision | content update | 336.270 | 23.840 | 35.187 | 35.832 | updated 11/11 |
| selective / precision | metadata update | 311.096 | 24.029 | 36.579 | 37.435 | updated 11/11 |
| selective / precision | store | 315.140 | 23.699 | 37.694 | 37.868 | new 11/11 |
| selective / precision | forget | 312.032 | 24.255 | 35.307 | 35.728 | absent 11/11 |
| selective / recall | initial | 316.407 | 23.435 | 36.773 | 36.870 | anchor 11/11 |
| selective / recall | content update | 341.406 | 23.920 | 35.281 | 35.318 | updated 11/11 |
| selective / recall | metadata update | 332.372 | 25.614 | 39.261 | 39.886 | updated 11/11 |
| selective / recall | store | 326.986 | 24.370 | 40.180 | 41.461 | new 11/11 |
| selective / recall | forget | 323.882 | 25.232 | 40.487 | 41.691 | absent 11/11 |
| all-match / precision | initial | 317.749 | 44.226 | 52.344 | 52.479 | anchor **0/11** |
| all-match / precision | content update | 304.319 | 37.458 | 48.321 | 48.708 | updated 11/11 |
| all-match / precision | metadata update | 306.286 | 38.013 | 49.614 | 51.369 | updated 11/11 |
| all-match / precision | store | 307.723 | 37.030 | 50.048 | 50.488 | new 11/11 |
| all-match / precision | forget | 321.278 | 38.526 | 50.185 | 50.843 | absent 11/11 |
| all-match / recall | initial | 331.816 | 44.544 | 56.426 | 56.446 | anchor **0/11** |
| all-match / recall | content update | 305.403 | 36.923 | 48.382 | 48.685 | updated 11/11 |
| all-match / recall | metadata update | 291.816 | 36.897 | 47.205 | 47.852 | updated 11/11 |
| all-match / recall | store | 303.154 | 37.891 | 49.213 | 50.250 | new 11/11 |
| all-match / recall | forget | 302.097 | 38.331 | 50.337 | 50.551 | absent 11/11 |

Selective initial anchors 22/22, all-match initial anchors 0/22. Marked update/store visibility 132/132 and deletion absence 44/44 are distinct checks, **not** 220/220 quality success. Observed per-phase after-call process working set: selective approximately 102–108 MiB, all-match 93–100 MiB. Background-store preparation seconds in row-group order: 12.177, 12.237, 12.707, 12.715, excluding anchor/SDK initialization; not an onboarding cost estimate.

Retained synthetic evidence (each path contains only this turn's new fixture):

- `vibe-disk-cost-20261003-qljbw37f/memory.db` selective/precision.
- `vibe-disk-cost-20261003-qqybdcnu/memory.db` selective/recall.
- `vibe-disk-cost-20261003-g5hrk75l/memory.db` all-match/precision.
- `vibe-disk-cost-20261003-i30_5u2h/memory.db` all-match/recall.

Paths are relative to this repository, no real databases were opened. Main database bytes while open: 8,986,624 / 9,027,584 / 8,634,368 / 8,626,176; WAL bytes 4,626,792 / 5,084,112 / 4,297,192 / 4,268,352, SHM 32,768 each. These are snapshots before closing both connections, not retained final file sizes or disk capacity guarantees. No deletion/cleanup of old or new evidence.

### Three hypotheses and separate probes

Ranked after the disk baseline: (1) metadata version changes unnecessarily rebuild sparse indexes even when content is unchanged; (2) retained traced allocations largely originate in the sparse indexes; (3) all-match omission is either a prior ranking problem or a projection regression. Each was tested independently, without mixing profilers into the latency table.

**Metadata rebuild:** fresh 10k selective in-memory process, warm once, profile unchanged recall, update only anchor confidence to 0.6 through SDK, profile next recall with identical query/top_k. Unchanged profile total0.039500s, no fit. Metadata profile total0.587851s with one TF-IDF provider.fit0.370906s (contains vectorizer.fit0.370802s) and one BM25 fit0.173507s; overlapping cumulative values must not be added twice. Both profiles hit anchor with no failures. Source uses `(id, version)` corpus keys and SDK update increments version even for confidence/scope changes. This supports a **future content-sensitive index identity**, not a fix already applied or a reason to cache mutable metadata. Fresh metadata/owner/lifecycle reads must remain intact.

**Retained allocation:** separate fresh 10k selective process, create fixture before tracemalloc starts, trace only first recall, discard result and gc.collect before snapshot; no latency attribution from this instrumented run. Current traced36.667MiB, traced peak54.203MiB; allocation origins TF-IDF file20,302,676 bytes (19.362MiB), strategies file16,465,632 (15.703MiB), storage775,894, PPR638,240, regex222,402, then smaller origins. Index-related files sum35.065MiB, approximately95.6% of this **new retained traced allocation**, not 95.6% of all process memory or exclusively proven live index ownership. Source allocations can be referenced by caches; SQLite/native/preexisting allocations are not exhaustively attributed. RSS before46.89MiB, with tracer/snapshot249.33MiB: tracing itself has large overhead, so do not compare that RSS to normal 100MiB runs or label it a leak. One snapshot after GC is not a growth/leak test.

**All-match old/new:** four fresh in-memory children (baseline/projection × precision/recall), same10k fixture, deterministic UUIDs and SDK store times from 2026-10-03 12:00 plus successive microseconds, two calls each. Baseline recall source from HEAD53cfcb6 injected only into diagnostic child SDK as in the preceding controlled comparison. All **eight** omit anchor, no failures; each pair returns identical full IDs, order and content (last five background records). Projection is not the cause for this fixed case. This assistant-authored expectation is not independently judged or a public benchmark score, but it is useful resolution-evidence omission evidence that must not be hidden behind empty failures.

Minimization through public SDK at n=2/5/6/10/100, both modes, top_k5: n2/5 include anchor, n6/10/100 omit it. Six is the minimum among these cases and the first corpus exceeding top_k. A direct public-provider stage probe on the six literal documents puts anchor index0 at **TF-IDF rank6 (0.323265 versus backgrounds0.507265)** and **BM25 rank1 (0.409850 versus backgrounds0.400824)**. SDK precision top_k5 omits it, top_k6 includes it. This localizes a lexical/similarity ranking disagreement and final cutoff, not simply an absent corpus record. Increasing top_k for six records is a diagnostic, not a scalable remedy or authorization to change defaults. Fusion-versus-rerank preservation still needs targeted evaluation before tuning.

### Reproducible red-capable quality signal

Run with project Python, repository cwd and model-hub offline flags. This diagnostic deliberately exits1 today (observed AssertionError in0.32s), exposing the unresolved expectation; it is **not** a newly added failing pytest case or a completed TDD repair. Same SDK seam already approved; fixture is in-memory, no model download or user data.

```python
from vibe_memory import VibeMemory
m = VibeMemory(agent_id='all-match-minimum', embedding_backend='tfidf')
try:
    anchor = m.store('连接池耗尽导致接口超时，释放连接后恢复正常',
                     session_id='anchor', auto_build_edges=False, auto_episode=False)
    for i in range(5):
        m.store(f'接口超时连接池维护记录编号{i}，连接资源配置记录',
                session_id='background', auto_build_edges=False, auto_episode=False)
    result = m.recall('接口超时如何修复连接池', mode='precision', top_k=5)
    assert result['failures'] == []
    assert anchor.id in {atom.id for atom in result['atoms']}, 'resolution evidence missing'
finally:
    m.storage.conn.close()
```

### Next priorities and unresolved scope

Prioritize memory quality over further latency polishing: evaluate fusion/rerank preservation under near-duplicate operational distractors, first with this red-capable SDK signal then diverse positives/negatives, negation, time/scope/contradiction and existing guard cases. Do not add a fix-word heuristic, global weight tweak, larger top_k, corpus truncation or model replacement based only on one artificial query. If a safe production repair cannot be justified, keep it experimental and documented. Retain this diagnosis under the existing quality/high-match work package, not as an automatic arithmetic increment to the original review count.

Second: evaluate content-sensitive TF-IDF/BM25 index keys to avoid metadata-only rebuild while preserving content/store/delete/order invalidation, separate connections, owner and lifecycle visibility, budget/dense compatibility and real degradation states. Third: quantify index retention and representation alternatives at scale before changing postings/caches; graph/dense/DELETE journal, 100k disk, overlapping writes, independent relevance and real-host/cost remain open. Keep original44/9/12 and both broad performance rows open. Start Plan/host E2E stays deferred. No production repair this turn; prior implementation remains as recorded above.

## Resolution evidence ablations — 2026-10-03

Reproducible entry: `.venv/Scripts/python.exe -m experiments.resolution_evidence_probe --json results/resolution_evidence_probe.json`. Final saved report contains **96 SDK calls**: four synthetic cases × sizes6/100 × precision/recall × six arms. Each uses a fresh in-memory TF-IDF SDK, no automatic edges/Episode, Top-5 unchanged. No cloud calls, real DB, host configuration, ranking default changes or new dependencies. Earlier exploratory executions are not additional independent samples of this final report.

| Arm | Resolution hit groups /4 | Newly included negative groups /12 |
|---|---:|---:|
| Baseline | 0 | 0 |
| No final similarity rerank | 0 | 0 |
| No graph fusion vote | 0 | 0 |
| No graph vote + no rerank | 2 | 6 |
| Max-normalized RRF before existing rerank | 0 | 0 |
| Existing one-slot BM25 report-side helper | 4 | 12 |

All96 have empty failure events; this does **not** mean quality passes. The six-row resolution case has BM25 evidence rank1, semantic/graph absent and fused rank6; bypassing the final rerank alone does not rescue it. With100 rows, removing both graph vote and rerank rescues the resolution in both modes but also includes all three negative targets in both modes. Correlated route votes plus final similarity are involved, but suppressing the graph vote is not established as a safe general fix; real graph-supported evidence was not tested here.

The reused `lexical_slot` helper keeps first four results and reserves the fifth for a positive, absent BM25 winner. It runs **after SDK scope boost in the report only**, not in production. Its twelve new negative hits are the three cases (explicitly unsuccessful release, old-version release, billing-service evidence while querying orders) × two sizes × two modes. Existing SDK scope is a boost, not an exclusion guarantee; the unsafe report-side addition can bypass even that ordering. A BM25 winner is lexical support, not evidence that the action succeeded or remains applicable.

Fixture iteration is disclosed: initial verbose negation/obsolete suffixes did not activate the slot intervention. Shorter negated/old-version statements were then used to construct exercised counterexamples. They are **development diagnostics**, not fresh held-out or independently labeled examples. Background maintenance rows are not all independently judged harmful; negative counts refer only to the explicitly labeled target per negative case. No actual dates, contradictory revision edges, dense models, final answers, latency/RSS or real-host acceptance were measured. Anonymous ordinal IDs are reported instead of random UUIDs. No timing fields are mixed into this deterministic report.

Existing regression command: `python -m pytest tests/test_retrieval_projection.py tests/test_rrf_fusion.py tests/test_longmemeval_lexical_slot_probe.py -q --basetemp <new-unique-directory>`: **17 passed /1.77s**, Python3.12.14 with model-hub offline flags. No new pytest cases were written: the experiment-report seam confirmation was requested but not yet received at record time. The earlier SDK six-row red signal remains unresolved; these regression passes are not a green repair or independent ranking-quality certificate. The instrumentation is scoped by context managers in the experiment only, with no production debug logs.

Decision: reject all tested global interventions as default repairs. Next, confirm the report-test seam and build an applicability-aware evidence-preservation experiment (success/negation, current/obsolete status and explicit service/environment), including displacement of existing relevant evidence and graph-supported controls. Do not invent a fix-word regex or assume metadata is verified truth. Only after exercised safety checks and a red→green public-seam regression should a production integration be proposed. Original44closed/9excluded/12open unchanged; metadata-only index rebuild and retained-index cost remain the following priorities. Start Plan and independent blind labels remain deferred.

## Scope-constrained evidence preservation — 2026-10-03

Run `.venv/Scripts/python.exe -m experiments.resolution_evidence_probe --applicability --json results/resolution_applicability_probe.json`. This adds an experiment-only `scoped_lexical_slot`: no query scope means no promotion; the BM25 winner must match **every provided query scope key** before using the existing one-slot helper. It does not parse successful actions, effective dates or corrections, infer a scope, change stored fields, filter original results or claim that matching metadata proves truth.

Six cases × sizes6/100 × two modes × three arms = **72 calls per report**. Cases: original unscoped repair, explicit orders/production/timeout repair, same-scope unsuccessful release, same-scope old-version repair, billing-service mismatch, and absent record scope. Missing record scope is **unknown**, so its promotion is an unsupported-risk indicator, not a proven harmful answer. Negation/old-version targets are explicit assistant-authored negative expectations, not independent labels.

| Arm | Unscoped repair /4 | Explicit-scope repair /4 | Newly included negated/obsolete groups /8 | Newly promoted scope mismatch/missing groups /8 |
|---|---:|---:|---:|---:|
| Baseline | 0 | 0 | 0 | 0 |
| Unconditional lexical slot | 4 | 4 | 8 | 8 |
| Scope-constrained slot | 0 | 4 | 8 | 0 |

All72 SDK calls have no failure events. Scope constraint stops the eight unsupported scope promotions, but **all eight same-scope negative promotions remain**; the original unscoped omission is still unresolved. Do not promote this into a completed applicability repair or require users to manually set fields for every recollection based on this evidence.

Initial displacement observations across fresh arms used random UUIDs/timestamps and showed differing tied background order; these preliminary displacement IDs are discarded. The replay now fixes SDK store UUIDs1..N, session ID and timestamps at 2026-10-03 noon plus successive microseconds. Two completed 72-call reports are byte-identical (SHA-256 comparison). Only store time/randomness boundaries are fixed; the whole runtime clock is not frozen, so this is same-day replay evidence, not future clock invariance. Returned IDs are ordinal-anonymized, and `displaced_ids` is mechanically compared to the matching baseline. Such a difference is **not** proof that the removed item was relevant; full relevant-displacement/graph controls are still open. The four-by-six earlier ablation was also re-run with fixed store boundaries into `results/resolution_evidence_fixed_probe.json` (96calls): previous aggregate results unchanged. The earlier random-boundary report is preserved as history, not an exact current-source replay artifact.

Existing projection/fusion/lexical-slot regressions **17 passed /1.66s** on Python3.12.14 with a new unique pytest directory and model-hub offline flags. No new pytest tests, full-suite run, production/source schema/ranking change, host configuration, real DB, API request or independent labels. Original44/9/12 remain. TDD requires confirmation of the new experiment-report testing seam before writing those tests; that confirmation has not been received at record time, so this remains diagnosis, not red→green implementation.

Next: confirm the report-test seam and use full candidate content plus correction/source context to distinguish successful/current evidence from unsuccessful/obsolete statements, with explicit scope as one guard rather than the relevance oracle. Reuse the existing selection-response boundary, including valid-but-wrong selections and missing/error fallback; assistant-produced selections must be labeled non-independent and cannot stand in for host-model/API cost or quality evidence. No new paid API or Start Plan attempt is authorized. If fewer verified judgments are available, leave ranking unchanged rather than invent verified metadata. Graph-supported relevant displacement, real dates and truth provenance remain necessary before proposing production integration.
