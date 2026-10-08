# Tests and coverage

## Staged checkpoint reproducibility — 2026-10-08

Tests run against a git checkout-index export, not the dirty development cwd.
Initial Windows checkout changes frozen JSON LF bytes to CRLF: 1101 pass,
5 fail, 10 skip /159.41s. Existing hash/identity assertions correctly reject
that change. Pin JSON to LF using .gitattributes, leaving hashes and cases intact.
Fresh index export: 101 related tests pass /20.04s; full actual-source Python
3.14.7 suite has 1106 pass, 10 skip /157.14s, exit0. Unique basetemp/JUnit and
offline model-hub flags used; no coverage refresh, paid inference or hosted CI
claim. This checkpoint test is not the still-pending full installed-wheel gate.
Evidence: `C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/github-checkpoint-20261008-b/`.

## Full installed attempt, fixture repair control — 2026-10-08

Current wheel installed into fresh Python 3.14.7 venv using existing dependencies
via temporary .pth; no source package at original fixture cwd. All 47 loaded
package modules from new venv; installed MCP subprocess path verified. Six CLI
--help checks and installed doctor synthetic end-to-end pass. Full suite has
1096 pass, 10 fail, 10 skip /693.79s, 170 warnings, exit1. Do not call it green.
MCP44/enhancement13/link14/doctor2 cases all pass. Ten failures depend on missing
seed/result/report-hash fixture inputs; separate fixed-input control reruns all
same ten nodes, 10 pass /4.78s, with all 33 package modules still from new venv.
Original full report remains unchanged; no tests/assertions or production edits.

Whole installed package/subprocess coverage: 4230/4865 lines, 1312/1682 branches,
combined85%. Harness pre-import causes module-not-measured warning. A full rerun
with complete frozen fixtures and pre-import-free coverage is pending. Reused
dependencies mean this is not clean/minimum-dependency acceptance. Artifacts:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/installed-full-20261008-a/README.md`.

## Current installed wheel lifecycle subset — 2026-10-08

Fresh wheel of current source; all 48 package Python files match checkout and
installed target bytes. Five unchanged public-lifecycle/full-ID/contract test
modules: 31 pass each on Python 3.10.11 /2.25s, 3.12.14 /2.22s, 3.14.7 /2.59s,
all exit0. Interpreter -I, cwd outside source, installed target prioritized,
35 loaded package modules all verified under target. No emitted ResourceWarning
with -Walways and final GC in these observed runs. Existing dependencies reused;
not full installed suite, clean/minimum-deps, MCP-subprocess or release proof.
The diagnosed constructor failure remains unrepaired pending test seam approval.
Artifact hash, commands and exact report paths:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/lifetime-wheel-20261008-a/README.md`.

## Existing adapter owner migration — 2026-10-08

Existing assertions/test names preserved while fixtures and offline smoke adopt
close/with/borrowed SDK. Same 44 cases, Python 3.14.7 with
`-Walways::ResourceWarning`: 24 unclosed-database warning text emissions before
and one after; both pass. One legacy factory compatibility case intentionally
retains hidden-SDK construction. No warning suppression or production edit.
Seven-module related source gates: Python 3.10.11 66 pass /2.70s; Python 3.12.14
66 pass /20.07s. Not full older-version or installed-wheel acceptance.
Actual Agents Runner/scripted Model and LangChain RunnableLambda smoke passes
using fresh temporary pinned framework dependencies, not cloud models. Source
import and framework target paths verified. Missing old target package files
were an environment failure, not a production bug. Evidence and install report:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/adapter-owner-migration-20261008-a/README.md`.

Full source Python 3.14.7: **1106 passed, 10 skipped, 179 warnings /326.71s**,
exit0. Whole-package/MCP-subprocess coverage: 4229/4865 lines, 1313/1682 branches,
combined85%. No excluded package modules or warning filters. Remaining unmanaged
owners still emit warnings; passing this gate does not establish memory quality
or refreshed wheel/full older-version compatibility.

## OpenAI factory borrowed SDK lifetime — 2026-10-08

User-confirmed factory memory=/existing functions/SDK close-with seams, synthetic
temporary libraries only. Borrow argument first fails once, then passes; conflict
guard first misses three ValueErrors, then four cases pass. Seven final cases
cover shared data, seven ordinary functions in the same list/order, normal and
exceptional caller closure, committed data on reopen, discarded tool lists not
closing their caller SDK, and non-default construction-option rejection.
Added normal/exception/discard cases are regression, not separate claimed reds.

Related six-module source checks: 52 pass on Python 3.10.11 /3.28s and 3.12.14
/2.72s. No full older-version or installed-wheel claim from these subsets. Tool
ASTs and returned list exactly match retained pre-edit source; earlier full-ID
and ambiguous-prefix fixes preserved. No new tool, internal mock, private test,
SQL assertion, paid model call, dependency install or real data/config edit.
Current-source full Python 3.14.7: **1106 passed, 10 skipped, 202 warnings
/222.78s**, exit0; JUnit 1116 total/zero failures/errors. Coverage includes whole
package and MCP subprocesses: 4229/4865 lines, 1313/1682 branches, combined85%.
Source/test hashes unchanged through run; no warning suppression or exclusions.
Optional framework dependencies absent in project environment; plain-function
checks are not refreshed real Agent/Runner or cloud/model-quality acceptance.
Legacy unmanaged factory callers remain a migration gap. Contract:
[ADAPTER_CONTRACTS.md](ADAPTER_CONTRACTS.md). Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/openai-lifetime-20261008-a/README.md`.

## LangChain helper lifetime seam — 2026-10-08

Four user-approved public-interface cases: repeat close/persistent save/load,
normal/exceptional contexts with caller exception propagation and visible
ResourceWarning checks, clear followed by new save/load. Close initially fails
once and context protocol twice before implementation. An output-reopen query
fixture was corrected to match that output; retrieval behavior was not widened.
Do not claim all assertions unchanged between initial red and final green.

An existing SDK warning test initially catches abandoned adapter connections
during global GC (related314.xml: 35 pass/1 fail). Pre-collection before recording
the new SDK instance's warnings isolates it; related314-fixed.xml: same 36 pass
/1.58s. No warning assertion/filter was weakened. Existing owner gaps remain.
Expanded eight-module compatibility: 73 pass on Python 3.10.11 /3.39s and
3.12.14 /8.35s. No full older-version/installed-wheel claim from these subsets.
Current-source full Python 3.14.7: **1099 passed, 10 skipped, 202 warnings
/209.21s**, exit0; JUnit 1109 total/zero failures/errors. Coverage includes
whole package and MCP subprocesses: 4227/4863 lines, 1311/1680 branches,
combined85%. No exclusions/warning suppression; changed source/test hashes
stable across run. Warning count unchanged; unmodified owners still need cleanup.
No private tests, SQL assertions, internal mocks, paid calls or real data/config
edits. OpenAI factory unchanged. Evidence and intermediate reports:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/langchain-lifetime-20261008-a/README.md`.

## SDK close and context lifetime — 2026-10-08

User-confirmed public SDK close/context/store/history seam, temporary synthetic
databases only. TDD close cases: 2 missing-method failures -> 2 passes; context
cases: 4 missing-protocol failures -> all 6 passes. Default/WAL normal and
exceptional exits, repeatable close, closed-use rejection, records on reopen,
and explicit-managed-instance ResourceWarning checks. No private tests, SQL
assertions or internal mocks. Initial default-temp permission failure is retained
separately, not counted as feature red; fresh explicit basetemp used thereafter.

Six related modules pass 64 each on actual-source Python 3.10.11 and 3.12.14.
Actual-source full Python 3.14.7: **1095 passed, 10 skipped, 202 warnings
/191.54s**, exit0; JUnit 1105 total/zero failures/errors. Coverage whole package
with MCP subprocesses: 4220/4856 lines, 1311/1680 branches, combined85%.
No module exclusions or warning suppression. Three changed code/test hashes
stable across run; separate corrected import check confirms actual checkout.

No new adapter API, tool-list change, destructor, auto index/model flush,
real data/provider edit, dependency or push. Existing abandoned-instance and
adapter warnings remain; constructor failures, new installed-wheel acceptance,
full older-version refresh and independent memory quality remain outside this
gate. Contract: [SDK_LIFETIME.md](SDK_LIFETIME.md). Retained evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/sdk-lifetime-20261008-a/README.md`.

