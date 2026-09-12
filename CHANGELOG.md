# Changelog

## [Unreleased]

### Fixed
- Force MCP stdio to UTF-8 so JSON-RPC responses containing Chinese edge labels work on Windows.
- Evaluate the PPR edge threshold against edge strength instead of seed-count-dependent probability mass.
- Normalize weighted PPR transitions and return dangling-node mass to the personalization seeds.
- Cache the semantic document matrix across SDK recalls and invalidate it when atom IDs/versions change.
- Count cold-start atoms with a tenant-scoped SQL `COUNT(*)` instead of hydrating every atom during recall.
- Use a sparse TF-IDF inverted index and only densify fused candidates during reranking.
- Reuse the BM25 index across recalls, with atom ID/version invalidation and bounded retention.
- Search BM25 through term postings instead of scoring every document, preserving reference scores and ordering.
- Bound `budget` recall hydration to a tenant/lifecycle-scoped storage candidate set while leaving precision and recall modes unchanged.
- Use trigger-synchronized SQLite FTS5 for whole-term budget candidates, with a `LIKE` compatibility fallback.
- Replace low-priority budget candidates with indexed one-hop causal neighbors while preserving the hard candidate limit.
- Weight the filtered graph signal in budget RRF and skip the duplicate TF-IDF rerank that suppressed graph-only answers.

### Documentation
- Add `STATUS.md` as the canonical test baseline and capability/evidence boundary.

### Added
- Add `experiments/retrieval_benchmark.py`: deterministic 1,000-atom/100-query retrieval ablation with vector, all-label PPR, and precision-label/seed-filter groups.
- Add `experiments/scale_visibility_benchmark.py`: deterministic 1k/10k/100k SDK write, recall, and post-commit visibility baseline.
- Split the scale benchmark into cold and warm recall latency using 20 deterministic queries.
- Add storage and SDK regression tests for bounded budget-recall candidates.
- Add the complete budget recall pipeline to the fixed retrieval quality ablation.
- Add an SDK regression proving a causal graph-only answer can enter Top-5 without exceeding the candidate budget.

## [0.3.0] — 2026-08-27

### Added
- Multi-strategy retrieval: BM25 + semantic + PPR graph + temporal, RRF fusion + rerank
- Memory Defense: 15 PII patterns, redact/block/warn modes
- Reflect: LLM-powered cross-memory reasoning (user-provided API key)
- Knowledge Pages: auto-generated Markdown from memories
- `vibe-init`: auto-detect and configure Claude Code/Codex/Cursor
- `vibe-http`: REST API server
- `vibe-mcp`: MCP Server (8 tools)
- LangChain adapter (`VibeMemoryLC`)
- OpenAI Agents SDK adapter (`create_vibe_tools`)
- GitHub Actions CI (Python 3.10-3.13)

### Changed
- `recall()` v3: multi-strategy with `strategies` parameter
- `store()` auto-scans for PII before storage
- SessionManager defaults to MAG injection mode
- 6 agent integration methods (up from 3)

### Fixed
- SQLite `check_same_thread=False` for multi-threaded HTTP server
- `_parse_reflection` JSON parser: greedy match for nested braces
- `pyproject.toml`: `include` moved to `[tool.setuptools.packages.find]`

## [0.2.0] — 2026-08-24

### Added
- LLM edge building: OpenAI/Anthropic/Transformers providers
- DeepSeek-v4-flash validation: 80% classification accuracy
- Agent integration: SessionManager + CLI (`vibe-session`)
- Semantic embedding: sentence-transformers auto mode + caching
- MAC/MAG dual-mode prompt injection
- Real vault integration: 100% cross-session recall

## [0.1.0] — 2026-08-21

### Added
- Core 5-layer architecture: chunking → edge building → PPR retrieval → injection → storage
- 8 edge labels: causal, revision, similar, adjacent, version, reference, lookup, influence
- PPR graph walk with 3 configurable modes (precision/recall/budget)
- Vibe Learner: online learning decay rate adjustment
- Graph partition: Session/Document/Parametric
- Louvain community detection
- Multi-tenant isolation
- Cold start: seed memory + aggressive thresholds
- GC: 4-level compression pipeline
- Incremental indexer: dual-speed queue
- Metrics: latency/throughput/hit rate/degradation tracking
- 14 experiments, 14 core modules
