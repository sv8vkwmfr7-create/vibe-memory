# Repository privacy audit — 2026-10-01

## Scope and result

Source snapshot: `53cfcb649a547d9f23767c8c6eca72b7661e2af9` plus current documentation edits and the explicitly included untracked RETRIEVAL_COST_DIAGNOSTIC.md. Source repository is not shallow. Scans were read-only; no user database, global configuration, history rewrite, credential validation request, production change or push occurred.

Gitleaks **8.30.1**, official [release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), downloaded only to a private temporary directory. Windows x64 archive SHA256 `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e` matches the release checksums file; this establishes consistency with that publication, not a separate binary security audit. Default detection configuration, no baseline or project ignore file, ignore-gitleaks-allow, redact=100, decode depth 5, archive depth 3 for directory/git scans. No custom allowlist was added. Official [usage documentation](https://github.com/gitleaks/gitleaks#usage) distinguishes directory, Git and stdin sources.

| Scan | Coverage | Result |
|---|---|---|
| Current exported working-tree snapshot | 336 tracked files plus one explicit diagnostic document; ~6,347,343 scanned bytes | exit 0, zero rule findings |
| Git `--all` history patches | scanner reports 110 commits, ~6,343,779 bytes | exit 0, zero rule findings |
| All reachable file/commit object contents via stdin | 715 unique blobs and all 111 commit objects; 11,882,730 bytes including batch headers | exit 0, zero rule findings |

Git lists 111 commits, all non-merge and with file numstats. The history scanner's 110 count discrepancy was not silently treated as complete coverage: a separate `rev-list --objects --all` / `cat-file --batch-check` / `cat-file --batch` pass supplied all 715 blob and 111 commit contents to the same scanner. The object scan supports coverage of reachable file/commit contents without relying on the patch counter. Trees, unreachable objects and reflogs are not that scope. No claims about why Gitleaks reported 110.

All three redacted JSON reports contain no findings and share SHA256 `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`. They remain private temporary artifacts, not repository attachments. No matched values, credentials, author addresses or signed download URLs are copied into this document.

## Personal-information candidate review

A separate read-only heuristic pass reused the repository's existing email, CN/international-phone, CN-ID, labeled-card and IP patterns. IPs were parsed rather than accepting every dotted number. This is a narrow PII heuristic, not comprehensive DLP or ownership validation. Current texts (337 files) and all reachable blob texts (715 distinct blobs, 11,794,159 bytes) had no NUL-containing binary exclusion; decoding used UTF-8 replacement, so non-UTF8/obfuscated formats remain limitations. No assumption that the same value in multiple historical blobs represents multiple people.

Current candidate counts: 8 example-domain emails, 2 phone literals and 1 labeled card literal in an explicitly synthetic privacy regression fixture; 11 loopback and 2 unspecified bind-address occurrences. Historical blob candidates: the same 8 email/2 phone/1 card occurrences, 18 loopback and 2 unspecified address occurrences, across 13 blobs. Context confirms declared test fixtures, examples and local binding configuration. No live contact/number/credential ownership checks were performed; a synthetic label is not proof a number could never belong to someone.

Separately, commit author/committer headers contain **one unique non-example-domain mailbox**, across 222 header occurrences. It is not a detected access credential. The user explicitly chose **保留现有署名** on 2026-10-01. Preserve it; do not change local author configuration, rewrite history or force-push. Thus the statement “the entire Git repository has no personal information” is withdrawn, not certified. Public attribution is accepted by this explicit user decision, not inferred from a scanner exit code.

## Reproduction and safe handling

From an isolated audit directory, invoke the verified executable (placeholders below are paths, not values to paste literally):

```text
gitleaks dir <tracked-snapshot> --redact=100 --no-banner --no-color --ignore-gitleaks-allow --gitleaks-ignore-path <audit-dir> --report-format json --report-path <audit-dir>/current-redacted.json --max-archive-depth 3 --max-decode-depth 5 --timeout 180
gitleaks git <repository> --log-opts=--all --redact=100 --no-banner --no-color --ignore-gitleaks-allow --gitleaks-ignore-path <audit-dir> --report-format json --report-path <audit-dir>/history-redacted.json --max-archive-depth 3 --max-decode-depth 5 --timeout 180
```

Build the snapshot by copying every `git ls-files -z` working-tree file while retaining relative paths, plus explicitly selected new documents; no whole-directory copying of local databases, .env, model caches or old pytest directories. Export all reachable blob/commit object bytes using the Git batch APIs, then feed them to `gitleaks stdin` with the same redaction/report settings and decode depth 5. Never print that input, violation match strings or author emails. Gitleaks input mode does not interpret Git batch headers as file provenance; the counts establish the supplied inventory, not per-commit attribution of a hypothetical finding.

If a future scan finds a plausible real credential: keep values private, verify provenance offline, arrange revocation/rotation with the owner before any separately authorized historical cleanup, and rerun the bounded scans. Redacting source without revocation does not neutralize an exposed secret. No suspected credential was found here requiring that action.

## Limits and status

This completes the repository-wide **static audit procedure and correction of the original unsupported absence claim**, not a proof that every possible secret or personal fact is absent. Unknown formats, rule gaps, large/encoded archive details, generated secrets, ignored/untracked user files, external datasets, databases, remote forks/caches/artifacts, unreachable Git objects and reflogs are not certified. The baseline must be rerun after later content changes; this very audit document and subsequent progress notes were authored after the measured snapshot.

No new scanner hook, CI job, dependency, production API or pytest test seam is introduced. Original audit row closes with the above boundaries and accepted attribution choice; the remaining review has **44 closed, 9 excluded, 12 unclosed of 65**. All other open gates, including performance repairs, historical orphan governance, ST compatibility and adversarial memory behavior, remain separate.