## MCP EOF connection cleanup repaired — 2026-10-08

Existing stdio/EOF seam, default and opt-in WAL: two real subprocess cases
fail before repair at unclosed-database ResourceWarning, despite exit0/tool
discovery; pass unchanged after repair. Production input loop now closes its
owned connection in finally. Normalized AST matches retained pre-edit source
after unwrapping that try/finally; protocol/handler logic unchanged.

Related MCP/enhancement/link/doctor suite: 73 passes on each 3.14.7 (20.41s),
3.10.11 (16.94s), 3.12.14 (44.27s). Causal warning red/green is verified on
3.14; older-runtime warning absence alone is not cleanup proof. Actual-source
full 3.14: **1089 passed, 10 skipped, 202 warnings /199.76s**, exit0. JUnit:
1099 total/zero failures/errors. SDK/adapter warnings remain, not warning-free.
Coverage 4205/4841 lines, 1307/1676 branches, combined85%, subprocesses/whole
package retained. 235 source inputs unchanged across full run.

No new close tool/interface/dependency, warning suppression, automatic index/
model flush, real data/config/provider edit, paid call or push. Loop exceptions
are structurally covered by finally but not separately fault-injected; startup
failures/forced kill/SDK and factory lifecycle remain outside this repair. Prior
wheel predates this MCP edit; no rebuilt-install claim. Retained red/green,
exact commands, source identity and remaining acceptance:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/mcp-owner-cleanup-20261008-a/README.md`.

## SQLite ResourceWarning attribution, not repaired — 2026-10-08

Python 3.14.7 diagnostic adapters run with allocation tracing and explicit
ResourceWarning visibility: 21 passed/8 reported warnings /1.84s, plus teardown
GC warnings. Creation stacks point to earlier LangChain/factory constructions,
not necessarily the later line where GC emits the warning. JUnit confirms all
21 cases pass; that is not a lifecycle-success verdict.

Five repeats each: discarded SDK and LangChain instances produce one unclosed
database warning; identical public operations followed by existing explicit
connection close produce none. Discarded create_vibe_tools lists also produce
one per run, with no documented caller close handle. Three actual MCP stdin-EOF
children each exit0 but emit one unclosed warning after GC. Normal process exit
was previously proved; explicit connection cleanup was not.

Next: existing MCP EOF seam first, guaranteed owner cleanup without new tools;
SDK/adapter explicit lifetime contracts separately. No warning suppression,
destructor workaround, production/test edit, real data/provider change, paid
call or new full-suite measurement. Do not claim all 202 full-suite warnings
attributed or fixed from this subset. Source fingerprint remains unchanged.
Runnable controls, exact limits and repair ordering:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/sqlite-lifecycle-diagnosis-20261008-a/README.md`.

## Compact repair: current matrix and rebuilt install refreshed — 2026-10-08

Actual checkout full regressions: Python 3.10.11 **1087 passed/10 skipped
/192.13s**, Python 3.12.14 **1097 passed /260.15s**, both exit0. Parsed JUnit
confirms 1097 tests each and zero errors/failures. All ten 3.10 skips lack
Transformers. Existing rich 3.12 optional checks pass, not all-backend proof.
Source fingerprint (235 files) matches before/after and prior actual 3.14 run:
`c83b1fe6338bbba89ad87b8ae33b8f71c03db29a2707d61e689746ce67a50ea2`.
Runs overlap; times are not performance comparisons. 3.10 embedded runtime is
a compatibility harness, not a production patch-release recommendation.

3.10 coverage: 4223/4857 lines, 1307/1676 branches; 3.12: 4222/4857 lines,
1309/1676 branches. Actual coverage versions 7.16.2/7.16.0 respectively;
whole package/subprocess collection retained, combined terminal score 85%.
Current matrix commands, skips, runtime versions and hashes:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-matrix-20261008-a/README.md`.

Rebuilt current wheel/sdist in a new snapshot (52 input hashes match live).
Sdist rebuild preserves 48 package Python members plus metadata/entrypoints.
New wheel installs offline/no-deps into separate target using existing 3.14
runtime/dependencies. Parent/child actual imports assert new target; six CLI
help entries, SDK lifecycle, real MCP nine tools/store/recall/EOF exit0 pass.
Installed original allocation regression also passes at 12,103,155 bytes.
No old install/config/real data/default changed, model download, paid call or
publication/push. This is not fresh dependency resolution/full installed suite.
Build warnings/example distribution/minimum/hosted/other-version/platform,
3.14 SQLite lifecycle warnings and independent memory-quality gates remain open.
Rebuilt artifact identity, commands and smoke limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-wheel-20261008-a/README.md`.

## Compact TF-IDF applied: actual Python 3.14 full gate passes — 2026-10-08

After copying the six unchanged missing fixtures, candidate full regression
passes **1087/10 skipped /205.83s**; related 3.10.11 and 3.12.14 suites each
pass 97. Original checkout red check repeated before application (1 failed/
4 passed /2.38s, 17,473,163 bytes). Baseline source saved before edit.

Applied paired stdlib Q-index/d-double posting arrays only in tfidf.py, with
its representation comment corrected; actual/candidate AST equal. Original
test assertion/file unchanged. Actual-source allocation is 12,103,155 bytes
(~30.73% lower), below unchanged 16 MiB. Actual-source full Python 3.14.7 gate:
**1087 passed, 10 skipped /188.19s**, exit0; JUnit 1097 total/0 failures/errors.
All skips lack Transformers, not optional-model success. 202 warnings include
unclosed SQLite connections; that lifecycle attribution remains separate.

Coverage 4203/4839 lines (86.86%), 1307/1676 branches (77.98%), combined 85%;
MCP subprocesses included at 95.63% lines/93.90% branches, knowledge_pages at
0%. All 235 source-input hashes match before/after actual run. Differential
script now reads frozen original source, not modified live source, and retains
9600 exact search/300 exact transform comparisons. No self-comparison claim.

