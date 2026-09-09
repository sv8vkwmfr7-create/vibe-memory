# Project Status

> Last verified: 2026-09-09

Vibe Memory 0.3.0 is a beta-stage local-first agent memory library. The core SDK, SQLite storage, TF-IDF retrieval, CLI/session manager, and MCP stdio interface are covered by the current local test suite. Public benchmark and production-scale claims remain unverified.

## Verified Baseline

| Item | Result |
|------|--------|
| Platform | Windows, Python 3.12.14 |
| Test command | `python -m pytest -q` |
| Test result | **275 passed, 0 failed** |
| Coverage | **74%** aggregate |
| Package version | 0.3.0 |

The reproducible local retrieval ablation (`experiments/retrieval_benchmark.py`) uses 1,000 synthetic atoms and 100 fixed queries. One Windows + Python 3.12.14 run measured: TF-IDF noise 40.00%, PPR with all labels 27.40%, and PPR with precision labels plus seed filtering 0%; p95 latency was 0.130 ms, 1.056 ms, and 0.901 ms respectively. These are synthetic regression numbers, not public-benchmark or production claims.

The SDK scale/visibility baseline (`experiments/scale_visibility_benchmark.py`) uses serial in-memory SQLite with TF-IDF, automatic edge building and Episode aggregation disabled. Budget recall hydrates at most `max(100, top_k * 20)` active/warm candidates selected through persistent SQLite FTS5, with a `LIKE` fallback when FTS5 is unavailable. The v3 baseline runs 20 deterministic recalls so cold and warm latency are explicit. At 1,000/10,000/100,000 atoms, cold recall was 5.814/4.614/12.046 ms and warm p95 was 1.926/1.804/2.182 ms; this is about 45.3%/91.9%/99.0% faster than the preceding same-machine `LIKE` candidate run. The tradeoff is lower write throughput: 10,531/11,000/9,370 ops/s versus about 19,903/20,556/19,054 previously. Sampled post-commit direct-read visibility remained 100%. This is not a concurrent, disk-backed, provider, or production workload result.

The v2 retrieval ablation now includes the complete budget pipeline. On the fixed 1,000-atom/100-query corpus it measured Precision@5 0.720, Recall@5 0.648, MRR 1.000, and 28.0% noise. FTS5 and the `LIKE` fallback produced nearly identical quality in a same-process comparison; the remaining gap comes from the bounded candidate policy, not token indexing alone.

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

- [x] Establish the real test baseline: 265 original tests, now 275 with PPR, cache, sparse retrieval, BM25, bounded candidates, and whole-term FTS coverage.
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
- [x] Add the full budget pipeline to the fixed retrieval ablation so candidate quality is visible beside latency.
- [x] Measure write/recall latency and write-after-read visibility at 1k/10k/100k atoms (`experiments/scale_visibility_benchmark.py`).
- [ ] Add concurrent, disk-backed, multi-tenant, and edge/episode load measurements.

## Current Evidence Gaps

- The reported 20% → 0% noise reduction comes from a small private experiment and is not yet a general product claim.
- LOCOMO and LongMemEval have not been run.
- The scale result is serial and in-memory with automatic edge/episode work disabled; there is no concurrent multi-tenant or production workload report.
- Real external-provider latency, cost, failure, and fallback behavior are not benchmarked.

The next milestone should improve evidence and correctness rather than add another integration surface.
