# MAC/MAG memory evidence display

The shared formatter used by SDK inject and SessionManager emits Markdown
headings with one JSON object per memory/relationship line. It returns a string,
not privileged system messages. Existing signatures, mode selection, grouping
and retrieval ranking are unchanged; free-form record Markdown has changed.
Consumers parsing the old record layout need to update.

Each non-empty injection carries an untrusted-evidence notice. Memory fields,
including summaries, tags and session IDs, are data, not instructions.
Newlines, controls and Unicode line separators remain inside JSON strings.
Quotes and instruction-like code are preserved as data, not keyword-filtered.
Retrieval priority and relationship confidence are not independent fact
verification and never grant instruction authority. High-priority grouping does
not instruct the model to override earlier conclusions.

Memory objects contain type=memory, full id, session_id, priority, summary, tags
and truncated_fields; MAC also retains its marker. MAC summaries show up to
120 characters and, with include_content=True, content up to 300 characters and
five tags. Summary-only MAC shows three tags. MAG shows up to 80 summary
characters and three tags, without content. Included fields shortened for display
are named in truncated_fields; a deliberately absent content field is not a
claim to have displayed the complete content. Relationship objects have
type=relationship, full from/to IDs, edge_label and confidence. The optional MAC
relationship map remains a subset, not an exhaustive graph.

max_tokens retains an approximate four-characters-per-token convention, not a
model tokenizer or byte limit. Serialized text, headings, separators and status
are charged to that character allowance; records are omitted whole, never cut
through JSON. Counts distinguish recalled totals from displayed and omitted
records. Mandatory notice/status can exceed extremely small budgets; then no
record is included. Empty recall retains the previous no-memories/no-signals
comment without inventing evidence.
JSON metadata and the trust notice consume space, so the same nominal budget
may deliver fewer records than the old Markdown layout. Display counts, not
recall totals, describe what was actually delivered; no answer-quality or
model-token cost benefit is implied.

This is a local formatting contract, not an HTML-sanitization promise, proof
against semantic prompt injection, a permission mechanism or a guarantee that
any host/model follows the notice. MCP uses a separate existing JSON path and
has not been changed. Model-level adversarial tests, true host validation and
fact-level citation checks remain separate work.

The approved public tests use build_injection and SDK.inject with real
temporary SDK/SQLite data, without private-method assertions, Mock SDKs,
paid model calls, real user databases or host configuration changes.