Closes this allocation regression, not full compatibility or quality gates:
3.10/3.12 current full-suite refresh, revised wheel/sdist smoke, optional models,
hosted/minimum/other-platform and independent retrieval quality remain open.
No real database/config/default/provider change, paid call, model download,
commit or push. Exact import proof, commands, hashes and retained history:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-tfidf-py314-20261008-a/README.md`.

## Isolated compact TF-IDF candidate, not promoted — 2026-10-08

Original source control with matching NumPy 2.5.3/pytest 9.1.1: Python 3.12
retains 16,140,051 bytes, 3.14 retains 17,473,163. This rules out NumPy version
mismatch for the observed crossing, not all runtime/SQLite differences.
Process-local dependency selection only; existing environments unchanged.

Isolated source copy changes only TF-IDF posting representation to paired
stdlib arrays (Q indices/d double weights), preserving iteration order. Same
3.14 fixture retains 12,103,155 bytes, ~30.73% lower; original 16 MiB assertion
passes without change. 34 resource/projection cases plus 63 contract cases
pass. Public vectorizer differential check passes 9,600 exact searches/300
exact transforms on synthetic fixtures; not independent relevance evidence.

Candidate full run is NOT green: 1083 passed/10 skipped/4 failed /185.44s.
Four resolution CLI tests fail because the initial snapshot omitted six
existing results JSON fixtures. After copying unchanged originals, all 100
resolution tests pass /17.03s. Fresh full rerun with fixtures and candidate
3.10/3.12 regression remain pending; original checkout is unchanged and its
3.14 resource failure remains open. No raised budget, production patch,
paid inference or model download. Exact scripts, bounds and hashes:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-tfidf-py314-20261008-a/README.md`.

## Python 3.14: core smoke passes, full gate fails — 2026-10-08

New no-system-site-packages venv, Windows/Python 3.14.7, SQLite 3.50.4 and
NumPy 2.5.3: frozen installed wheel passes isolated core smoke (six CLI help
entrypoints, SDK lifecycle, real MCP nine tools/store/recall/EOF exit0).
Core-only inventory was saved before installing dev dependencies; pip check
passes before and after expansion. No semantic extras/model download/paid calls.

Full current-source run after actual source-import verification: **1086 passed,
10 skipped, 1 failed /192.04s**, exit 1. JUnit confirms 1097 tests, zero errors;
ten skips lack Transformers. Failure is the 10,000-record retained-allocation
budget: 17,473,499 bytes vs 16 MiB. Without coverage, the same module gives
1 failed/4 passed in 2.24s, measuring 17,473,163 bytes. Do not mark 3.14 green.

Allocation snapshots point mainly to TF-IDF/BM25 posting tuples; a two-item
tuple is 64 bytes on 3.14 vs 56 on 3.12. Runtime object overhead is a supported
contributor, not a complete causal claim: comparison environments have different
NumPy versions. Same-dependency comparison and budget/storage decision remain open.
No implementation, assertion, skip policy or threshold was changed.

Coverage lines 4198/4834 (86.84%), branches 1305/1674 (77.96%), combined 85%;
includes MCP subprocesses (95.63% lines/93.90% branches) and knowledge_pages
at 0%. 202 warnings include unclosed SQLite connections, not warning-free
acceptance. All 235 source-input hashes match before/after. No real client/data,
hosted CI, full installed-wheel suite or independent quality claim. Exact commands,
hashes and reusable diagnosis:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/clean-wheel-py314-20261008-a/README.md`.

## Installed terminal-panel/MCP preference journey — 2026-10-08

Nine scripted stages pass on the clean installed wheel: fresh default,
first-use cancel/Enter, off/on without MCP restart, saved cancel, invalid
input, EOF and restart persistence. First eight observations share one live
PID; matching synthetic evidence delivery changes 5 to 2 to 5 with the switch.
Cancel/invalid/EOF preserve configuration bytes and mtime; initial cancel
leaves the settings file absent. Both temporary servers exit 0 after stdin
close. Only synthetic state under the new gate was used.

This proves command behavior/live preference reading, not automatic popup,
real host instructions/semantic selection, all-feature switches or human
visual usability. Privacy acknowledgement is informational: fresh/cancelled
first use still has enhanced=true and delivers five records. No production
consent gate was added; the guide now distinguishes cancel from off explicitly.
No full suite rerun or production/test change, real configuration/provider
edit, model download, paid call, publication or push. Exact journey/harness:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/installed-onboarding-20261008-a/README.md`.

## Clean core installed-wheel smoke — 2026-10-08

The frozen current wheel was installed into a new no-system-site-packages
venv on Windows/Python 3.12.14 via pip --isolated/--only-binary and an explicit
PyPI index. Resolver chose numpy 2.5.3; complete environment contains only
pip 25.0.1, numpy 2.5.3 and vibe-memory 0.3.0. No semantic/dev extras or model
download. Pip reused HTTP-cached binary artifacts, not a measured fresh download.

Python -I smoke outside the repository verifies parent/child VibeMemory and
NumPy imports from the new venv, system package inheritance disabled, and no
Transformers/SentenceTransformers. Six generated CLI --help entrypoints, public
SDK synthetic lifecycle and real MCP nine tools/store/recall/stdin-close-exit0
pass. pip check reports no broken requirements. Host selection remains pending
and unverified. The base interpreter/stdlib is reused, not a fresh OS image.

Core clean dependency installation/basic runtime is now evidenced on this
environment. Full installed-wheel regression, semantic extras, minimum versions,
other Python/OS/build-backend and real AI-client/quality gates remain open.
No existing runtime/configuration, production defaults, real data/provider,
paid request, publishing or push. Exact resolver report, paths and limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/clean-wheel-20261008-a/README.md`.

## Local built-artifact smoke — 2026-10-08

Built wheel and sdist from a new curated snapshot of current package sources,
pyproject.toml/README/LICENSE; 52 input hashes match the live dirty checkout.
Used installed setuptools public PEP 517 hooks (84.0.0, wheel 0.48.0) after
the available environment could not execute python -m build. No frontend
dependency install or build output in the original checkout. Rebuilding the
generated sdist preserves all 48 package Python files and metadata/entrypoints
bytes (50 comparisons, zero differences), not whole-archive reproducibility.

Wheel installed offline with pip --no-index --no-deps --target in a temporary
gate, reusing Python 3.12.14 and existing dependencies. Parent/child actual
imports and distribution metadata resolve under the installed target, outside
the repository. Six generated console executables pass --help; public SDK
synthetic store/recall/update/history/forget passes. Real installed MCP lists
nine tools, stores/recalls and exits 0 after stdin close; host selection remains
unverified as expected. No real configuration/database/provider edits, paid
calls, publishing, commit/push or new production/test code.

This is not a clean-environment dependency install, full installed-wheel suite,
real AI-host selection or published-release acceptance. Seed example JSON is
not packaged (default SDK does not load it); shipping-policy/regression is
open. License metadata emits backend deprecation warnings; no build-minimum
policy was changed to silence them. Exact artifacts, hashes, harness and limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/wheel-acceptance-20261008-a/README.md`.

## Current framed repair: full Python 3.10 gate refreshed — 2026-10-08

Current checkout: **1087 passed, 10 skipped /177.76s**, exit 0, Windows/Python
3.10.11. Parsed JUnit confirms 1097 total, zero failures/errors, ten skips.
Eight optional answer-model cases and two real-tokenizer checks explicitly
skip because Transformers is absent; not optional-model validation success.
This supersedes older 1085-collected/full and 60-test/targeted 3.10 evidence
for current-source core compatibility, not their historical records.

