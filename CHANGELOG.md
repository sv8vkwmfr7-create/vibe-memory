# Changelog

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