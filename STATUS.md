# Project Status

> Last verified: 2026-09-13

Vibe Memory 0.3.0 is a beta-stage local-first agent memory library. The core SDK, SQLite storage, TF-IDF retrieval, CLI/session manager, and MCP stdio interface are covered by the current local test suite. Public benchmark and production-scale claims remain unverified.

## Verified Baseline

Chinese lexical retrieval now uses dependency-free CJK character bigrams in TF-IDF/BM25. CJK budget queries use the tenant/agent-scoped LIKE candidate fallback because unicode61 does not segment Chinese into matching bigrams; candidate hydration stays bounded but SQL scan cost increases. Budget TF-IDF zero-score padding no longer counts as semantic graph seeds. A 131-atom regression retrieves an old Chinese answer beyond the 100-candidate cutoff. On a local 5-incident/10-question document-reconstructed debugging set, Recall@5 changed: BM25 0.25→0.85, TF-IDF 0.60→0.90, two-hop budget 0.45→0.85. These assistant-authored labels/edges are not independent held-out evidence and the private corpus is not published. English synthetic v3 quality remains 0.808/0.984 (one/two hops). Large Chinese corpus latency and synonym understanding remain unverified.

External session retrieval evaluation is available via `experiments/session_evaluation.py`; see `experiments/SESSION_EVALUATION.md`. It uses query cutoffs and human relevance labels, compares empty retrieval/BM25/TF-IDF/two-hop budget, and prints IDs/metrics rather than corpus text. Only an explicitly synthetic interface smoke has run; no real corpus or Agent answer-quality evidence is available yet. Corpus snapshots and anonymized IDs must be reviewed before use. This preparatory addition does not change the core retrieval path.

PPR and recall traces now load only active edges whose two endpoints are active/warm memories in the seed agent/tenant scope. Foreign-agent, foreign-tenant and archived bridge nodes cannot influence PPR scores. Mixed-scope seeds raise ValueError; warm memories and a seed tenant different from the storage default remain supported. This avoids materializing other scopes' edges, but does not cap the current scope's graph size or SQL scanning time. The v3 quality sweep is unchanged (0.808 one hop, 0.984 two hops); this run's p95 was 8.760 / 8.719 ms, so no speedup is claimed.

Candidate expansion now caps depth at two hops, returned edge rows at `2 * candidate_limit` per hop, and frontier nodes at `candidate_limit`. A 500-neighbor regression retains the strongest causal answer within 10 candidates. The v3 quality sweep remains 0.808 for one hop and 0.984 for two hops; SQL scanning/sorting and full PPR traversal still have no strict time bound. High-fanout truncation can omit weaker paths and is not a lossless graph search.

The 2026-09-13 v3 retrieval run removes query-word leakage from graph-only answers. Budget fusion now respects connectivity-rejected semantic seeds across lexical lists. On the same v3 corpus, default one-hop/20% Recall@5 improved from 0.792 to 0.808 (p95 5.771 ms); explicit two-hop/20% reached 0.984 (p95 5.816 ms). One hop remains the default. Candidate hydration is bounded, but graph edge traversal is not a strict execution-time budget. These are synthetic regression results, not held-out production evidence. Full tests passed with a fresh `--basetemp` directory, avoiding inaccessible old Windows pytest temp files.

| Item | Result |
|------|--------|
| Platform | Windows, Python 3.12.14 |
| Test command | `python -m pytest -q` |
| Test result | **285 passed, 0 failed** |
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