Reused the isolated embedded interpreter with numpy 2.2.6, pytest 9.1.1,
coverage 7.16.2, SQLite 3.40.1. Actual package import and python310._pth were
checked against the live checkout. No dependency/runtime configuration edit.
All three model-hub offline flags and an isolated COVERAGE_FILE were set;
same full coverage command below, with new gate root:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/framed-full-py310-20261008-b`.

XML coverage: lines **4218/4852 (86.93%)**, branches **1305/1674 (77.96%)**;
terminal combined score 85%, not line coverage. MCP subprocess source remains
included (95.63% lines/93.90% branches); knowledge_pages remains measured 0%.
Fingerprint of 235 inputs (package/test/experiment Python files and
pyproject.toml) is unchanged before/after execution:
`1d807cd2132c8b6c60c8a5e4c38341a1157dd6272914eaf07436d9021a6520ef`.

- junit.xml SHA256: `ce12a8e91ec564a648f14ccfe22d165eb7907cb26216e2cd89d504c71eb60b1d`
- coverage.xml SHA256: `94332e10530aa09df7f29613efbcedafe549cf094dbc1a3e9f647d21d65ea6a9`

Exact runtime/command/limits: `<gate-root>/README.md`. No production/test
changes, real data/provider edits, paid calls, commit/push or hosted CI run.
Optional models under 3.10 and current 3.11/3.13/3.14 compatibility remain
unverified. This gate is not independent memory quality or full-goal completion.

## Framed corpus identity installed: current regression gate — 2026-10-08

New tests/test_text_index_identity.py uses only public SDK/storage and synthetic
temporary/in-memory data. Fixed 10k short-record content-rebuild resource gate
was red on per-document hashes: 17,238,042 new retained traced Python bytes
exceeded 16 MiB. Framed-corpus digest passes. The budget excludes fixture
construction, follows GC after discarding the result, and is neither RSS nor
a global product memory cap. No elapsed-time hard gate.

Four public boundary cases cover precision/recall and same-/second-connection
updates: the unframed concatenated text stays identical while beta evidence
moves from atom a to b (Unicode, quotes and newline included). All pass live
code. An isolated copied mutation without the length prefix fails all four
by returning atom a. This mutation check does not claim four production bugs.
Five new tests alone: **5 passed / 2.06s**. No private cache assertions,
collaborator mocks or direct SQL assertions.

Python 3.10.11 related modules including the new tests: **60 passed / 80.50s**,
exit 0; parsed JUnit has no failures/errors/skips. Artifact:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/framed-related-py310-20261008-a.xml`.
This is targeted, not a current full 3.10 gate.

Full Python 3.12.14 suite: **1097 passed / 249.06s**, exit 0; parsed JUnit
1097 tests, 0 failures/errors/skips. Same coverage command and all three
model-hub offline flags as the preceding gates, with isolated gate root:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/framed-full-py312-20261008-a`.
MCP subprocess source remains included. XML lines **4217/4852 (86.91%)**,
branches **1307/1674 (78.08%)**; combined terminal score 85%, not line coverage.

- junit.xml SHA256: `7910a45d92071453b3aab33b1ea2eba95e4de5d5453efd6574b630e242ca1e6b`
- coverage.xml SHA256: `338e59cfafe54186e59abf03554e8e12ce507cfb2dd4be8d01dbed67c3cf8520`
- live ppr.py SHA256: `0f6e4a3995c87a8f13634a6a57000ddd53a3e9e82d95eea71ae71f6b6aed8705`

Live key implementation matches the measured framed candidate, with only
comments/docstrings different (verified no-index diff). The earlier controlled
10k short/long timing/allocation results remain bounded synthetic evidence,
not fresh production, independent quality, dense-model or hosted acceptance.
Corpus scanning and per-largest-record UTF-8 allocation remain. No version
suppression, new schema/interface/dependency, real database, paid request,
host/provider config, commit or push. Current 3.11/3.13/full 3.10 and broad
six-package completion are still not established by this gate.

## Metadata text-index repair gate — 2026-10-08

Public-SDK resource regression was red before the repair: 3,000 synthetic
records, confidence-only update, traced peak 5,450,253 bytes against a 3 MiB
warm-recall fixture budget. It became green with content-sensitive TF-IDF/BM25
cache keys. Four variants now check same-/second-connection metadata updates
in precision/recall, and three strict-scope membership/deletion cases cover
precision/recall/budget. Existing projection/evidence tests retain content,
store/delete, owner/lifecycle, graph and reinforcement checks. No private
cache assertions, mocks of index collaborators, direct SQL or elapsed-time
hard gates were added.

Python 3.12 related checks: 52 passed / 59.74s, then three new scope checks
passed / 0.35s. Python 3.10.11 current related module set: **55 passed /
63.09s**, exit 0; parsed JUnit confirms no errors/failures/skips. Artifact:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/metadata-py310-20261008-a.xml`.
This is a targeted 3.10 run, not a post-repair full compatibility run.

Full Python 3.12.14 current suite: **1092 passed / 241.69s**, exit 0;
parsed JUnit 1092 tests, 0 errors/failures/skips. Same coverage command and
three model-hub offline flags as the gate below, using new gate root
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/metadata-full-py312-20261008-a`.
Coverage includes MCP subprocess source: lines **4210/4845 (86.89%)**,
branches **1303/1670 (78.02%)**, combined terminal score 85%.

- junit.xml SHA256: `61a089023f63b6ecc6273bdccbb62a4f1350aa74cac29da917aaba881e4c379f`
- coverage.xml SHA256: `dc48f44a28c6611cc4b54db80495b618b5c6949ad88569be62bfa1dc339c4cce`

The separate 100-record diagnostic now observes zero text-index fit calls
after confidence changes and refitting after content changes. Neither those
profiles nor allocation-budget passes prove independent retrieval benefit,
large-scale latency/RSS reduction or real semantic-model compatibility.
Digest scanning has an O(corpus-bytes) cost and retained digest objects. Dense
provider ID/version caching remains unchanged by source inspection; no new
dense-model run was performed. No real database, host/provider setting, paid
call, dependency install, commit or push. Other current-version/hosted and
six-package quality gates remain open.

## Current post-repair Python 3.12 full coverage — 2026-10-08

Current checkout including all nine adapter ID cases: **1085 passed / 208.98s**,
exit 0, Windows/Python 3.12.14. Independently parsed JUnit: 1085 tests,
0 failures, 0 errors, 0 skips. This supersedes the earlier 1084-test Python
3.12 run for current-checkout regression evidence; historical runs below remain.

Command: `.venv/Scripts/python.exe -m pytest tests/ -q -o "addopts=--tb=short"
--basetemp <gate-root>/pytest-temp --cov=vibe_memory --cov-branch
--cov-report=term --cov-report=xml:<gate-root>/coverage.xml
--junitxml=<gate-root>/junit.xml`. `COVERAGE_FILE=<gate-root>/.coverage` and
HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE/HF_DATASETS_OFFLINE were all set to 1.
Fresh gate root:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/current-py312-20261008-b`.

