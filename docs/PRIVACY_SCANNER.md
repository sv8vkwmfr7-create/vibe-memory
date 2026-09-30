# Privacy scanner boundaries

`MemoryDefense.scan(content)` returns `(cleaned_content, violations)`. Default `redact` rewrites detected spans. `warn` returns findings without rewriting or automatic logging; `block` lets `scan_before_store`/SDK reject detected content. Findings contain original matched text: never log or publish them as safe metadata.

## False-positive repair

Generic long keys now require an explicit `api_key`/`access_key` label and separator. Card numbers require `credit_card`, `card_number`/`card_no`, 银行卡 or 信用卡 labels with a separator. A bare hash, timestamp or long order ID no longer matches solely because of length. Chinese phone numbers cannot be embedded in a longer ASCII identifier/number; numbers next to Chinese text remain detectable. Existing known API-key prefixes, credentials, email, IP, JWT and ID patterns are retained.

This trades unlabeled generic-secret/card detection for fewer destructive false positives. Do not treat an absence of findings as proof that content is safe. A standalone 11-digit order number resembling a phone may still be a false positive. The scanner is not comprehensive DLP or a validator of real phone/card/ID ownership. Custom `patterns` can add application-specific detection; exclude_patterns remains supported.

All matches use original offsets. Redaction unions overlapping intervals and replaces each union once; adjacent intervals remain separate. The marker uses the leftmost match's type (longest first for equal starts), not a claim of one exclusive classification. The findings list retains every original match and offset. This prevents nested matches from corrupting surrounding content or exposing fragments.

## Integration limits

SDK `store` scans content before persistence and default summary generation. This repair does not add scanning to explicit summaries, context fields, update, batch chunking or every adapter input. SDK store still returns an atom, not a new redaction-notification envelope; use the scanner's existing return value to review processing without logging raw matches. End-to-end user notifications and consistent write-path privacy enforcement remain open work.

Previously damaged stored content is not restored automatically. No real database migration or secret corpus evaluation was performed. Tests use synthetic strings, TF-IDF and an in-memory database; they establish the tested false-positive/overlap behavior, not independent retrieval-quality gains or complete privacy coverage.