XML totals: lines **4209/4844 (86.89%)**, branches **1303/1670 (78.02%)**.
Terminal combined score is 85%, not line coverage. MCP subprocess source is
included; unused knowledge_pages remains measured at 0%.

- junit.xml SHA256: `1cb32d4b5bc62cde0e6c41de5fd80b923d427114b29354421040c4a36438d3af`
- coverage.xml SHA256: `7232a6a7002a5af0d4a0333b051d62ff9c3162249702929569f1625b585d1f5d`

No production/test changes, paid calls, real database operations, host/provider
configuration changes, commit or push. This is local regression evidence, not
independent memory-quality improvement or hosted MCP acceptance. Current
Python 3.11/3.13 verification remains open.

## Post-repair Python 3.10 full compatibility/coverage — 2026-10-08

Current checkout including nine adapter ID cases: **1075 passed, 10 skipped /
118.55s**, exit 0, Windows/Python 3.10.11. JUnit independently reports 1085
tests, 0 failures/errors and 10 skips. The skips are eight optional answer-model
tests and two real-tokenizer trust-boundary checks, all because Transformers
is unavailable in this minimal environment, not successful model validation.

The existing isolated runtime
`C:/Users/ASYS/AppData/Local/Temp/vibe-python31011-embed-20261001-a/python.exe`
was reused without installation/configuration edits. Both the actual import
and its default `python310._pth` point at this checkout before site-packages,
including for child processes. Runtime: pytest 9.1.1, numpy 2.2.6, coverage
7.16.2. This older embedded runtime is a compatibility harness, not a
recommended production Python patch release.

Command: that interpreter `-m pytest tests/ -q -o "addopts=--tb=short"
--basetemp <gate-root>/pytest-temp --cov=vibe_memory --cov-branch
--cov-report=term --cov-report=xml:<gate-root>/coverage.xml
--junitxml=<gate-root>/junit.xml`; isolated `COVERAGE_FILE=<gate-root>/.coverage`
and all three model-hub offline flags. New gate root:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compat-py310-20261008-a`.
Original process was polled to exit; XMLs parsed after completion.

Package lines **4,210/4,844 (86.91%)**, branches **1,301/1,670 (77.90%)**;
combined terminal score 85% is a different metric. OpenAI Agents adapter
line-rate 98.11%, branch-rate 78.57%; MCP subprocess line-rate 95.63%,
branch-rate 93.90%. Unused knowledge_pages remains measured at 0%.

- coverage.xml SHA256: `7447b892ac293b64898ef8c7916d15b8b3055cdbce01327a709d3984418cf3e9`
- junit.xml SHA256: `86ab5a6f5f89268b41a86694cb7a201ba7088f2a173070ac37b704b3d62e16f6`

No production/test edits, real data, provider settings, paid calls, commit/push
or hosted acceptance in this run. Python 3.11/3.13 remain unverified for current
changes. Installed 3.14.7 lacks pytest/numpy/coverage/sklearn; no dependencies
were installed and no 3.14 suite was run. This result does not establish
independent retrieval/answer benefit or universal adapter correctness.

## Exact-ID order protection — 2026-10-08

The OpenAI Agents exact eight-character ID check now exercises both earlier
and later creation times relative to colliding long IDs, using the approved
public storage fixture API. Both correctly link the exact atom. This closes
an order-coverage gap in the original test; it needed no production change and
is not a new red-green repair. Current adapter/MCP-ID subset: **44 passed /
5.10s**, exit 0. JUnit artifact in the isolated workspace:
`results/oa-link-order-20261008-a.xml`. New adapter ID module has nine cases.
The 1084-pass full run below predates this additional parameter; no new full
suite, coverage, compatibility, host or model result is claimed here.

## OpenAI Agents link ID repair — 2026-10-08

After explicit approval of public adapter/SDK/storage seams, two deterministic
source/target-prefix tests failed: an ambiguous display ID returned `created`.
The adapter now prioritizes exact IDs, resolves only unique eight-character
prefixes within the current owner scope, and returns a JSON ambiguity error
before linking. Store/recall deliver an additive `full_id`; legacy `id` remains.
Separate missing-field tests failed before each delivery change. No SDK or HTTP
ID contract, model/provider setting or real database was changed.

Eight new checks in `test_openai_agent_link_ids.py` use fixed random IDs only
during public SDK fixture setup, temporary stores and actual adapter functions.
They cover source/target ambiguity without writes, requested full/unique-prefix
edge endpoints, exact eight-character IDs and full-ID delivery. The existing
ordinary adapter success assertion no longer accepts an error. No private
closures, direct SQL assertions or model calls are involved.

Adapter/new-ID/MCP-ID subset: **43 passed / 5.76s**. Full current local suite:
**1084 passed / 124.61s**, exit 0, Windows/Python 3.12.14; JUnit independently
reports 1084 tests, 0 failures/errors/skips. All three offline model-hub flags
were enabled. Command as the October 7 no-coverage invocation, using fresh root
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/oa-link-full-20261008-a`
and adjacent `oa-link-full-20261008-a.xml` JUnit report, SHA256
`0b7f5da6af5c82687e720af6b1219704cb23c3d7f59371b303f451834ea1b22b`.

No post-repair coverage or other-version/hosted result is claimed. The 1076-test
coverage measurement below predates this repair. No commit/push, wrong-edge
historical migration or production-data impact assessment was performed.

## Fresh full local coverage gate — 2026-10-08

Current dirty checkout: **1076 passed / 185.06s**, exit 0, Windows/Python
3.12.14, pytest 9.1.1, coverage 7.16.0. JUnit independently reports 1076 tests,
0 failures, 0 errors and 0 skips. XML package totals: **4,204/4,839 lines
(86.88%)**, **1,298/1,664 branches (78.00%)**; terminal combined score is 85%,
not line coverage. MCP subprocess source is included (line-rate 95.63%,
branch-rate 93.90%); knowledge_pages remains included at 0%.

Command: `.venv/Scripts/python.exe -m pytest tests/ -q -o "addopts=--tb=short"
--basetemp <new-gate-root>/pytest-temp --cov=vibe_memory --cov-branch
--cov-report=term --cov-report=xml:<new-gate-root>/coverage.xml
--junitxml=<new-gate-root>/junit.xml`. `COVERAGE_FILE` was isolated at
`<new-gate-root>/.coverage`; all three model-hub offline flags were set as in
the October 7 run. Root:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/local-gate-20261008-a`.
No old test root or report was overwritten. Original process was observed to
terminal exit; artifacts were parsed and hashed after completion.

- coverage.xml SHA256: `5d8918f00c79b9f056dbd2c1fd060d724d33194a7449bd8878b3d43b86bc7299`
- junit.xml SHA256: `e2e263bf2ec205dc9d56aa8fc4c42b434d34590764ad77322778d079d3a666a7`

No production/test changes, paid model calls, real-user database operation or
host configuration changes were made in this gate. This refreshes local 3.12
coverage only, not 3.10/3.11/3.13, hosted CI, release or independent answer
quality. Coverage movement across differently sized checkouts is not a causal
quality improvement estimate.

Read-only inspection still finds a weak OpenAI Agents adapter link assertion:
`tests/test_adapters.py::test_oa_link_and_forget` accepts either an error or a
status. Its passing result does not establish successful edge creation. The
adapter also resolves eight-character prefixes through a dictionary overwrite
in `vibe_memory/openai_agents.py::vibe_link`; collision safety is not established
by this test. These were not repaired or dynamically collision-tested here;
MCP's separately verified prefix guard must not be attributed to this adapter.

## Full local regression after MCP host acceptance — 2026-10-07

Current checkout: **1076 passed / 139.46s**, Python 3.12.14, pytest 9.1.1,
exit 0. JUnit independently reports 1076 tests, 0 failures, 0 errors and 0
skips. Local artifact `native_acceptance_full_regression_v1.xml` SHA256:
`120447acea8f307b1e2957cbe084dc58689fcc1aac73e2dd8b5d1aa5b84e8470`.
The artifact is in the isolated ZCode acceptance workspace, not published CI.

The full suite ran with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` and
`HF_DATASETS_OFFLINE=1`, a new synthetic test root, no coverage instrumentation,
and pytest arguments `-q -o "addopts=--tb=short" --basetemp <new-test-root>
--junitxml <new-report-path>`. Do not reuse a populated `--basetemp` directory:
pytest may clear it. Existing local HTTP-adapter fixtures use loopback; model
provider tests use their test doubles. No paid model request or real-user
database was used. This run does not refresh coverage or Python 3.10/3.11/3.13
compatibility and does not imply hosted CI, release or independent quality.

Separate current subsets: MCP/enhancement/link/settings/strict-scope **90 passed
/ 34.99s**; settings/enhancement after the onboarding-document update **17
passed / 7.19s**. The isolated native runner additionally has five offline CLI
regressions; these live outside this repository's 1076-test count.

Three separately reviewed, one-shot native ZCode/deepseek-flash MCP cases passed:
explicit elapsed duration, ambiguous duration clarification, and empty returned
evidence without a whole-library absence claim. These are real Agent/MCP answer
observations, not tests in the local suite or independent accuracy estimates.
Their artifacts, billing estimates and limitations remain in the isolated
acceptance workspace. No further paid case is authorized by this record.

## Experiment date propagation across frozen packs — 2026-10-04

After explicit approval of export/final/answer/CLI seams, evaluation date now
propagates from source batch default (overridden by explicit per-case date),
through export and final-selection freeze, into answer inputs. Date comes from
the original pack, never response-supplied metadata. Canonical date validation
is shared with run; legacy undated cases stay undated. Source/pack hashes already
cover date metadata; old artifacts were not rewritten or re-scored.

TDD first reproduced missing export argument, lost final/answer date and lost
CLI batch date, then fixed each slice. Eight new cases exercise date transport,
historical-question preservation, invalid original dates, old-pack compatibility
and subprocess export→finalize→answers with synthetic responses. These responses
are transport fixtures, not model-quality evidence.

Related modules: **115 passed / 14.17s**, Python 3.12.14,
`.tmp-asof-pipeline-py312-20261004`; **115 passed / 24.34s**, Python 3.10.11,
`.tmp-asof-pipeline-py310-20261004`, both exit 0. No fresh full suite/coverage,
real-host inference, independent review or production API/default change. Answer
citation-ID checks still do not evaluate temporal/semantic correctness. Next is
date-bound selection/answer evidence across controls, not another metadata feature.

## Experiment evaluation-date transport — 2026-10-04

`resolution_selection_probe.run` now accepts an explicit optional evaluation
date without temporal candidate filtering. Eight new date-transport/validation
cases first reproduced missing argument/validation, then passed. Related modules:
**107 passed / 14.00s** on Python 3.12.14, **107 passed / 13.97s** on Python
3.10.11, exit 0. Twelve original synthetic cases received source date 2026-10-01
with unchanged candidate order; diagnostic callback only, no model-quality claim.
See results/fact_selection_asof_check.md. No fresh full-suite/coverage result;
the 996-test run below predates this experiment-only change. Export/final/answer
pack propagation remains open; no production API/default or frozen pack change.

## Read-only history audit and public adapter remediation — 2026-10-04

Human approved both seams before implementation. New audit tests first failed
for a missing module, missing STALE report and missing CLI JSON, then passed
after minimal implementation. Seven synthetic temporary-file tests now cover
orphan categories, read-only preservation, valid STALE/cross-owner history,
timezone uncertainty, missing/unsupported files, CLI and committed WAL visibility.
No real user database or host/provider configuration was changed.

HTTP fixture binds port 0, polls authenticated `/health` rather than sleeping a
fixed startup interval, and always shuts down/joins. Assertions now identify the
stored memory and verify its summary/tags; MCP lifecycle always links the stored
IDs and verifies direction/label, while missing content must return an error.
The first stronger HTTP label assertion failed because the public response is
the existing Chinese enum value, not the English request label; test corrected,
production interface unchanged. These changes rectify a subset of weak tests,
not every test in the repository and not an actual host acceptance.

Validation (all exit 0):

- Python 3.12.14: **996 passed / 151.20s**, full suite,
  `.venv/Scripts/python.exe -m pytest -q --basetemp .tmp-history-public-full-20261004`.
- Python 3.10.11: **69 passed / 10.96s**, history audit, adapters and MCP,
  isolated interpreter and `.tmp-history-public-py310-20261004` root; this is
  targeted compatibility, not a new full 3.10 run.
- Prior intermediate 3.12 subset: 67 passed / 31.48s before two additional audit
  tests; final audit-only run: 7 passed / 0.70s.

These runs do not refresh coverage. XML below predates the new audit and PPR
changes. No hosted CI, release, independent answer-quality result or push claim.

## Latest PPR transition-reuse regression — 2026-10-04

After the per-call PPR transition cache change: **989 passed / 121.73s**, exit 0,
Python 3.12.14, offline model-hub flags, `.tmp-ppr-transition-full-20261004`.
This run did not measure coverage. Post-change Python 3.10.11 targeted PPR,
closed-form, tenant, determinism, projection and direction checks: 106 passed /
4.30s, exit 0, current checkout import verified, offline model-hub flags and
fresh `.tmp-ppr-transition-py310-20261004` root. This is targeted compatibility,
not a fresh 3.10 full run. Both XML reports below predate the production change
and must not be presented as current-change coverage.

## Current Python 3.12 coverage — 2026-10-04

Latest worktree (including eight-label trace assertions): **989 passed / 182.78s**,
exit 0, Python 3.12.14, no skips. Command: `.venv/Scripts/python.exe -m pytest -q
--basetemp .tmp-trace-full-cov-py312-20261004 --cov=vibe_memory --cov-branch
--cov-report=xml:results/coverage-current-py312-20261004.xml --cov-report=term`,
with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. Polled the original process
to terminal exit. XML inspected: lines 4,132/4,765 (86.72%), branches
1,261/1,628 (77.46%); terminal combined coverage is 84%, not line coverage.
XML SHA256: `c72ce1d4a9260286859890d384b3b5a29048d73ae8b456375d0214431504c3e8`.
The package includes unused modules and MCP subprocess source, without narrowing
measurement to improve the percentage. Passing optional-model tests here is not
independent quality or real-host/API billing evidence. This is local uncommitted
source, not hosted CI; Python 3.11/3.13 and remaining review work are unverified.

## Trace-label compatibility subset — 2026-10-04

The existing public SDK projection test now checks all eight relationship labels
in precision/recall, with literal expected trace endpoints, labels, depth and
0.65 confidence. Together with causal direction/signal regressions:
61 passed / 3.19s on Python 3.12.14 and 61 passed / 3.33s on Python 3.10.11.
The isolated 3.10 runtime's imported `vibe_memory.__file__` was checked to be
this checkout, not an installed package copy. Both use fresh temporary test
roots. These preserve navigational trace output, not reverse causal truth or
independent memory quality. No implementation change was needed for the stronger
assertions; they passed initially, so this is not a new red-green bug repair.

Current suite collection is 989 after adding 14 label/mode combinations to the
existing two instances. Python 3.10.11 full coverage completed: **979 passed,
10 skipped / 125.47s**, exit 0. Eight answer-model cases lack optional model
dependencies and two transformer-specific cases are skipped in this minimal
environment; these are not successful model validations. Command: isolated
3.10 interpreter `-m pytest -q --basetemp .tmp-trace-full-py310-20261004
--cov=vibe_memory --cov-branch
--cov-report=xml:results/coverage-current-py310-20261004.xml --cov-report=term`,
with both offline model-hub flags. XML inspected: lines 4,133/4,765 (86.74%),
branches 1,259/1,628 (77.33%); terminal combined percentage is 84%, a different
metric. MCP subprocess source appears in XML (line 95.59%, branch 93.75%).
XML SHA256: `16bfc29a27e871253ab1205a8c96e4083db5ff84b51d334bd8d8bc4e98cf90e3`.
No coverage exclusions or artificial threshold were added. Unused modules remain
included (knowledge_pages.py is 0%); coverage does not prove their integration.
The 975-test result below predates this expansion. Current 3.11/3.13, hosted CI,
real-host/model quality and the remaining review ledger are not closed by this
local compatibility run.

## Current working-tree regression — 2026-10-04

Windows/Python 3.12.14: **975 passed / 133.23 seconds**, exit 0.
Command: `.venv/Scripts/python.exe -m pytest -q --basetemp .tmp-full-goal-20261004-a`,
with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.
The same process was polled to completion, not restarted on observation timeout.
Includes local uncommitted experiment tests; not published CI or independent
retrieval/answer-quality evidence. No fresh coverage measurement, supported-version
matrix, real-host authorization, model billing or production data migration is
claimed. Existing user changes and temporary evidence were preserved.

Read-only onboarding inspection also confirms that privacy acknowledgement is
recorded through the terminal panel; MCP settings authorization currently relies
on host/user guidance, not a verified real-host approval workflow. Passing the
suite does not close that acceptance requirement or the remaining review ledger.

Install the development dependencies in your chosen virtual environment:

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/ -v --tb=short --cov=vibe_memory --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml
```

The same coverage command is configured in `.github/workflows/test.yml` for Python 3.10–3.13 on Ubuntu. Each job uploads only `coverage.xml` as `coverage-python-<version>`, including on test failure; a missing report fails the upload step. A configured workflow is not evidence of a completed hosted run. No minimum percentage is enforced yet: first establish reproducible baselines and prioritize uncovered behaviors rather than inventing a threshold.

Coverage measures the complete `vibe_memory` package, including currently unused modules; no low-coverage module is omitted to improve the score. Line coverage, branch coverage and the terminal report's combined percentage are different measures. Passing tests or high coverage do not prove independent retrieval quality, security, every optional model backend or every platform/version.

Subprocess measurement uses the standard `coverage.py` `patch = ["subprocess"]` configuration. Development dependencies require coverage with TOML support >=7.10 and pytest-cov >=7.0; production dependencies are unchanged. MCP test clients close stdin and wait for normal EOF exit, allowing coverage to flush, with a bounded kill-and-fail fallback for a hung process. The new exit check validates an actual server process rather than a mock. Abruptly killed processes may still lose measurements.

Use pytest for test verdicts and fixture lifecycle, including a single module: `python -m pytest tests/test_m1.py -q`. The eight old `run_all()` functions and two separate manual test runners were removed; running those files directly is no longer a supported test entry point. The manual loops could miss newly added tests, mis-handle fixtures or print failures without a failing process exit. Constant per-test `[PASS]` messages were removed; pytest's summary and exit code are authoritative. The comparison/simulation demonstration output, doctor output assertions and child-process protocol prints remain intentional, not substitute test verdicts. No test assertions, fixtures or diagnostic protocol outputs were removed in this cleanup.

Official references: [pytest-cov reporting](https://pytest-cov.readthedocs.io/en/latest/reporting.html), [pytest-cov subprocess migration](https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html), [coverage configuration](https://coverage.readthedocs.io/en/latest/config.html#run-patch), [GitHub artifact inputs and matrix naming](https://github.com/actions/upload-artifact).

## Local sparse projection regression — 2026-10-03

Unpublished worktree: sparse TF-IDF projection adds eight public-SDK cases in `test_retrieval_projection.py`. Two 3,000-atom allocation cases fail on the pre-change implementation (~5.17MB versus a 3MiB warm temporary-Python-allocation budget) and pass after change; the budget is fixture-specific, not process RSS or a latency threshold. Other cases cover metadata/content updates, repeated reinforcement, caller-mutated results, second-connection store/delete/lifecycle commits, history, owner isolation, complete evidence and graph-trace endpoint identity. No direct SQL assertions or private-method tests in the new module.

Relevant subset: **102 passed / 11.57s** on 3.12.14, **102 passed / 5.38s** on the existing isolated 3.10.11 environment, with this checkout imported first. Full rich 3.12.14 run: **891 passed / 122.54s**. All use offline model-hub flags and new unique pytest roots. An initial subset run had 30 passes and 18 Windows default-temp setup errors; rerunning in a fresh root resolved those environment errors without deleting old directories. No updated coverage or new hosted/Python3.11/3.13 proof. Performance comparisons and sampling limits are in RETRIEVAL_COST_DIAGNOSTIC.md; full regression is not independent quality or real-host model acceptance. The hosted results below still describe only their named commit, not these local changes.

## Hosted baseline: 53cfcb6

[Run 36818592016](https://github.com/sv8vkwmfr7-create/vibe-memory/actions/runs/36818592016), commit `53cfcb649a547d9f23767c8c6eca72b7661e2af9`, succeeded on Ubuntu for all four versions. Downloaded logs and artifact contents were inspected, not just the status badge. Each test command wrote coverage.xml; each artifact ZIP contains only that file and matches its published SHA256.

| Python | Actual result | Lines covered / valid | Branches covered / valid | Artifact ID |
|---|---|---|---|---|
| 3.10 | 822 passed, 11 skipped / 50.38s | 4009/4636 (86.48%) | 1221/1584 (77.08%) | 11142302977 |
| 3.11 | 822 passed, 11 skipped / 62.95s | 4007/4636 (86.43%) | 1221/1584 (77.08%) | 11141853590 |
| 3.12 | 822 passed, 11 skipped / 75.35s | 4007/4636 (86.43%) | 1221/1584 (77.08%) | 11142452601 |
| 3.13 | 822 passed, 11 skipped / 65.14s | 4007/4636 (86.43%) | 1221/1584 (77.08%) | 11142133142 |

Archive digests (not XML hashes), in Python-version order:

```text
3.10 a7787a503863c77c75d29c754fa2eb87bf9baa4f7776001825b13ef07d61f5a7
3.11 0faa30c92e9b9e2450dc34ba994c66b0561625d3cedb9337b607278559227295
3.12 06b428d34723b5cb9791094451328d6b3002caac9a77613d550caf9f32268b60
3.13 a3c566383f1fcb87e3662a22d5a20f05e18bf7e61e25fc696ca4bcc87b1e7865
```

All reports use coverage 7.16.2, include knowledge_pages rather than excluding it, and show MCP line-rate 0.9521 / branch-rate 0.9194. Eleven skips are eight optional answer-model, two optional real-tokenizer and one Windows-only working-set test; optional backends are not validated by these Ubuntu jobs. Python 3.13 logged 179 warnings; passing does not establish warning-free compatibility. Existing local measurements below remain historical, distinct baselines.

## Local baseline boundaries

Batch 3w test-runner hygiene regression: **833 passed / 114.21s** on the rich Windows/Python 3.12.14 environment; the ten changed modules additionally passed **214 / 8.44s** on the isolated Python 3.10.11 environment. Both use offline model-hub flags and isolated pytest roots. Collection stays 833; normalized ASTs preserve test assertions/fixtures after removing manual runners and constant success prints. This batch did not rerun coverage, so the last XML measurements remain 3v below. Based on a6000d9 plus uncommitted 3v/3w changes, not hosted CI or independent quality evidence.

Latest batch 3v (2026-10-01), based on pushed `a6000d904227559d7d7ff137dca1cc1aa7793cd0` plus uncommitted CI/compatibility repairs:

| Windows environment | Full result | Lines | Branches |
|---|---|---|---|
| Python 3.10.11 / SQLite 3.40.1, only dev dependencies | 823 passed, 10 skipped / 72.89s | 4,009/4,636 (86.48%) | 1,221/1,584 (77.08%) |
| Python 3.12.14 / SQLite 3.53.1, existing optional models | 833 passed / 168.47s | 4,008/4,636 (86.45%) | 1,223/1,584 (77.21%) |

Both use `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, separate `COVERAGE_FILE` paths and isolated pytest temporary roots; model-hub flags do not prohibit every network API. MCP remains 159/167 lines, 57/62 branches. Final edited SQLite/forgetting/WAL subset additionally passed 43 / 2.08s on 3.12. Ten 3.10 skips are eight optional local-answer tests and two actual tokenizer checks, not omitted core tests. Optional tests require cached model assets AND runtime dependencies; a cache alone does not imply Transformers/torch are installed. The dev extra now includes scikit-learn for the existing lexical gate experiment/test, not for production retrieval. Fresh minimal 3.12 collection previously failed without it.

3.10 XML SHA256 `a81e4b75564731ff7b14828c4ccf6c6224354e42ab11891ee14374c959e812f2` (222,667 bytes); 3.12 XML `7418e3073847af36811cf7561d8bbc654cea5a48cd1b370bb81ca697cba5a9cb` (222,640 bytes). Reports are temporary local artifacts, not downloaded CI artifacts. The first embedded 3.10 run preferred the installed package copy and produced a zero-data coverage report, which is invalid; placing the current checkout before site-packages fixed the source path. Full minimal runtime dependencies: numpy 2.2.6, sklearn 1.7.2, pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.2; the rich 3.12 environment versions below remain unchanged. The official 3.10.11 embedded package is an isolated compatibility harness, not a production patch-release recommendation.

[Hosted run 36747296226](https://github.com/sv8vkwmfr7-create/vibe-memory/actions/runs/36747296226) at the pushed base failed, with test exit 2 and no coverage artifact; the other matrix jobs were cancelled. Public logs required authentication (403), so the exact hosted traceback is unverified; the missing dev dependency was independently reproduced locally. The new repairs have not yet been pushed/retested on Ubuntu 3.10–3.13 or had hosted artifacts inspected. That gate remains open. Earlier measurements below are historical baselines.

Batch 3u, after per-instance SDK serialization: **833 passed / 135.35s**, Windows/Python 3.12.14, using the coverage command above with `-q` and an isolated pytest temporary root. Package lines: **4,008/4,636 (86.45%)**; branches: **1,223/1,584 (77.21%)**; combined rounded score 84%. MCP remains 159/167 lines and 57/62 branches. Local XML SHA256: `8d71c0237716a51e9f4f1cfb08319e974cab364a533254566386cdb9edd17ba8`, 222,640 bytes. Model-hub offline environment flags were not explicitly set for that invocation; it was not evidence that all network access was blocked. No live cloud-model integration was added. At that time hosted matrix and real Python 3.10 verification were pending.

The initial 2026-09-30 measurement, before enabling subprocess collection, passed 828 tests in 180.30s on Windows/Python 3.12.14. It covered 3,863/4,635 lines (83.34%) and 1,182/1,586 branches (74.53%), with a rounded combined score of 81%. That report **excluded subprocess executions** and is not the final MCP baseline. Its XML SHA256 was `98487efa95388895cc43161464f910255406e2741e555223f86a05521c111f49`.

After enabling subprocess collection and changing the test client's shutdown, the MCP/doctor subset passed 43 tests in 63.40s. MCP combined coverage was 93% (159/167 lines), versus 48% in the earlier full run; this reflects measurement completeness, not a production capability change. The added exit test initially failed in 0.62s because the old forced termination returned code 1 rather than normal exit code 0.

The final 2026-10-01 full run passed **829 tests in 226.92s**, with subprocess collection enabled:

| Measure | Covered / total | Rate |
|---|---:|---:|
| Package lines | 4,007 / 4,635 | 86.45% |
| Package branches | 1,225 / 1,586 | 77.24% |
| MCP server lines | 159 / 167 | 95.21% |
| MCP server branches | 57 / 62 | 91.94% |

The terminal combined score is rounded to 84%, not 84% line coverage. XML SHA256: `e7603e7b8514df5025ed54f352212dee346fab06f814c7f9fcdfad2a05fc4372` (222,650 bytes). `knowledge_pages.py` remains 0% covered; optional embedding/LLM provider branches and experimental partition paths also have gaps. They remain visible in the denominator. Next coverage work should establish their actual supported contracts and add behavior checks, not remove them from measurement or treat this baseline as complete coverage.

These measurements use an uncommitted working tree based on `505792e6532e42ea91c328dc656a6203daf17fa4`, including local review repairs and experiments; they do not describe the files at that commit alone. Runtime versions: SQLite 3.53.1, numpy 2.3.5, pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.0. Model-hub offline flags were enabled for full runs. Optional dependencies installed locally differ from the minimal CI environment; hosted results are pending push and actual matrix execution. Python 3.10 runtime verification is a separate, still-open gate.

`coverage.xml`, `.coverage` and `.coverage.*` are ignored local artifacts. XML contains source paths, line hits and branch counts, not test prompts or memory contents; it is the only upload path, not the entire working directory. To preserve a previous local coverage database, set `COVERAGE_FILE` to a new temporary path before running. To avoid a conflicting pytest temporary root on Windows, append `--basetemp=<new-temporary-directory>`; do not point this at a directory containing user data.
