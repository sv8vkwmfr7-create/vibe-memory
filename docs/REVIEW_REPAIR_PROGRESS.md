# Review repair progress — 2026-10-01

## GitHub development checkpoint prepared — 2026-10-08

User authorized a checkpoint commit/push, not a formal release. Selected core
reliability, SDK/adapter lifetime, onboarding/settings, corresponding tests and
documentation; included six synthetic frozen JSON inputs required by CLI tests.
Local model experiments, temporary DBs/caches and unrelated result artifacts stay
outside this checkpoint. Existing public author attribution is preserved.

Exporting the Git index exposed Windows CRLF conversion of byte-hashed JSON:
initial complete snapshot had 1101 pass, 5 fail, 10 skip /159.41s. A native
.gitattributes rule pins JSON checkout to LF; neither fixture content nor hash
assertions were changed. The new actual staged-tree snapshot passes the related
101 cases /20.04s and full Python 3.14.7 suite: 1106 pass, 10 skip /157.14s,
exit0. No coverage refresh or hosted CI result is claimed. Static Gitleaks8.30.1
snapshot scans report zero findings, not a guarantee all sensitive data is absent.

Known SDK constructor-failure cleanup, remaining unmanaged owners, full installed
acceptance, dependency/platform matrix and independent memory quality stay open.
No paid model call, real data/client/provider config change or release tag.
Private verification artifacts:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/github-checkpoint-20261008-b/`.

## Full installed attempt isolated fixture dependencies — 2026-10-08

Installed current wheel in fresh Python 3.14.7 venv, borrowing existing test
dependencies via a local .pth (not clean/minimum-dependency installation).
Six generated CLI --help entrypoints exit0. Installed vibe-doctor synthetic
MCP/store/restart/cross-session recall/scope/cleanup check also exits0.
Actual MCP subprocess resolves to new installed package; original full MCP44,
enhancement13, link14 and doctor2 cases pass. All 47 parent-loaded package modules
verify under new venv. No production/test assertion changes or paid calls.

Full attempt: 1096 pass, 10 fail, 10 skip, 170 warnings /693.79s, exit1.
Failures: five missing cwd seed JSON fixtures, four missing prior synthetic CLI
result fixtures, one experiment's source-hash report input paths. In a separate
control, restoring explicit inputs makes all same ten failed nodes pass /4.78s;
all 33 loaded package modules still from new venv. Original failed run preserved.
This is NOT full installed acceptance or ten established production defects.
Package JSON distribution contract remains separate; SDK default does not
request the seed fixture. Known constructor failure remains unfixed.

Coverage includes whole installed package/MCP subprocesses: 4230/4865 lines,
1312/1682 branches, combined85%, but initial harness pre-import emits a
module-not-measured warning. Next gate should freeze complete fixture inputs,
avoid pre-import before coverage, and rerun the full suite. Other Python full
installed gates, clean dependency build and independent quality remain open.
No real data/client config edit, commit or push. Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/installed-full-20261008-a/README.md`.

## Current wheel lifecycle subset verified — 2026-10-08

Rebuilt current dirty source into a fresh local wheel without changing production
code, existing dependencies or test assertions. All 48 package Python files match
checkout/archive/installed target byte-for-byte. Wheel SHA256:
`71355c78f93703ce12fc3ff3d6527b4f990650acfe66db025aa8594acfe98919`.
Five unchanged lifecycle/full-ID/contract test modules run outside source cwd,
with -I and installed target prioritized: 31 pass each on actual Python 3.10.11,
3.12.14 and 3.14.7. All 35 loaded package modules originate in the installed
target. No ResourceWarning emitted in observed final runs with visible warnings
and final collection. No paid inference, commit/push or real data/config edit.

Existing interpreter dependencies were reused; this is not clean/minimum-deps,
full installed-suite/console-script/MCP-subprocess or non-Windows acceptance.
Startup-failure repair awaits constructor seam confirmation; known bug remains
in this local wheel. No production release claim. Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/lifetime-wheel-20261008-a/README.md`.

## SDK startup failure reproduced, repair pending — 2026-10-08

Actual-source Python 3.14.7 public-constructor diagnostic, temporary synthetic
libraries only: valid tfidf with/context emits zero unclosed-database warnings;
invalid backend raises original ValueError and emits one warning on collection,
reproduced twice. SDK creates storage before embedding provider, but constructor
has no exception cleanup; caller context entry is never reached on failure.
Minimal control discards traceback/warning references between observations.
No production/test code changed. Proposed repair releases storage when later
SDK initialization fails, without changing backend error/fallback behavior or
successful SDK ownership. Constructor regression seam awaits confirmation;
storage-constructor-internal failure is a separate unverified path. Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/sdk-startup-diagnostic-20261008-a/README.md`.

## Existing adapter owners migrated — 2026-10-08

Migrated existing adapter tests and offline framework smoke to SDK/helper
close/with and the borrowed factory seam; no production behavior change this
turn. All existing assert ASTs and test names preserved against pre-turn dirty
backups. Short-ID tests retain two independent connections. One legacy factory
creation case remains for compatibility, with its known unmanaged SDK lifetime.
Same 44 cases with visible ResourceWarning: 24 unclosed-database warning text
emissions before, one after; both pass. This is not a whole-suite leak count.
Seven-module source subsets: 66 pass each on Python 3.10.11 and 3.12.14.

Real offline framework smoke refreshed on Python 3.12.14: seven tool schemas,
scripted Model through actual openai-agents 0.22.3 Runner store/recall, and
langchain-core 1.6.6 RunnableLambda two-turn read/save all pass. Zero cloud model
calls; external socket guard retained; visible ResourceWarning none emitted.
Fresh temporary pip target installed because the old temporary target was
missing package entrypoints despite retained metadata. Project dependency
declarations and existing environment distributions unchanged. This does not
prove cloud authentication, autonomous selection or answer quality. Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/adapter-owner-migration-20261008-a/README.md`.
Remaining: other owners/legacy factory cleanup, constructor failures, refreshed
wheel/full matrix and independent quality. No paid inference or real data/config
edit, commit or push.

Full source Python 3.14.7: 1106 passed, 10 skipped, 179 warnings /326.71s,
exit0. Whole-package coverage including MCP subprocesses: 4229/4865 lines,
1313/1682 branches, combined85%. Production SDK/adapter and migrated test/script
hashes unchanged through validation. Prior full run had 202 warnings; remaining
warnings are not suppressed and the suite is not warning-free. Duration is an
observed run time, not a performance gate or a claimed speed improvement.

## OpenAI factory can borrow caller-owned SDK — 2026-10-08

User-confirmed keyword-only memory= accepts an existing SDK. Caller config and
close/with control lifetime; factory neither creates nor closes a borrowed SDK.
Non-default agent_id/db_path/embedding_backend with memory raise ValueError.
Legacy constructor and exact seven-plain-function list stay compatible; no new
model-facing close tool, destructor, auto flush or warning suppression.

TDD borrow: one missing-keyword failure -> pass; conflicting options: three
missing ValueErrors -> all four pass. Seven final cases cover shared reads/
writes, normal/exceptional caller closure, persistence, discard without closing
caller SDK, and conflicts. Six-module related suites each pass 52 on actual
Python 3.10.11/3.12.14; these are not full matrix or installed-package proof.
All seven tool function ASTs/list match retained pre-edit source, preserving
earlier dirty full-ID/prefix fixes. Recommended examples now show SDK with.

Full actual-source Python 3.14.7: 1106 passed, 10 skipped, 202 warnings /222.78s,
exit0; JUnit 1116 total/zero failures/errors. Whole-package/MCP-subprocess
coverage: 4229/4865 lines, 1313/1682 branches, combined85%. Changed source/test
hashes stable across run. No warning-free, rebuilt-wheel or quality claim.

Legacy unmanaged callers still need migration; plain-function tests do not
refresh historical real Agents/Runner smoke. Missing optional framework deps
were checked, not installed. Constructor failures, package/matrix refresh and
independent quality remain open. No paid call, real data/config edit or push.
Contract: [ADAPTER_CONTRACTS.md](ADAPTER_CONTRACTS.md). Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/openai-lifetime-20261008-a/README.md`.

## LangChain helper explicit lifetime added — 2026-10-08

User-confirmed helper close/context/save/load/clear seams; synthetic temporary
databases only. VibeMemoryLC now delegates close/context lifetime to its SDK,
returns the helper on entry, and preserves caller exceptions on exit. Repeat
close is harmless. Clear remains deletion and permits subsequent save/load.
Usage examples now use with; framework and tool-list contracts unchanged.

TDD: one missing-close failure -> pass; two missing-context failures -> pass
after correcting an unrelated-query fixture expectation (no retrieval edit).
Combination run exposes old adapters' GC warnings contaminating an SDK-instance
warning test: one failure -> same 36 cases pass after pre-collection before that
instance's warning recording. No warning assertion removed/filter added; this is
test isolation, not proof old owners are repaired. See retained intermediate XML.

Eight related modules each pass 73 on actual-source Python 3.10.11 and 3.12.14.
Actual-source Python 3.14.7 full: 1099 passed, 10 skipped, 202 warnings /209.21s,
exit0; JUnit 1109 total/zero failures/errors. Whole-package/subprocess coverage
4227/4863 lines, 1311/1680 branches, combined85%. Changed helper/test hashes
stable through run; OpenAI factory hash unchanged. No warning-free or new wheel
claim. Latest package artifact still predates SDK and helper lifetime additions.
Existing helper behavior AST unchanged except lifetime methods and usage docs.
No OpenAI factory edit, model tool, paid call, new dependency, real data/config
edit, commit or push. OpenAI caller ownership, adopting close in existing
owners/tests, startup failures, package/matrix refresh and independent quality
remain open. Contracts: [ADAPTER_CONTRACTS.md](ADAPTER_CONTRACTS.md).
Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/langchain-lifetime-20261008-a/README.md`.

## SDK explicit lifetime added — 2026-10-08

Confirmed public seam: SDK close/context/store/history only, temporary synthetic
databases, no private tests, direct SQL assertions or paid calls. Added repeatable
close and context management; all SDK operations reject closed instances with a
clear RuntimeError. Maintenance admission and instance-lock ordering retained.
No auto index flush, destructor, new dependency or adapter/tool-list change.

Red/green: close cases 2 fail -> 2 pass; context cases 4 fail -> all 6 pass
on Python 3.14. Default/WAL, normal/exceptional exits and persisted records on
reopen covered. Existing related six-module suites each pass 64 on Python
3.10.11 and 3.12.14. These are not new full older-version matrix runs.

Actual-source Python 3.14.7 full suite: 1095 passed, 10 skipped, 202 warnings
/191.54s, exit0. Parsed JUnit: 1105 total, zero failures/errors. Whole-package
coverage including MCP subprocesses: 4220/4856 lines, 1311/1680 branches,
combined85%. SDK/maintenance/new-test hashes unchanged through full run.
Unmodified owners still generate warnings; no warning-free claim. Current wheel
predates this SDK change. Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/sdk-lifetime-20261008-a/README.md`.

Contract: [SDK_LIFETIME.md](SDK_LIFETIME.md). Adapter-owned APIs and examples,
constructor failure cleanup, abandoned instances and real-client quality remain
open. Existing adapters still need explicit ownership wiring; merely adding SDK
close does not fix unmodified callers. No real data/config edit, commit or push.

## MCP owned connection closes on EOF — 2026-10-08

Default/WAL real stdin-EOF regression first fails twice at unclosed ResourceWarning
while exit0/tool discovery pass; both pass after input-loop finally closes the
owned connection. AST comparison confirms no protocol/handler change beyond
that wrapper. No model-facing close tool, auto index flush or policy change.

Related suite passes 73 on 3.10/3.12/3.14. Actual-source 3.14 full regression:
1089 passed/10 skipped/202 warnings /199.76s, exit0, JUnit zero failures/errors.
Source inputs unchanged through run. This closes observed MCP EOF cleanup only;
remaining SDK/adapter warnings are not hidden or claimed fixed. Full old-version
matrix and rebuilt package were not refreshed for this new MCP edit.

Next define SDK/adapter explicit lifetime ownership/seams before new interface
tests. Startup failure cleanup, exceptional-I/O injection, forced termination,
old test cleanup, independent quality and overall review ledger remain open.
No real configuration/database/provider edits, paid calls, commit or push.
Evidence:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/mcp-owner-cleanup-20261008-a/README.md`.

## SQLite lifecycle warning diagnosed; implementation pending — 2026-10-08

Current 3.14 allocation traces attribute adapter warnings to unclosed connections
created by earlier helper/factory instances. SDK/LangChain disposal controls
reproduce warning 5/5; explicit existing connection cleanup gives 0/5. Factory
tools disposal reproduces 5/5, but public factory hides SDK ownership behind
seven functions and has no documented close handle. Not just test cleanup.

Three real MCP processes at stdin EOF exit0 yet each emits one unclosed database
warning after GC. Source has no guaranteed explicit close around input loop.
Keep prior normal-exit acceptance distinct from deterministic resource cleanup.
No demonstrated corruption/data loss or complete attribution of all suite warnings.

Proposed order: repair MCP owner cleanup on existing stdio/EOF seam first;
then define SDK/adapter close/context ownership, preserve factory tool-list
compatibility and improve old test/example cleanup. No added model-facing tool,
automatic LLM flush, destructor suppression or blanket warning ignore.
Diagnosis only: 21 adapter tests pass, full regression not rerun, source/test
fingerprint unchanged, no real data/config or paid calls. Retained reproductions:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/sqlite-lifecycle-diagnosis-20261008-a/README.md`.

## Compact repair current-version and package gates refreshed — 2026-10-08

Actual source full 3.10.11: 1087 passed/10 skipped /192.13s; 3.12.14: 1097
passed /260.15s, both exit0. Zero JUnit failures/errors. 3.10 skips only missing
Transformers; 3.12 uses existing optional dependencies. Source fingerprint
unchanged across runs and equal to prior green 3.14 full gate. Current local
3.10/3.12 refresh is done; no hosted/full supported-version matrix closure.

Current wheel/sdist rebuilt, 52 snapshot inputs match actual source; 50 code/
metadata members equal across sdist roundtrip. Offline new-target installation
passes actual parent/child imports, six CLI helps, SDK lifecycle, real MCP
nine tools/store/recall/EOF exit0. Installed original 16 MiB regression passes
at 12,103,155 bytes. Existing installation untouched; no production edits in
this turn, paid calls, model downloads, commit or push.

Still open: full installed-wheel suite/fresh dependency and minimum build gates,
3.11/3.13/current hosted/other platforms, optional model breadth, license metadata
warnings/example distribution, 3.14 SQLite connection lifecycle attribution,
real AI-client acceptance and independent applicability/answer-quality evidence.
Do not infer memory quality from passing compatibility tests.
Evidence and artifact hashes:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-matrix-20261008-a/README.md`,
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-wheel-20261008-a/README.md`.

## Python 3.14 allocation regression repaired in current source — 2026-10-08

Completed candidate full gate with all fixtures: 1087 passed/10 skipped
/205.83s; related 3.10 and 3.12 suites each pass 97. Reconfirmed original red
regression before application, then changed only TF-IDF posting representation
to stdlib arrays, retaining double weights/order and existing test threshold.

Actual checkout: retained allocation 17,473,163 -> 12,103,155 bytes (~30.73%
reduction), full Python 3.14.7 regression **1087 passed, 10 skipped /188.19s**,
exit0. JUnit confirms zero failures/errors, 235 source-input hashes unchanged
through the full run. Ten skips lack Transformers; 202 warnings include
unclosed SQLite connections. This closes the observed allocation failure only.

No extra dependency, retrieval scoring/ranking/default/API change, private-test
coupling, raised threshold, real data/config/provider edit, paid call or push.
Current full 3.10/3.12 refresh and rebuilt-install validation remain next;
earlier wheel artifacts do not contain this repair. Optional models, lifecycle
warning diagnosis, independent quality and overall review ledger remain open.
Exact red/green evidence, frozen baseline, comparisons and coverage hashes:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-tfidf-py314-20261008-a/README.md`.

## Python 3.14 resource fix candidate isolated, not applied — 2026-10-08

Matching NumPy 2.5.3/pytest 9.1.1 does not remove original 3.14 failure;
3.12 stays at 16,140,051 retained bytes vs 3.14's 17,473,163. Runtime posting
tuple overhead remains the supported contributor. No existing environment edit.

Only the isolated source copy replaces TF-IDF posting tuples with paired
stdlib arrays, preserving double weights/order. Existing 16 MiB test passes
at 12,103,155 bytes (~30.73% lower); 97 targeted tests and 9,600 search/300
transform exact comparisons pass. Original source/test/defaults unchanged.

Candidate full run: 1083 passed/10 skipped/4 failed /185.44s. All four failures
are resolution CLI reads of six omitted frozen JSON fixtures. Copying their
unchanged originals makes the whole module pass 100 /17.03s; do not call this
a corrected green full run. Next: full candidate rerun with complete fixtures,
3.10/3.12 regressions, then minimal patch and actual checkout full validation.
No production compatibility closure, real data/provider edits, paid calls,
model download, commit or push. Retained evidence and runnable controls:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/compact-tfidf-py314-20261008-a/README.md`.

## Python 3.14 full regression exposes allocation-budget failure — 2026-10-08

Clean installed core wheel smoke passes on a new Python 3.14.7 venv, with
NumPy 2.5.3; six console help entries, SDK lifecycle and real MCP nine tools/
store/recall/EOF exit0 verified. Host model selection remains unverified.
After adding dev dependencies, current-source full suite is **1086 passed,
10 skipped, 1 failed /192.04s**, exit 1. All skips lack Transformers.

Open compatibility item: existing 16 MiB retained-allocation test reports
17,473,499 bytes; isolated no-coverage repeat reports 17,473,163 (1 failed,
4 passed /2.24s). Evidence retrieval assertions pass. Snapshot comparison
supports larger Python 3.14 posting-tuple overhead as a contributor, but NumPy
differs between environments; causal isolation remains pending. Preserve red
test, then compare same dependencies before choosing compact posting storage
or revising the cross-runtime resource contract. Do not hide with a raised cap.
202 warnings include unclosed SQLite connections and require separate attribution.

No production/test edits or default changes, real data/provider/config changes,
model downloads, paid requests, publishing, commit or push. Coverage/JUnit,
unchanged source fingerprint, import proof and repeatable diagnosis retained:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/clean-wheel-py314-20261008-a/README.md`.

## Installed first-use settings journey verified — 2026-10-08

Clean installed package, nine scripted terminal-panel/MCP stages passed:
initial defaults/cancel/confirm, live off/on in one server, cancellation,
invalid input, EOF and persisted restart. First eight use the same live PID;
delivered matching records change 5/2/5 without restart. Cancel/invalid-input/
EOF preserve settings bytes/mtime; both temporary MCP processes exit 0 on EOF.

Important existing policy made explicit in the guide: cancel is not off;
first-use cancel retains enhanced=true, and privacy_acknowledged is not an
enforced delivery gate. This is not automatic first-run popup/host consent,
real model selection, human visual usability or completion of all switches.
Only synthetic local state; no production behavior, existing client/runtime
settings, real database, model/API call, publishing, commit or push changed.

Retained states, import proof, harness and limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/installed-onboarding-20261008-a/README.md`.

## Clean core dependency installation verified — 2026-10-08

New venv, system site-packages false, Windows/Python 3.12.14. Installed the
frozen wheel with declared core dependencies only: numpy 2.5.3 and vibe-memory
0.3.0, plus bootstrap pip 25.0.1; no model/dev extras. Actual parent/isolated
child imports point at the new environment, not source or the previous target.
Six CLI help entrypoints, public SDK synthetic lifecycle, real installed MCP
nine tools/store/recall/EOF exit0 and pip check pass. No host semantic selection.

This closes bounded clean-core-install/basic-smoke evidence, not a full clean
machine/build, installed-wheel regression or broad compatibility/quality gate.
No existing environment, production source/config/defaults, user database,
provider settings, model download, paid calls, publishing, commit or push.
Minimum/other-version/semantic-extra/client acceptance and prior release
warnings remain open. Resolver hashes, inventory, paths and command:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/clean-wheel-20261008-a/README.md`.

## Built wheel installed and smoke-checked outside checkout — 2026-10-08

Curated current-source snapshot builds wheel/sdist; 52 copied inputs match the
live checkout. Sdist-to-wheel rebuild matches 48 Python files plus metadata
and entrypoints. Offline target installation uses existing Python/dependencies;
actual parent/child imports point at the wheel installation rather than source.
Six generated --help entrypoints, public SDK synthetic lifecycle and real MCP
store/recall/nine tools/stdin-close-exit0 pass. Host selection remains pending
and unverified, not a model-quality success. No publishing or production changes.

Release caveats recorded: seed example JSON not bundled (not loaded by default
SDK), license metadata backend warnings, missing executable build frontend
worked around with installed public backend hooks. No automatic package-data
policy/minimum-backend changes. Clean dependency installation, minimum backend,
full installed-artifact suite, other runtimes, hosted CI/release and real AI
client acceptance remain open. No real data/provider edits, paid calls or push.

Artifact hashes, exact commands, import proof, smoke observations and limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/wheel-acceptance-20261008-a/README.md`.

## Current full Python 3.10 core regression refreshed — 2026-10-08

Current source including framed text-index identity: 1087 passed, 10 skipped
/177.76s, original process exit 0. JUnit independently confirms 1097 tests,
zero failures/errors. All skips are due to missing Transformers: eight
optional answer-model cases and two real-tokenizer checks. The current local
3.10 core full-suite evidence gap is closed; optional model compatibility is
not. Older full/targeted results are retained, not relabelled as current.

Coverage lines 4218/4852 (86.93%), branches 1305/1674 (77.96%); subprocess MCP
source included. Before/after fingerprints of 235 Python/source-config inputs
match. Reused isolated existing runtime, offline model-hub flags and a new
test artifact directory; no production/test/dependency/provider changes,
real data, paid calls, commit/push or hosted CI run. Current 3.11/3.13/3.14,
optional model, publishing/client and memory-quality gates remain open.

Parsed reports, hashes, exact command, runtime and verification limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/framed-full-py310-20261008-b/README.md`.

## Applicability inputs frozen; structural acceptance is not semantic proof — 2026-10-08

Prepared fourteen label-free selection inputs from the unchanged frozen SDK
soft-scope top20 pools: four questions in three contexts plus delivered-empty
and question-title-only abstention controls. Independent per-case files carry
question/as_of/scope and full candidate text/scope; review criteria and source
labels remain separate. This is not production MCP delivery or independent
evaluation. No model/paid call, new production API/default or provider change.

Existing process_selection protocol replay preserves original text and empty
selections; an unknown ID falls back observably. A deliberately wrong-scope ID
is structurally accepted: no scope/time/semantic verification is claimed.
Its output omits case applicability context, so any future answer stage must
rejoin selected IDs with immutable original evidence/question/date/scope.
The resolution probe's session/exact-scope pool and root-cause answer prompt
are domain-specific, not an unchanged generic config-answer pipeline.

Related current-source experiment regressions: 141 passed /14.55s, JUnit
failures/errors/skips zero. Fourteen model files plus combined input, review
and protocol-check artifact have seventeen verified hashes. No semantic model
result or quality gain is inferred from these checks. Fresh bounded paid
authorization is required before submitting any case; old authorization is
exhausted. Overall compatibility/host/onboarding/performance work remains open.

Input manifest, isolated files, contract audit and reproduction:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/applicability_selection_v1_isolated/REPORT.md`.

## Local relevance reranker is not an applicability fix — 2026-10-08

Replayed the frozen SDK soft-scope pools with already-local bge-reranker-base,
CPU/local-only loading, no paid/answer-model calls or download. Model input is
only question/text pairs; expected answers and developer labels are excluded.
Three fixtures x four questions x three pool depths, repeated in reverse job
order: 72 observations, all 36 repeat pairs retain selected-ID order.

At depth20/final5, all-required-evidence coverage stays 4/4 on original7,
improves 1/4 to 2/4 on same_scope19, and improves 2/4 to 4/4 on missing_scope7.
T01/T03 still miss current_prod under same-scope question-title distractors.
Explicit test-environment records enter 3/4 same_scope19 outputs and 4/4 of
each seven-record fixture. This is candidate contamination, not a measured
wrong final answer. The frozen pool cannot be repaired when required evidence
was excluded before scoring. No general accuracy/model-default conclusion.

Do not promote the reranker as the fix. Next quality work must separate text
relevance from scope/time/fact applicability using existing selection
experiment seams, preserve frozen misses, and validate the full candidate to
selection to answer chain before production changes. Fresh paid authorization
is still required; the paused independent review is unchanged. No production
code/default change, commit or push. Exact model/source fingerprints, scores,
selected IDs, limitations and reproduction:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/selection_local_reranker_v1/REPORT.md`.

## Candidate omission diagnosed; simple remedies fail stronger controls — 2026-10-08

The original T01/T03 top-five miss reproduced twice per question through the
public SDK. All seven source texts survived in active history. Public component
replay ranks current_prod sixth/seventh in TF-IDF and seventh in BM25: lexical
ranking and candidate truncation, not lost storage. Soft scope promotion occurs
after truncation and cannot recover the omitted record. Disabling automatic
edges or Episodes does not recover it. No production-code/default change.

Expanded developer-authored controls preserve the original questions/texts,
add twelve same-scope question-title notes, or remove only current_prod's
environment metadata. In the nineteen-record fixture, top20 covers all four
questions' required sources, but retaining the first five covers only one;
strict scope also covers only one. For missing metadata, top20 covers four but
final-five/strict-top5 cover two. These are evidence-coverage counts, not answer
accuracy or independent evaluation. Forty-eight SDK observations and a fresh
repeat preserve all coverage verdicts; twelve distractor-order comparisons
differ, so exact rank determinism is not claimed. No degradation events.

Already-local BGE-small-zh-v1.5 was compared through public SDK readers on
fresh identically TF-IDF-written temporary stores, with offline flags and no
fallback. Across twelve contexts per backend, top-five full-evidence coverage
is 2/4 versus 2/4 on original7, 1/4 versus 2/4 on same_scope19, and 2/4 versus
2/4 on missing_scope7 (TF-IDF versus BGE). The motivating current_prod miss
persists for T01/T03. Timings include loading, not a warm latency benchmark.

Next: test the existing local reranker against frozen pools before proposing
any production or model-default change. No paid/answer-model calls, downloads,
real database/provider changes, commit/push or independent-review completion.
Detailed inputs, observations, limitations and reproduction scripts:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/selection_controls_v2/diagnosis_v1.md`
and `C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/selection_pool_challenge_v1/REPORT.md`.

## Four controls frozen offline: required current fact omitted — 2026-10-08

Before any fresh paid authorization, reused the existing public SDK input
preparer and static production instruction to freeze four new developer-
authored synthetic current/history/future-plan/insufficient-evidence controls.
Model calls zero; no production/test code change. Source and first candidates
are preserved, not tuned after observing the outcome. Not independent review.

Status blocked_missing_evidence: T01 current configuration and T03 future-plan
comparison both omit required current_prod from top-five delivered candidates.
That source describes online failed requests being attempted again four times,
effective September 20; other records use literal production/retry terminology.
T02's historical source and T04's unknown-policy source are delivered. No SDK
degradation failures. This does not yet prove whether storage/merge, candidate
generation, ranking or scope handling causes the omission, and is not a model
selection/answer failure or an overall accuracy estimate.

Next priority: diagnose storage survival and recall-stage loss via the existing
public SDK/history/storage seam. Do not spend proposed paid calls on unseen
required evidence or rewrite the fixture to improve rank. Do not infer a
production model/default change from this small synthetic control. Previous
four-call authorization remains exhausted; automatic continuations are not
new authority. 96-row human review remains paused, no real-data/provider/config
operation, commit or push. Pack, mapping, source hashes and exact limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/selection_controls_v2/README.md`.

## Next priority returns to memory-task quality — 2026-10-08

The framed-index repair is locally implemented and gated; more identical
regression/performance runs are not a substitute for answering memory tasks.
Current evidence still separates three earlier native host cases from four
provided-context generateText cases. The latter meet original synthetic
criteria but do not cover all current/historical/future/insufficient-evidence
controls, independent benefit or strict answer-only-from-selected-ID grounding.

Proposed next bounded execution: four one-shot synthetic questions covering
current confirmed configuration, historical configuration, future plan versus
effective fact, and insufficient applicable evidence. Freeze evaluation dates,
inputs/instructions and developer criteria before calls; send no reviewer labels,
keep first responses/errors/usage, no retries or default/ranking changes. Reuse
the existing isolated DeepSeek route after live availability verification.
This proposal is not a frozen input pack or an executed experiment; fresh
human call authorization is required. Do not silently implement a two-stage
pipeline or resolve the separate attribution/visibility product decision.

Read-only shared-ledger check: all existing request entries settled, unchanged
11-CNY cumulative limit, conservative settled estimates total 1.327322 CNY;
provider billing was not inspected. Remaining budget is not call authorization.
Prior four-question authorization is exhausted. Start Plan and the 96-row
human review remain deferred; do not fill the latter. No new paid call, model
run, production/test edit, real database operation, commit or push this turn.

## Framed text-index identity installed locally — 2026-10-08

Within the human-confirmed public SDK/storage boundary, a new 10k fixed-text
rebuild resource regression first failed on live per-record hashes: 17,238,042
new retained traced Python bytes exceeded its 16 MiB fixture budget. The
measured framed-corpus candidate makes it pass. Live TF-IDF/BM25 cache identity
now retains ordered IDs plus one SHA256 of byte-length-prefixed UTF-8 documents;
no full plaintext corpus or per-document digest objects. Dense ID/version keys,
metadata version increments and fresh owned/lifecycle/scoped reads remain.

Four additional public cases move beta evidence between two records while
preserving concatenated bytes, with Unicode/quotes/newline content, precision/
recall and same-/second-connection writes. All pass live code. The copied
unframed mutation fails all four, returning stale atom a instead of expected b.
This is a mutation safety check, not four new production bug discoveries.
New module: tests/test_text_index_identity.py, five cases, no private cache
assertions, direct SQL, collaborator mocks or elapsed-time hard gate.

The live implementation differs from the measured isolated candidate only in
comments/docstrings (verified no-index diff); timing evidence remains the
previous bounded synthetic comparison, not a new independent benchmark or
production SLA. Encoding still scans the corpus and allocates by largest
record; no fixed single-record memory cap or zero-cost invalidation is claimed.
No new interface/schema/dependency, real database, model/provider changes,
paid calls, commit or push. Current 3.12 full gate: **1097 passed / 249.06s**,
JUnit 0 failures/errors/skips; package line coverage 86.91%, branch 78.08%.
Current 3.10 related gate: **60 passed / 80.50s**, no failures/errors/skips,
not a new full compatibility run. Commands, XML counts, hashes and limits are
in TESTING.md. Broad six-package scope remains open; original broad audit
44 closed / 9 excluded / 12 unclosed is not recalculated from this subtask.

## Compact corpus digest candidates screened — 2026-10-08

Two isolated public SDK/storage experiments preserve live source. JSON-stream
digest is rejected: short warm improves 23.96→20.25ms but long notes worsen
38.71→66.50ms. The next length-framed UTF-8 streaming SHA256 candidate improves
short warm 24.59→18.84ms and long warm 39.68→33.19ms on separate controlled
10k fixtures; one traced allocation run/profile/version retains 1,209,879 fewer
new Python bytes (~1.154MiB), without retaining full plaintext. Encoding still
allocates by largest record, so no fixed single-record memory cap is claimed.

Each experiment: 136 timed recalls, 68 paired returned ID/order/content/
confidence sequences equal, no degradation failures; eight additional traced
calls excluded from timing. Two reversed-order repetitions, synthetic repeated
long notes and uncontrolled host load limit generalization. Not independent
quality, dense/disk/graph or 100k evidence. Live digest source remains unchanged.

Framed candidate isolated import verified; existing public projection/strict-
scope/evidence regressions: **55 passed / 64.04s**, JUnit no errors/failures/
skips. A public boundary-moving check passes candidate precision/recall and
fails a copy with framing removed. Initial reversed fixture dates had not
activated the mutation and were corrected; do not count that initial pass as
effective safety evidence. No production/test code edits, new full/compatibility
gate, model cost, real-data operation, commit or push this turn. Next retain
this boundary regression and gate the candidate before replacing live code.

Detailed raw reports, source hashes, sample counts and limits:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/metadata-framed-comparison-20261008-a/REPORT.md`.

## Direct-content cache key measured, not adopted — 2026-10-08

Reused the isolated public SDK/storage comparison runner for current digest
versus exact-content keys, differing only in the executable cache-key expression.
10k fixed-ID/time synthetic precision fixtures with short or 20x repeated
background text, two reversed-order repetitions: 136 timed calls, all 68 paired
returned ID/order/content/confidence sequences equal, no degradation failures.
Eight separate allocation-only recalls are excluded from timings (144 total).

Short unchanged warm medians: digest 23.26ms, content 17.56ms. Long: 38.04ms
versus 30.14ms. But new retained traced Python allocations after first recall/GC
increase by 398,855 bytes for short notes and 12,536,606 bytes (~11.96MiB) for
long notes in one measurement/version/profile. This is not process RSS.
Unconditional plaintext retention is not adopted. Current live digest source
hash is unchanged; no production/test code, real data, provider config, paid
call, commit or push. The next candidate is a compact unambiguously framed
whole-corpus digest with bounded working allocation, not yet implemented or
proven faster. Do not substitute the short-record win for long-record evidence.

Full protocol, samples, counts, source hashes and limitations:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/metadata-content-comparison-20261008-a/REPORT.md`.

## Metadata repair latency/retention tradeoff measured — 2026-10-08

Controlled isolated package copies differ only in the executable cache-key
expression; baseline restores ID/version and current matches live source.
Fixed-ID/time 1k/10k public SDK/storage synthetic fixtures, precision/recall,
two repetitions reversing version order: 272 timed calls, all 136 paired
returned ID/order/content/confidence sequences equal, no degradation failures.
No tracing in latency runs. Four separate traced calls measure Python allocation.

At 10k, confidence-update recall median changes from 183.15/186.00ms to
24.50/24.95ms (precision/recall, about 86.6% shorter). Unchanged warm recall
changes from 17.72/17.19ms to 23.47/23.98ms: about 32.5–39.5% longer, or
5.7–6.8ms extra. This confirms the digest tradeoff; not universal acceleration.
One traced 10k precision run/version shows 650,048 additional retained Python
bytes after first recall/GC, while metadata-call incremental traced peak falls
from 16,127,951 to 6,286,818 bytes. These are not RSS/production SLA results.

Next prioritize reducing unchanged-query digest overhead while preserving
content/order/membership invalidation, fresh metadata and dense behavior,
within the confirmed public SDK/storage test seam. Do not hide this regression
behind a faster metadata-only fixture. No production-code change this turn,
paid calls, real data, new defaults, commit or push. Broad performance gates
remain open. Full protocol, raw cells, ranges and hashes:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/metadata-comparison-20261008-a/REPORT.md`.

## Text-index metadata invalidation repaired locally — 2026-10-08

Human confirmed public SDK/storage tests on temporary synthetic databases.
The new public-call allocation regression first failed: a confidence-only
update caused 5,450,253 bytes of traced peak allocation for a 3,000-record
warm precision recall, exceeding the fixture's existing 3 MiB budget.
After the narrow repair it passes. Four variants now cover precision/recall
and same-/second-connection metadata updates, checking fresh summary/tags/scope,
confidence/decay/weight, version increment and reinforcement as well as the
allocation bound. Three additional public checks cover strict-scope membership
changes and deletion across connections in precision/recall/budget modes.

Only TF-IDF-backed retrieval changes cache identity to ordered atom IDs and
SHA256 content digests for its TF-IDF/BM25 indexes. Dense-provider retrieval
keeps ID/version identity. No metadata/version suppression, mutable-atom cache,
candidate truncation, retrieval threshold/default or new dependency is added.
Digest computation still scans/encodes the corpus on every call and retains
per-document digest objects; this is not constant-time invalidation or an
established overall latency/RSS improvement. Existing cache retention limits
are unchanged, and neither a real semantic-model benchmark nor universal dense
compatibility is claimed from source preservation.

The original 100-record public-SDK profile was replayed separately: unchanged
and confidence-only queries now make no fit calls, while content change still
fits TF-IDF/BM25 and returns the new text. Original failing and new passing
JSON reports are preserved as metadata_index_repro_v1.json and
metadata_index_repro_green_v1.json in the isolated workspace's results directory.
These instrumentation observations are distinct from the repository public-API
test assertions. No real database, provider configuration, paid call, commit
or push. Broad performance and six-package completion remain unproven.

Verification: current 3.12 full suite **1092 passed / 241.69s**, JUnit confirms
0 failures/errors/skips, line coverage 86.89%, branch coverage 78.02%. Related
3.10 suite **55 passed / 63.09s**, no failures/errors/skips; no new 3.10 full
run is claimed. Commands, artifacts and hashes are in TESTING.md. The original
44 closed / 9 excluded / 12 unclosed broad audit count is not recalculated
from this implemented subtask alone.

## Metadata-only index rebuild reproduced — 2026-10-08

New offline diagnostic uses only public SDK store/update/recall with 100
synthetic in-memory records, TF-IDF, no automatic edges/Episodes or model calls.
An unchanged warm precision query makes zero VibeMemory fit calls. Changing
only anchor confidence to 0.6 makes TF-IDF and BM25 fit once each (plus the
provider wrapper); changing content also fits. All phases return the anchor,
updated confidence/content and no degradation failures. The explicit proposed
no-refit performance assertion fails for the confidence-only phase; this is
not evidence of an incorrect answer or a measured latency SLA violation.

Reproduction command: project Python interpreter followed by
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/metadata_index_repro_v1.py`.
Its first report is `results/metadata_index_repro_v1.json` in that isolated
workspace. Existing files are protected against overwrite. The script exits 1
on the observed no-refit assertion, intentionally; it is not a passing test.
Current source still keys indexes by atom ID/version and increments version
for metadata updates. No cache-key repair, production/test edit, default change,
real database operation or paid call was made. Before implementation, confirm
the public SDK/storage test boundary and preserve content/membership/order,
owner/lifecycle/scope and cross-connection invalidation. Do not suppress version
increments merely to hide this rebuilding cost.

## Current Python 3.12 post-repair gate refreshed — 2026-10-08

Full current suite including the final exact-ID creation-order parameter:
**1085 passed / 208.98s**, exit 0, Python 3.12.14. Parsed JUnit confirms
0 failures/errors/skips. Coverage XML: 4209/4844 lines (86.89%) and
1303/1670 branches (78.02%), including MCP subprocess measurement.
Commands, isolated artifacts and hashes are recorded in TESTING.md.

This closes the stale 1084-test Python 3.12 gate gap; it does not close
independent answer-quality, real host acceptance or other-version gaps.
No production/test edits, paid calls, real data operations, commit or push.
The six-package objective remains incomplete.

## Four-case evidence-selection acceptance executed — 2026-10-08

Human separately authorized four one-shot paid questions. Frozen L02/L03/L06/D01
inputs were unchanged and submitted independently through the existing native
ZCode generateText route, tools disabled and retries zero; no reviewer labels
were sent. Returned selection: deepseek-vibe-test/deepseek-flash, low reasoning.
All four completed with stop and settled usage. Developer review found original
criteria met: environment-specific 4/1 retries, unconfirmed 7 not promoted,
12 elapsed calligraphy days and preserved date-list weather evidence.

Important new gap: L02 selected only production/test records but the answer
also mentioned the unselected rumor. That satisfies the original no-promotion
criterion, not a stronger answer-only-from-selected-evidence contract. Do not
equate selected IDs with mechanically isolated answer evidence. Decide whether
selection is an attribution declaration or a strict visibility boundary before
claiming or implementing a stronger product guarantee.

Four calls: input 2,273, output 1,218, reported total 3,491 tokens; separately
reported reasoning 978. Sum of per-call elapsed times 22.484s. Existing ledger
conservative estimate 0.022114 CNY double-counts separately reported reasoning
and ignores cache discounts; not a provider bill. Existing cumulative 11-CNY
limit unchanged. Detailed raw outputs, usage and review:
`C:/Users/ASYS/.zcode/vibe-memory-deepseek-test-20261006/results/selection_acceptance_v1/execution_review.md`.

These are provided-context generations, not native Agent/MCP host calls or
independent accuracy, stability, causal improvement or cost-saving evidence.
Each question had fresh messages, not a persistent Agent session. Production
defaults, actual SDK candidate noise, host configuration and real data remain
unchanged. No commit/push. Four-question authorization is exhausted; no retries
or additional model calls are implied. Overall six-package objective remains
incomplete, including the newly observed selection/answer consistency gap.

## Post-repair Python 3.10 gate refreshed — 2026-10-08

Reused the existing isolated Python 3.10.11 runtime and verified current-checkout
imports, including its default child-process path. Full current suite:
1075 passed, 10 skipped / 118.55s, exit 0; JUnit 1085 total, 0 failures/errors.
Eight optional answer-model and two tokenizer checks skipped for missing
Transformers. Post-repair package line coverage 86.91%, branch coverage 77.90%;
OpenAI Agents and MCP subprocess measurements included. Exact counts, commands,
hashes and limitations are in TESTING.md.

This advances package 5's local supported-version/coverage evidence, not the
whole six-package objective. No new production/test changes, runtime install,
paid request, real-data operation, commit/push or hosted CI. Current 3.11/3.13,
independent semantic benefit and the separately authorized model acceptance
remain open. Python 3.14 lacks test dependencies and was not tested.

## Exact-ID order gate strengthened — 2026-10-08

Follow-up within the confirmed public adapter/storage seam checks exact
eight-character ID priority for both earlier and later creation times relative
to long IDs sharing the prefix. Both pass without further production edits.
Relevant adapter/MCP-ID subset: 44 passed / 5.10s. Nine adapter ID cases now
exist; the prior 1084-pass full run predates this extra parameter. No new
full/coverage/host/model claim, real-data operation, commit or push. Four-case
paid selection validation still awaits separate authorization.

## OpenAI Agents link follow-up completed locally — 2026-10-08

Human confirmed the public adapter/SDK/storage test boundary. Two deterministic
ambiguous source/target cases reproduced successful linking instead of rejection.
Minimal adapter-only repair now prioritizes exact IDs and rejects ambiguous
eight-character prefixes, retaining the existing JSON error convention. Store
and recall expose additive full_id fields for disambiguation. The ordinary
link success test now requires created; eight new public-interface checks verify
no-write rejection, endpoint identity and ID delivery.

43 relevant checks passed / 5.76s; full local Windows/Python 3.12.14 suite:
1084 passed / 124.61s, JUnit 0 failures/errors/skips. TESTING.md records artifacts,
hash and scope. No post-repair coverage, other-version/hosted acceptance, commit
or push. No HTTP/SDK contract changes, model calls or real-user data changes.
Historical row counts are not recomputed from this subtask. Six-package goal,
paid four-case selection acceptance and remaining release/quality gates remain
incomplete; this repair is not evidence of improved semantic memory accuracy.

## Local coverage refresh, open gates retained — 2026-10-08

Full current Windows/Python 3.12.14 coverage run: **1076 passed / 185.06s**,
exit 0; JUnit 0 failures/errors/skips. Package line coverage 4,204/4,839
(86.88%), branch coverage 1,298/1,664 (78.00%); MCP subprocess measurement
included. Artifact paths, hashes and exact command are in TESTING.md. No
production/test changes, paid requests, real database operation, commit or push.

Package 5's current local 3.12 coverage evidence is refreshed; remaining weak
assertions, other-version/full hosted compatibility and publication remain
open. In particular, the OpenAI Agents adapter link test still accepts an
error result; source inspection also finds overwrite-based short-ID resolution
in that adapter. No new collision reproduction or fix is claimed. MCP's earlier
prefix repair does not prove all adapters safe. Do not change the historical
closed/excluded/unclosed row counts on the basis of this run alone.

The separately frozen four-case selection pack remains prepared, not run:
new paid model authorization is pending. Neither local coverage nor the earlier
synthetic date-topic ranking experiments establish answer-quality improvement.
All six work packages retain their original completion conditions.

## Current host/onboarding/regression evidence — 2026-10-07

The package table below is a dated 2026-10-04 audit, not the latest host status.
Subsequent isolated native ZCode acceptance used the explicitly authorized paid
`deepseek-vibe-test/deepseek-flash` route, not the deferred free Start Plan route.
Three new-session, one-recall cases passed external manual answer review:
explicit elapsed duration, ambiguous duration clarification, and empty evidence
without claiming whole-library absence. Each question had separate human
authorization and no retry. These are three selected cases, not independent
accuracy, general applicability coverage or proof of all package-1 conditions.

The external acceptance runner's terminal-event recognition and multi-request
usage aggregation were repaired, tested offline and exercised in subsequent
live acceptance. Original observations and read-only verification are retained
separately in the isolated acceptance workspace; estimates are not provider
bills. Neither a soft timeout nor an Agent-turn reservation is a hard cost cap.
The user-visible TUI session, free-plan route and broader client compatibility
are not established by these separate native sessions.

`GETTING_STARTED.zh-CN.md` now documents the existing MCP enhancement default,
terminal preference/first-use notice, shared-directory scope, current-host model
versus local retrieval, privacy and cost boundaries, and optional strict scope.
No automatic first-use popup or all-feature control panel is claimed.

Fresh full local regression: **1076 passed / 139.46s**, Python 3.12.14, offline
model-hub flags, no coverage measurement. See `TESTING.md` for command scope,
JUnit counts/hash and targeted runs. This is a dirty local checkout, not a
published commit or hosted CI. No commit/push or production data migration was
performed. The six work packages remain open where their original completion
conditions lack evidence, particularly representative applicability controls,
retention/time policy, dense/cold performance, compatibility/coverage gates and
independent algorithm benefit. The 96-row human review remains paused/unfilled.

## Six-work-package completion audit — 2026-10-04

Newest package-1 experiment: human approved a separate CUDA environment;
GPU tensor check and cached SmolLM2-1.7B FP16 load succeeded. Same frozen prompt,
12 original cases, all 12 parse-error fallback (C06 reached token cap); raw choices
also point to old/inapplicable facts. Environment works, semantic/protocol quality
does not. First outputs and resource evidence: results/smol_gpu_selection_12_first.md.
No production change, final-answer quality proof or default enablement. Original
CPU .venv retained; runtime dependencies downloaded, no new model weights.

Latest package-1 diagnostic: the now date-bound 12 original cases were actually
run through cached local Qwen2.5-0.5B with one frozen prompt and independent chat
calls. Eight structurally accepted (six empty, two nonempty), four fallbacks;
C01 still loses new-value evidence and C12 accepts inapplicable test-environment
evidence. No final answers or independent accuracy score. Prompt/model pair is
not eligible for production defaults. Source, first raw responses, cost and
limits: results/dated_local_selection_12_first.md. No parser relaxation/retry,
paid API, production change or new full-suite/coverage run in this experiment.

Scope remains the six user-prioritized packages, not a goal limited to passing
tests or improving graph latency. None is proven completely closed:

| Package | Current evidence | Remaining completion condition |
|---|---|---|
| 1: failed memory tasks | Current C01 omission reproduced; existing five-candidate boundary includes m2; two actual offline 0.5B attempts failed structural selection, second raw choice was old m1 | Verified applicability selection/final answers across current, historical, planned, scope/conflict and paraphrase controls; no oracle labels or prompt-tuned single-case claim |
| 2: onboarding/host/cost | Terminal settings exist; no completed current real-host inference/authorization/usage acceptance | User must resume deferred ZCode/Start Plan acceptance; keep Codex config protected and no paid fallback |
| 3: history/time/forgetting | Human-approved read-only whole-file admin audit implemented; seven temporary-DB checks pass, including committed WAL history; legacy STALE transition/time provenance remains absent | Agree retention/time policy and backup/apply acceptance; real database migration requires separate authority |
| 4: performance | Trace incident-edge read and per-call PPR transition reuse implemented; chain/star result comparisons, Python allocation diagnostics and latest 989-test regression | Dense/cold/resident memory, arbitrary graph behavior and measured incremental memory tradeoff remain; do not close original two rows from a star fixture |
| 5: test/release gate | Human-approved public MCP/HTTP test remediation: health readiness, ephemeral port, target-ID recall assertions, unconditional directed link and strict missing-content error; 69 targeted checks pass on 3.10 | Remaining weak assertions, current full compatibility/coverage gates and authorized publication remain |
| 6: algorithms/models | Default MCP auto-graph off; Louvain/Learner primary-path and independent-benefit gaps recorded | Reference/feedback test boundary and independent relation/task-benefit evidence needed before default integration or model upgrade |

Human explicitly approved the admin and public-adapter test seams, then resumed
implementation. Automatic goal continuations alone are not approval. Start Plan and 96-row human review remain
explicitly deferred; repeated local tests cannot substitute for them. Original
44 closed / 9 excluded / 12 unclosed retained, not a new row-by-row count.
No commit/push, host/provider configuration change or real-data migration.

Newest production addition is the read-only administrator audit: current full
3.12 regression **996 passed / 151.20s**, exit 0; 3.10 targeted audit/adapter/MCP
**69 passed / 10.96s**, exit 0. No fresh coverage. Prior PPR per-call transition reuse:
106 targeted tests then 989 full tests / 121.73s, exit 0. Coverage XML predates both changes.
Detailed evidence: TESTING.md, RETRIEVAL_COST_DIAGNOSTIC.md,
results/fact_selection_current_input_check.md and both c01_local_selection
attempt records. Further single-case prompt iteration or repeated identical
regression is not a memory-effect improvement. Admin/weak-test implementation now
proceeds while host/independent review stay deferred.

## Latest sparse-hydration subtask — 2026-10-03

Human approved existing SDK/storage public-interface tests using synthetic temporary databases. Replaced full-corpus atom hydration only for TF-IDF non-budget retrieval with a fresh complete id/version/content/created_at projection and on-demand owned active/warm full records. No persistent mutable-atom cache, corpus/candidate truncation, ranking-formula/SDK-signature change, new dependency, MCP tool/default, cloud call or real-data migration. Budget, dense and fallback paths stay unchanged. Production diff: two files, 44 additions / 7 deletions.

Resource-contract red: two warm 3,000-atom calls allocate approximately 5.17MB, exceeding the 3MiB fixture budget; green after change. Eight new public-SDK checks cover allocation, same/second-connection mutation and reinforcement, caller-owned result isolation, store/delete/history, owner/lifecycle/full evidence/graph trace. Relevant 3.12 subset **102 passed / 11.57s**; full **891 passed / 122.54s**; existing isolated 3.10 subset **102 passed / 5.38s**, current checkout import verified. Initial default-temp run's 18 WinError5 fixture errors are not product regressions or a successful run; new unique roots fix the test environment without deleting old evidence. No new coverage or hosted CI result.

Fixed-ID/time 10k old/new diagnostics: four pairs × 11 calls each side, 88 calls, identical IDs/order and no failures, warm p95 about 118–121ms to 32–34ms (~72% lower). Uncontrolled initial equality trial rejected. Original nine-cell harness repeated after change: 99/99 anchor hits, 100k precision/recall warm p95 **440.173/421.262ms**, sampled peaks **736.03/737.75MiB**. These are bounded synthetic observations; 100k is not a controlled old/new speedup estimate. No independent relevance, SLA or universal memory reduction claim. Non-sampling 10k profile: full conversions 10,005→10 and JSON loads 20,010→20 on this fixture; temporary Python allocation probe approximately 1.51MB after change, not RSS. Full method, historical observations and limits: RETRIEVAL_COST_DIAGNOSTIC.md.

Keep **44 closed / 9 excluded / 12 unclosed**: sparse hydration is one implemented subtask, while dense, disk, graph/high-match and cold/index memory costs remain open. Start Plan and real ZCode model/authorization/usage acceptance remain deferred. Existing uncommitted work and prior evidence preserved, no commit/push.

## Repository privacy audit and accepted public attribution

Verified official Gitleaks 8.30.1 Windows archive checksum, temporary tool only. Current exported snapshot: 337 files, ~6.35MB, zero findings. Git patch scanner: 110 reported commits, zero findings; Git actually lists 111 non-merge commits with file changes, so supplemented with all 715 reachable file blobs and 111 commit objects via stdin (~11.88MB), also exit 0 / zero findings. This closes the static audit procedure, not an absolute secret-absence guarantee. Detailed scope, hashes and safe rerun instructions are in REPOSITORY_PRIVACY_AUDIT.md.

PII heuristics find current/historical synthetic regression literals, example emails and loopback/unspecified bind addresses. Commit metadata contains one non-example-domain mailbox; the human explicitly replied **保留现有署名**. Preserve it, no history rewrite or author-config change. Withdraw the blanket no-personal-information claim rather than pretending a successful secret scan proves it. No raw match, credential, mailbox or signed URL published. No live credential/phone validation, real-data operation, new CI hook/test seam, production mutation, commit/push or full regression claimed. Documentation changes only, diff check passes.

Original audit-procedure/unsupported-absence row now closes: **44 closed / 9 excluded / 12 unclosed**. Admin and weak-assertion test seams still await their distinct human approvals; the attribution answer does not authorize them. Performance measurements remain diagnostic, not fixes. Overall review goal is incomplete.

## Precision/recall cost investigation: full hydration remains expensive

Existing scale scripts measure budget only. Nine isolated-process public-SDK diagnostics now cover TF-IDF budget/precision/recall at 1k/10k/100k synthetic atoms, no graph/auto-edge/Episode, one cold plus ten warm queries. All anchor hits 11/11, failures empty; not independent quality. At 100k warm p95 budget 2.482ms, precision 8056.678ms, recall 8702.513ms; sampled process working-set peaks 142.43/840.53/839.18MiB respectively. Sampling/host-load limitations and reproduction are in RETRIEVAL_COST_DIAGNOSTIC.md.

Separate 10k warm precision profile: corpus hydration 0.220/0.247s, JSON decoding 0.084s, overlapping cumulative costs. Direct TF-IDF encode of 10k×5000 float64 actually allocates 381.47MiB; this is not normal sparse search. A 100k dense batch is an unexecuted arithmetic projection, not proof. Dense semantic models/graph-bearing cost remain open. Do not substitute budget or cache mutable atoms without invalidation. No production/test mutation, new pytest seam, real-data operation, cloud request or commit/push; documentation and local Wiki updated. Both performance rows remain unclosed, counts **43 closed / 9 excluded / 13 unclosed**. Prior administrator and weak-assertion test-boundary questions still await human replies; automatic continuation is not confirmation.

## Hosted CI acceptance after push 53cfcb6

Commit `53cfcb649a547d9f23767c8c6eca72b7661e2af9` was pushed and remote main verified identical. [Run 36818592016](https://github.com/sv8vkwmfr7-create/vibe-memory/actions/runs/36818592016) completed successfully on all four Ubuntu matrix jobs (Python 3.10–3.13). Actual downloaded test logs show 822 passed / 11 skipped each: 50.38s, 62.95s, 75.35s, 65.14s respectively. Skips are eight optional answer-model tests, two optional real-tokenizer tests and one Windows-only working-set measurement. This is not the rich local 833-pass result or optional-model integration proof.

All four coverage ZIPs were downloaded in memory and their SHA256 matched GitHub artifact digests. Each contains only coverage.xml, with nonzero executed lines, MCP measurement and knowledge_pages included. Exact metrics/digests are recorded in TESTING.md. The first anonymous API attempt was rate limited; authenticated archive download initially returned 401 because the credential header followed the signed redirect. Retrying the same artifacts with the API credential restricted to GitHub and an unauthenticated signed archive request succeeded. No credential or signed download URL is recorded. Initial failed access is not counted as verification.

The CI/coverage-artifact row now closes: **43 closed, 9 excluded, 13 unclosed of 65**. Node20 action deprecation and upcoming ubuntu-latest migration are warnings, not test failures. No production change this acceptance pass. Weak assertions/conditional link execution/fixed HTTP startup sleep were confirmed in existing tests; their MCP/adapter/HTTP test boundary was requested and awaits human confirmation. Historical administrator seam also remains awaiting confirmation. Overall repair is incomplete; this acceptance documentation remains local, with no further commit/push.

## Batch 3w: pytest is the test verdict authority

Removed eight obsolete run_all functions and two standalone manual runners from ten existing pytest modules, plus 183 constant per-test success prints: 546 lines removed. Manual lists missed later tests; the two standalone loops could mishandle fixtures or print failure while exiting normally. No new runner or abstraction replaces pytest. Test function signatures, assertions, fixtures and remaining diagnostic/protocol outputs are preserved. Comparison/simulation demonstrations and doctor output assertions remain intentional. TESTING.md documents the supported single-module pytest command; direct execution of the cleaned test files is no longer a supported test path.

Before/after normalized AST fingerprints match for all ten modules, excluding only the named manual runners/main blocks and constant success-print expressions; pytest collection remains **833**. The first raw stdin JSON validation attempt failed to parse and is not counted as success; Base64 transport plus explicit nonzero-exit checks produced the valid comparison. The baseline snapshot is outside Git in a temporary file. Source scan finds no remaining run_all definitions or those success prints/main blocks in the ten modules. No assertion removal or newly skipped test.

Python 3.10.11 changed-module subset **214 passed / 8.44s**; full rich Python 3.12.14 suite **833 passed / 114.21s**, offline model-hub flags, isolated pytest directory. This run did not measure coverage: batch 3v XML remains the last coverage baseline. Diff whitespace check passes. Production behavior, dependencies, schema and retrieval defaults are unchanged this batch. No real-data operation, cloud-model request, commit or push.

The original run_all/print hygiene row closes locally: **42 closed, 9 excluded, 14 unclosed of 65**. Fixture duplication and weak/conditional/sleep assertions are separate remaining rows, not claimed fixed. Historical administrator seam still awaits the human reply to the prior TDD question; automatic goal continuation is not that approval. CI repairs still need authorized push and hosted matrix/artifact verification. Overall repair is incomplete.

## Historical-edge investigation: implementation seam awaiting confirmation

Rechecked schema/GC and ran an actual temporary-file SDK store/collect_garbage diagnostic with a raw edge fixture targeting an already-missing atom: orphan count **1 before, 1 after**, foreign_keys 0. GC's scoped endpoint join excludes it. Schema lacks a stale-transition timestamp; created_at is not a retention clock. Both original historical-governance rows remain open; counts stay **41 closed, 9 excluded, 15 unclosed**. No real user database inspected/changed.

ATOM_EDGE_LIFECYCLE.md records a proposed separate whole-file administrator preview/explicit backup-and-transaction repair seam. Default preview must not initialize schema; valid stale/pending and existing cross-owner history are not orphan deletion candidates. STALE cleanup is deferred pending transition-time/legacy policy. TDD seam confirmation was requested before new tests/implementation; no CLI or cleanup capability is claimed. Previous 3v CI fixes remain uncommitted/unpushed; no new runtime/test/schema change or full-suite result this investigation.

## Batch 3v: actual Python 3.10 verification and minimal CI dependencies

Both repair commits were pushed: `f549f0e6ab20c5434d21aa4c67fe9d728deb4ddf` and `a6000d904227559d7d7ff137dca1cc1aa7793cd0`. [Hosted run 36747296226](https://github.com/sv8vkwmfr7-create/vibe-memory/actions/runs/36747296226) failed: setup/dependency installation succeeded, test command exited 2, and no coverage artifact was created; three jobs were cancelled by the matrix. Public API log retrieval returned 403, so no complete hosted traceback is claimed. A fresh Windows 3.12 environment containing only `.[dev]` reproduced a collection error from the experiment's undeclared sklearn import. Added scikit-learn >=1.2 to dev only, preserving the frozen sklearn stopword rule and its existing test; production dependencies stay unchanged. Do not skip that test just to make collection green.

The first minimal full run then reported 8 failed, 823 passed, 2 skipped / 77.97s: cached model files existed on this host but Transformers was absent. A fixture now checks the two optional runtime dependencies for those eight existing local-model tests. With dependencies absent, these tests explicitly skip; with the normal rich environment, all eight still execute and pass. Existing model-cache checks/assertions remain intact; no production model behavior changes.

The old uv process/session terminated with exit 1 after retries, connection reset and archive extraction failure; it was not restarted on an observation timeout. A separate official [Python 3.10.11 Windows embeddable package](https://www.python.org/downloads/release/python-31011/) was downloaded; its MD5 matches the published `f1c0538b060e03cbb697ab3581cb73bc`. This verifies download consistency, not a signature/security audit or a recommendation to deploy an old patch release. Isolated temporary interpreter/dependencies only, no global install/PATH or user database changes. Runtime: Python 3.10.11, SQLite 3.40.1, numpy 2.2.6, sklearn 1.7.2, pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.2.

Actual 3.10 contention/readonly/WAL/serialization baseline: 2 failed, 38 passed / 2.02s, both failures being tests assuming newer constants/exception attributes. Fix absent-constant removal and assert readonly text on every version, additionally checking code 8 when present; 40 passed / 1.62s. Full execution exposed the same assumption in forgetting/WAL experiment error handlers; reuse the existing lock classifier in these and the disk-pressure handler rather than treating every OperationalError as BUSY. Forgetting red 1 failed / 0.35s, green 1 passed / 0.51s. Disk-pressure 3.10 temporary-file smoke retained/recovered the anchor under an external write lock.

Final minimal **3.10 full: 823 passed, 10 skipped / 72.89s**; skips are eight answer-model and two real tokenizer checks whose optional dependencies are absent. Rich **3.12 full: 833 passed / 168.47s**, followed by the final edited SQLite/forgetting/WAL subset **43 passed / 2.08s**. Offline model-hub flags and isolated coverage/test directories are used. Earlier 3.10 full had two experiment failures and an invalid zero-data coverage report because the embedded interpreter preferred an installed copy; final source path was corrected and a valid fresh report obtained. Do not count either early run as a success. Exact XML metrics/hashes are in TESTING.md. This is Windows compatibility evidence, not Ubuntu matrix, all 3.10 patches or independent memory-quality proof.

Original Python 3.10 SQLite compatibility row closes locally: **41 closed, 9 excluded, 15 unclosed of 65**. Hosted CI/artifact row remains partially repaired until this additional change is pushed, the entire matrix passes and artifacts are inspected. No new production API/schema/default, real-data migration, cloud-model request or further commit/push this batch. Overall review repair remains incomplete.

## Batch 3u: per-instance SDK serialization

Reproduced the shared-connection race with a real temporary WAL database, an external write transaction and an observed SQLite DB-API connection: while recall had temporarily set busy_timeout to zero, concurrent store failed immediately with `database is locked`. Red: **1 failed / 0.27s**. The existing public-operation decorator now admits through WALMaintenance before taking an instance RLock; the lock also applies without maintenance. No new API, dependency, schema or ranking default. Same-thread nested calls remain reentrant and exceptions release the lock. HTTP's existing compound-operation lock is retained.

User-approved SDK/WAL seams cover the race with and without maintenance, readonly exception recovery followed by a different-thread write, nested inject, and a previously admitted nested operation draining while a new call waits for checkpoint. First green **1 passed / 0.37s**; expanded contention/WAL subset **16 passed / 1.60s**. Full Windows/Python 3.12.14 regression with real MCP subprocess coverage: **833 passed / 135.35s**; package lines 4,008/4,636 (86.45%), branches 1,223/1,584 (77.21%). See TESTING.md for the artifact and execution boundary. `git diff --check` passes (existing line-ending warnings only).

The entire call, including embedding/LLM callbacks, is serialized, so other callers of that instance may wait; no latency/throughput guarantee or FIFO policy. Callbacks must not wait for another thread to call the same instance. Direct component/storage access, caller-managed multi-call transactions, component mutation and returned objects are outside this lock. Separate instances have separate locks and still need database/WAL coordination. README records these limits; no universal thread-safety or memory-quality claim.

The original busy_timeout race row closes locally: **40 closed, 9 excluded, 16 unclosed of 65**. Same uv Python 3.10 session/process remains running, with a changed extraction directory but no usable target interpreter/test result; that gate remains open. Hosted CI and historical governance remain open. No real user database, cloud-model request, commit or push was part of this repair. The overall review repair is not complete.

## Batch 3t: truthful public documentation and archive boundaries

README no longer stacks obsolete full-suite counts or presents Phase 0 stars, unbacked LLM percentages/model-size requirements, generic RAG noise or universal competitor superiority as current results. The v3 ablation table now matches all four stored JSON arms, including budget; noise 0.22 is 22%. Bound the artifact to its actual last commit `6a8ad0606dbb5d6d850ffa8c1776c1e86b070430` and SHA256 `c1da44768623ab055f8768af0b0f7124c64631a0888a761e5821ade4db38d65f`, explicitly not a recorded execution-source commit. This turn did not rerun that benchmark or fabricate provenance. The current local test baseline stays centralized in TESTING.md; old STATUS entries are labeled historical, including superseded no-public-benchmark/no-subprocess-coverage statements. Public-data retrieval pilots are not final-answer or independent human evaluation.

PROMO's old templates are replaced with concise Chinese/English descriptions, working source-install/SDK examples and explicit onboarding, model costs, MCP auto-edge and framework adapter limitations. HINDSIGHT_COMPARISON withdraws stale feature denials, unverified vendor numbers and rankings; no new competitor recommendation or measurement was substituted. Phase 0/development prose is retained as historical, unverified observation, with private Wiki links and the named private gateway address removed. Historical experiments now have unique numbers 1–15; conflicting E/F versus A–D findings are scoped to their backend/configuration rather than merged into a perfect-result claim. No Git history rewrite or original user audit-report edit.

Validation: all four README metric rows and the artifact hash match the actual JSON; local Markdown links in all six edited public docs resolve; experiment numbering is exactly 1–15; tracked Markdown and the current repository text scan have no matches for the reported gateway host or private Wiki-link form. This bounded scan is not a complete secret/PII audit and does not clean already published/history copies. Related adapter/doc/RRF regression **32 passed / 1.34s**; actual offline quickstart and the PROMO SDK call both pass using temporary databases. No production code, dependency, schema or retrieval-default edits this batch; no cloud/model call or commit/push. The previous full coverage baseline remains **829 / 226.92s** from batch 3s, not a new full run in 3t.

Five original documentation rows close locally: README counts/ablation, synthetic-result competitor claims, unsupported Phase 0/LLM scores, stale PROMO numbers, and public-doc link/domain/duplicate-heading hygiene. Counts: **39 closed, 9 excluded, 17 unclosed of 65**. Hosted CI/artifact execution, complete secret audit, historical-data governance and independent quality gates are still pending. The same uv Python 3.10 process/session remains live; no completed runtime or test evidence, so that gate remains open. The full repair goal continues.

## Batch 3s: coverage baseline including real MCP subprocesses

CI now invokes existing pytest-cov with package line/branch reporting and saves only `coverage.xml` in a uniquely named artifact per Python 3.10–3.13 job, even on test failure; missing XML is an upload error. The workflow YAML and actual coverage configuration pass local contract checks. No arbitrary minimum coverage threshold or low-coverage exclusions were added. [Testing and coverage](TESTING.md) documents commands, exact dependencies, baselines, subprocess caveats and hosted-CI limits; README links it.

The first local run passed **828 / 180.30s**, but pytest-cov 7 did not collect subprocess executions: 3,863/4,635 lines (83.34%), 1,182/1,586 branches (74.53%). Following official coverage configuration, dev-only dependencies require pytest-cov >=7 and coverage[toml] >=7.10; `patch=["subprocess"]`, branch measurement and relative paths are configured. Production dependencies are unchanged. The existing MCP test client now closes stdin and waits for normal EOF exit (bounded kill-and-fail cleanup on timeout), instead of force-terminating the server before coverage can flush. This changes only test lifecycle, not production SDK/MCP behavior. The user approved this existing stdio seam before its new test; red **1 failed / 0.62s**, exit code 1 instead of 0; fixed real MCP/doctor subset **43 passed / 63.40s**.

Final full local run: **829 passed / 226.92s**, Windows/Python 3.12.14 with offline model-hub flags, isolated coverage database and pytest temporary root. XML: **4,007/4,635 lines (86.45%), 1,225/1,586 branches (77.24%)**; rounded combined score 84%. MCP: 159/167 lines (95.21%), 57/62 branches (91.94%). The XML hash and exact runtime/dependency versions are recorded in TESTING.md. `knowledge_pages.py` remains 0%; no module is omitted to inflate results. Improved subprocess measurement is not improved memory quality, security proof or all-version/model coverage.

The original CI/coverage row is **partially repaired, hosted matrix/artifact verification pending**: the changes have not been committed/pushed or run on GitHub. Therefore original counts stay **34 closed, 9 excluded, 22 unclosed of 65**. Python 3.10 uv provisioning is still live at the same process/session, with no completed interpreter or tests; its compatibility row remains open. No real-data migration, runtime dependency/schema/default changes, cloud model request or commit/push. The broader repair goal remains active; next gates are real 3.10 competition/read-only/WAL verification, hosted CI after authorized push, and historical-data governance.

## Batch 3r: explicit TF-IDF fitting contract and runtime verification boundary

Direct `TfidfProvider.encode` fits the first batch only; later encoding preserves the vocabulary and gives unseen terms zero weight. Method docs and README now require explicit full-corpus `fit` and recomputing old vectors after refitting. `encode_query` never fits and returns a zero-length vector before fitting. Production SDK recall already fits changed active corpora using atom ID/version cache keys; the added store/recall test verifies newly stored vocabulary is learned. No runtime behavior, ranking defaults or dependencies changed.

Four contract checks initially produced **1 failed, 3 passed / 0.43s** (missing method documentation, not broken SDK refitting). Together with a new actual SQLite BUSY/READONLY runtime check and existing contention/WAL checks: **40 passed / 1.35s**. Full local regression: **828 passed / 163.28s**, Windows/Python 3.12.14, offline model-hub mode, isolated temporary directory, including unpushed experiments. This is not published CI, independent retrieval-quality evidence or Python 3.10 verification.

Python 3.10.21 environment provisioning through uv is still running, with extracted files observed in its temporary directory; no completed interpreter or 3.10 test result yet. The new SQLite check exercises real exceptions, not synthetic error codes, but has only run on 3.12 so far. Keep the original 3.10 row open, including old tests directly assuming newer SQLite constants/attributes. Do not weaken their assertions without an actual baseline. One original TF-IDF contract row closes: **34 closed, 9 excluded, 22 unclosed of 65**. No real-data migration, cloud model request, commit or push. Next: finish the separate 3.10 environment and run contention, read-only propagation and WAL recovery before closing its compatibility row.

## Batch 3q: truthful reranker and framework adapter contracts

Fusion/strategy docstrings now distinguish the production cosine/RRF `rerank_by_similarity` from the pass-through `Reranker` compatibility class. Removed advertised nonexistent scorer classes; the placeholder's optional query encoding, discarded vector and error pass-through are documented rather than rewritten. No ranking algorithm/default or class runtime behavior changes.

OpenAI adapter docs import the existing `openai_agents` module and explicitly wrap the factory's plain functions with `agents.function_tool`. Existing direct-function API stays dependency-free. LangChain docs/README no longer claim BaseMemory inheritance, universal chain compatibility or LangGraph state/checkpoint support; the supported path is explicit load/save wiring in a RunnableLambda chain. [Adapter contracts](ADAPTER_CONTRACTS.md) records exact versions and reproducible offline smoke, rather than promising a new native BaseMemory implementation.

Five added checks: initial **3 failed, 2 passed / 0.44s** (false docs with current runtime behaviors reproduced); corrected adapter/RRF regression **32 passed / 1.62s**. Full local regression: **823 passed / 168.22s**, Windows/Python 3.12.14, offline model-hub mode, isolated temporary directory, including unpushed experiments (not published CI or independent memory-quality proof).

Separate real-framework smoke `experiments.adapter_framework_smoke` passes with `openai-agents==0.22.3` and `langchain-core==1.6.6` installed only in a temporary target directory. Seven FunctionTool schemas are built; the actual Agents Runner dispatches store then recall using a scripted Model; a real three-step Runnable chain explicitly reads/responds/saves and sees saved content on its second invocation. Cloud model calls are zero, tracing disabled and external socket connects blocked. Setup failures (unprocessed pywin32 paths, overbroad blocker rejecting Windows asyncio loopback) were corrected before the successful run; no evidence is inferred from those failures. This does not verify cloud credentials/model-selected tools, streaming, legacy BaseMemory, LangGraph or all SDK versions. No production dependency/schema change, user-data migration, commit or push. Three original contract rows close: 33 closed, 9 excluded, 23 still unclosed of 65. The broader repair goal remains active.

## Batch 3p: explicit and revision-bounded custom model code trust

`TransformersProvider` no longer hardcodes `trust_remote_code=True` for tokenizer and model loaders. Keyword-only `trust_remote_code=False`, `revision` and `code_revision` preserve existing positional arguments and factory forwarding. Boolean trust and revision types are validated at construction and again before loading. Opting in requires a full 40-hex model commit; custom-code revision also requires a full commit and defaults to the model commit. For code in another repository, supply its separately reviewed commit. No opt-in retry occurs after denial. Untrusted native models may still use a branch/tag or the upstream default revision; this is not a claim that every default model load is immutable.

[Hugging Face's custom-model guidance](https://huggingface.co/docs/transformers/models#custom-models) recommends caution and commit pinning when loading repository-defined code. Opt-in permits custom Python execution with the current process's permissions; a SHA is not a malware audit, sandbox, signature or immutable-local-file guarantee. Local directories also require pin metadata for opt-in, but the upstream loader does not lock their file contents; use a reviewed controlled copy. Artifact serialization and third-party dependency security are outside this patch. No remote revision SHA was invented for the user, and no remote custom model was downloaded or executed.

Initial red: **24 failed / 0.51s**, including hardcoded trust and missing parameter/validation failures. Expanded targeted LLM/reflector/observability regression: **105 passed / 15.01s**, including 26 new checks. Two real installed-Transformers tokenizer sentinel checks confirm default denial before the synthetic custom module executes and explicit opt-in reaching its deliberate RuntimeError; module copies use an isolated temporary cache, no network/side effects from the sentinel. These optional-dependency checks did run locally, not skip. Actual offline CPU Qwen2.5-0.5B-Instruct snapshot `7ae557604adf67be50417f59c2c2f167def9a775` loads and completes a 2-token chat through the provider with trust disabled; this verifies the existing local-native path, not model answer quality or every checkpoint. Existing dtype/generation deprecation warnings remain, without unrelated parameter rewrites. Full local regression: **818 passed / 155.36s**, Windows/Python 3.12.14, offline model-hub mode, isolated temporary directory, including unpushed experiments (not published CI or independent memory-quality evidence). The original trust row closes: 30 closed, 9 excluded and 26 still unclosed out of the original 65 rows. No schema/dependency, cloud model request, real-data migration, commit or push.

## Batch 3o: observable, privacy-bounded fallback failures

All four retrieval strategy catch paths now return a per-call `failures` list of fixed `{stage, reason}` labels; empty-corpus and no-failure results return an empty list. SDK accumulates strategy counts, and embedding-cache encoding/persistence failures are counted without failing the primary write. Clearing a failed semantic query vector prevents later reranking of incomplete semantic state. Requested `strategies_used` semantics stay unchanged; failures identify execution errors, not low relevance or successful matches.

Reflector keeps its list-returning fallback API, but `reflector.stats()["degradation"]` now distinguishes provider, parse and insight-store failures. Invalid JSON or a non-object/missing/non-list `insights` structure (including non-dict entries) is a parse failure; valid `{"insights": []}` is not. Existing direct/fenced/embedded JSON extraction stays supported. Further field validation, topic reflect counter consistency and independent insight-quality evaluation are not claimed here.

HTTP `/recall` and `/session/start`, and MCP `vibe_recall` and `vibe_session_start`, preserve the per-call list. HTTP `/stats` and MCP `vibe_stats` expose a safe cumulative `failures` map from SDK metrics. `mem.stats()["metrics"]["failures"]` is also available locally. Categories are only `timeout`, `connection`, `storage`, `invalid_data`, `os_error`, `unexpected`; unknown stages collapse to `other`. New diagnostic fields never retain exception messages, custom class names, queries, keys, tracebacks or IDs. The safe counter map filters arbitrary legacy degradation names rather than forwarding them to clients. Legacy local `degradation` remains unchanged. Labels are coarse, in-memory, resettable and bounded for these new paths; this is not durable monitoring, a concurrency guarantee or a global audit of existing transport error replies. Reflector counters are separate from SDK cache/retrieval counters.

Initial red: **21 failed / 0.66s**. Expanded core checks: **100 passed / 17.93s** (34 added checks); core full regression **789 passed / 164.27s**. Three transport/filtered-counter checks then reproduced missing exposure: **3 failed / 0.93s**. Final targeted SDK/privacy/metrics/reflector/loopback HTTP/real subprocess MCP regression: **156 passed / 36.89s**, including 37 new checks. An earlier run had **85 passed, 2 setup errors / 50.33s** due to access denial on the existing default pytest temporary root; it ended before the isolated-directory rerun. Final full local regression: **792 passed / 182.88s**, Windows/Python 3.12.14, offline model-hub mode, isolated temporary directory, including unpushed experiments (not public CI or independent memory-quality proof). The original bundled silent-failure row closes: 29 closed, 9 excluded, 27 still unclosed out of 65 original rows. No dependency/schema, external model request, real-data migration, commit or push; no ranking defaults or strict mode added.

## Batch 3n: honor chunk-size and explicit novelty parameters

`max_chunk_chars` now bounds each non-user message's body by lossless Python-character slicing, with per-piece summaries/tags/IDs and monotonically expanded Episode positions. Unsplit source positions remain unchanged; original-message context is retained without mutating input. Positive integer chunk limits and nonnegative integer context windows are enforced. The body bound does not bound context size or total message volume, and slicing may cross word/grapheme boundaries; it is not semantic chunking.

SDK batch writes filter the complete sanitized response before splitting via `filter_routine=True`, preserving meaningful tail fragments such as standalone `已`. Direct chunking defaults to retaining routine messages, as before. Privacy preflight still scans all original messages before any write. Long SDK batch replies now create multiple atoms instead of an oversized atom; single `store` is unchanged.

Explicit `previous_atom` uses character-level `1 - SequenceMatcher.ratio()` novelty against `threshold` in [0,1]; errors/corrections still take precedence and complete acknowledgments remain rejected. With no previous atom, existing default admission remains. SDK does not automatically activate novelty comparison. This is not embedding similarity, contradiction detection or independently verified memory quality; SequenceMatcher has worst-case quadratic cost and its default autojunk behavior remains.

Original 12 checks: **12 failed / 0.44s**; repaired initial regression **77 passed / 0.55s**. Expanded 21 new checks cover body reconstruction, Unicode/empty/exact limits, invalid config/threshold, threshold sensitivity, untouched direct-call filtering defaults, SDK fragment retention and tied-timestamp persistence/Episode pointers. Chunking/privacy/Episode/causal/SDK regression: **145 passed / 52.45s**. Full local regression: **755 passed / 156.13s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode, including unpushed experiments (not public CI or independent memory-quality evidence). The original bundled `previous_atom/max_chunk_chars` row closes: 28 closed, 9 excluded and 28 still unclosed out of the original 65 rows. No schema/dependency, model call, real-data migration, commit or push. Config validation applies at construction; later attribute mutation is not newly validated.

## Batch 3m: numerical stability, legacy lock handling and contract checks

Decay prediction uses the sign-stable sigmoid form, preventing negative finite scores from overflowing while preserving the configured range and ordinary-score results. SDK recall and WAL checkpoint share a small lock-error predicate: primary/extended SQLite BUSY/LOCKED codes take precedence, and only known SQLite lock-message prefixes are accepted when code attributes are absent. Non-lock errors still propagate; rollback, timeout restoration and maintenance admission recovery remain tested. No new serialization/thread-safety guarantee is introduced.

Python documents error-code attributes as [added in 3.11](https://docs.python.org/3/library/sqlite3.html#sqlite3.Error). Local runtime inventory contains only 3.12/3.14: missing-code/constant behavior is simulated, not actual Python 3.10 execution. The original supported-version review row remains partially open until real 3.10 verification.

Reflector factory docs now state the actual explicit hosted-provider contract: no DeepSeek alias/environment-key lookup is promised; OpenAI-compatible endpoints use `openai`, explicit endpoint/key/model, and custom providers can be passed directly to `Reflector`. Three no-network constructor checks preserve supported providers and unknown-alias rejection. The duplicate SDK defense assignment and identical degradation branches are removed. Six direct RRF checks cover empty inputs, one-based ranks, rank-not-score semantics, overlap, weights/top-K, ties, missing weights and hashable IDs without changing the fusion algorithm. This is core direct coverage, not a claim that all malformed-input or retrieval-quality concerns are solved.

Original numerical/legacy-path red: **6 failed, 8 passed / 0.28s**. Expanded stability, contract, RRF, real lock/maintenance, SDK metrics/privacy regression: **97 passed / 2.03s**, including 32 added checks. Full local regression: **734 passed / 141.21s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode, including unpushed experiments (not public CI or independent memory-quality evidence). Four original rows close: sigmoid overflow, duplicate code, reflector documentation mismatch and absent direct RRF tests. Legacy-runtime verification is not counted closed. No schema/dependency, cloud/model call, real-data migration, commit or push; no retrieval defaults changed. Finite-score sigmoid stability does not validate arbitrary NaN model state/configuration.

## Batch 3l: bound runtime metric histories

Stdlib deques retain at most 1,000 samples per latency operation, recall-result series and graph-snapshot history, and 20 phase-history records. Operations, graph snapshot/phase record counts and graph peaks remain cumulative since `reset`; graph peaks are maintained separately from evicted snapshots. Recall `total_recalls` remains cumulative and new `sample_count` identifies the recent distribution window. Latency `count` describes retained samples. New `sampling` metadata states the window policy. Reset clears both cumulative and window state, and standard SDK/HTTP/MCP stats retain JSON-compatible output.

Original functional red: **4 failed, 1 passed / 0.20s**, using 1,100 records without sleeps/model calls. Five new checks cover eviction, exact percentiles, cumulative/window separation, historical peak retention, reset/re-record and context-measure/SDK output. Metrics/SDK/HTTP/real-MCP regressions: **97 passed / 19.17s**. Full local regression: **702 passed / 89.87s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode, including unpushed experiments (not public CI or independent memory-quality evidence). No external monitoring service, dependency, schema, real-data migration, commit or push.

This bounds histories for a fixed set of series, not total memory under unlimited caller-supplied operation names, edge labels/sources or degradation types. No new thread-safety guarantee or process-RSS/load benchmark is claimed. After the window fills, latency/result distributions intentionally describe recent samples rather than all-time data; graph peaks and cumulative counters retain their prior scope. Phase `transition_count` continues counting calls, including repeated phases, not deduplicated transitions.

## Batch 3k: narrow lexical causal signals

The shared `_has_causal_signal` recognizes Chinese causal connectors (including `故而/故此`, not bare `故`) and complete English connector words using stdlib Unicode word boundaries. It no longer treats generic action/update verbs, sequence terms or bare `结果` as causal evidence. This affects future same-session rule building, cross-session rule classification and LLM-failure fallback; LLM-success parsing, thresholds, directions and stored edges are unchanged.

Original 35 checks: **19 failed, 16 passed / 0.23s**, including a real in-memory SDK batch with a false causal edge. Final 37 new checks add synthetic provider-failure coverage without network calls. Signal/building/indexer/LLM/history/ingestion regressions: **137 passed / 7.92s**. Full local regression: **697 passed / 92.72s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode, including unpushed experiments (not public CI or independent memory-quality evidence). No schema/dependency, real-data migration, commit or push.

This remains a lexical heuristic, not pair-level causal proof. Whole-word `so` can be noncausal; negated/quoted connectors and unrelated clauses are not interpreted. Chinese phrase matching still has semantic ambiguity, and implicit causal expressions without these connectors may be missed. Historical wrongly labeled edges need a separate audited reclassification plan; none were rewritten here.

## Batch 3j: filter complete acknowledgments, not substrings

`should_ingest` now compares the entire lowercased reply after stripping boundary whitespace and common English/Chinese sentence punctuation, against the existing short acknowledgments plus the previously tested `OK, got it`. Meaningful text containing `token`, `webhook`, `book`, or Chinese acknowledgment/progress substrings is retained. Error/correction precedence is unchanged. SDK `store_batch` shares this decision; direct `store` bypasses it and is unchanged.

Original functional red: **10 failed, 10 passed / 0.22s**, including a real in-memory batch that previously persisted no rows. All 20 new checks and chunking/SDK/privacy/edge-history regressions pass: **83 passed / 7.15s**. The persistence assertion compares sorted content lists rather than unrelated timestamp-tie ordering. Full local regression: **660 passed / 89.74s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode, including unpushed experiments (not public CI or independent memory-quality evidence). No semantic model, dependency, schema, real-data migration, commit or push. This is a deterministic allowlist, not semantic importance or contradiction detection; blank-input handling, unused `previous_atom`/threshold and chunk-size policy are not repaired. Historical omissions require source-backed reimport rather than automatic reconstruction.

## Batch 3i: preserve same-session edge history

Both SDK automatic same-session insertion paths now use an atomic directed-pair `ON CONFLICT DO NOTHING`, reusing the existing SQL serializer. Existing rows in every status remain byte-for-byte unchanged; new rows alone increment SDK edge metrics. Explicit replacement/link and indexer policies are unchanged, with no new schema/dependency or real-data migration.

Original functional red: **3 failed / 0.17s**. Five new checks cover all statuses, repeat building, the public store path, directed pairs, explicit replacement compatibility and unrelated ID collision errors. Targeted lifecycle/indexer/Episode/SDK regression: **65 passed / 10.51s**. The first public-path fixture observed an extra edge under tied atom timestamps; fixed source timestamps now isolate history preservation without weakening that assertion. Tie-order policy and whole-session rebuilding cost remain separate limitations. Full local regression: **640 passed / 110.07s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode, including unpushed experiments (not public CI or independent memory-quality evidence). No commit or push.

This is a local repair record, not a release or a retrieval-quality benchmark.

## Batch 3h: completed-version template suppression

Augmentation now uses the existing scoped bootstrap marker: completed seed versions use persisted records only, never template fallback. This is an intentional whole-version fallback policy, not a new per-fact registry. Uninitialized versions/other owners/changed documents still augment. Every fallback attempt checks the durable marker, covering other connections with cached templates and reopened managers without new schema.

Original red: **2 failed / 0.32s**, repaired seed/bootstrap/cold-start regression: **27 passed / 0.45s**. Expanded SDK, real MCP, rollback/scope/restart/cached-connection and synthetic forgetting-trace regression: **94 passed / 13.79s**, including six new checks. Final full local regression: **635 passed / 90.66s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode; includes unpushed experiments, not published CI or independent quality evidence.

The old trace requiring template recall residue failed after repair (one failed / 0.38s). Its assertions now explicitly require template/prompt seed residue false; the report keeps measured fields and updates its prose. Surviving batch context/reimport/merge provenance residual assertions remain unchanged. No new dependency, model call, retrieval-mode/threshold default, real-data migration, commit or push. This is not complete erasure: new seed versions, unmarked legacy data, trusted template readers/raw writes, RAM, context, logs/backups remain outside the boundary.

## Batch 3g: seed defense and transactional durable bootstrap

Seed content/summary now reuse the shared text preflight before template caching or persistence; SDK passes its defense, direct managers default to redact, unknown partitions fail explicitly. The additive seed_bootstrap table keys initialization by tenant/agent/canonical-document digest. Clones and success marker commit atomically; repeat connections/restarts return no new clones, and deleting a clone does not reopen the same completed initialization. Changed documents form new versions; this is not old-version migration or hot reload.

Original red: **4 failed / 0.30s** (privacy loading/block, restart duplication, partial SQL failure). Repaired original/SDK/privacy regression: **40 passed / 0.30s**. Expanded scope, two-connection race, caller-transaction, warn/custom/exclusion, version-change and SDK trace regression: **71 passed / 0.88s**, including eight new checks. Final full local regression: **629 passed / 90.76s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode; includes unpushed experiments, not published CI or independent quality evidence.

The old forgetting trace failed with IndexError because it assumed a restarted bootstrap always returned a restored clone. It now records zero rebootstrap clones and false for the retained legacy restoration field. The still-unfixed cached template recall/prompt residual assertions remain true. No new dependency, model call, retrieval default, real seed/database migration, commit or push. See PRIVACY_SCANNER.md for additive schema, legacy first-run duplication, version accumulation and incomplete-erasure boundaries.

## Batch 3f: SDK text write-path defense preflight

One shared SDK scanner now covers store content/explicit summary/contexts and supplied update content/summary before mutation. Batch message contents are scanned on copies before chunking, summary truncation and context copying, then generated atom text is checked before any write. Block-mode rejection leaves no partial batch memory/edges/Episodes/store counters; this preflight is not atomicity for arbitrary later database errors. Block preflight intentionally includes user-only and otherwise filtered messages.

Initial red: **12 failed / 0.22s**, no fixture errors. Original write-path/scanner/SDK/ownership regression: **72 passed / 9.37s**. Expanded SDK defense, adapter, HTTP and real MCP regression: **140 passed / 21.10s**, including nineteen new checks. Final full local regression: **621 passed / 106.54s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode. Includes unpushed local experiments; not published CI or independent quality evidence.

Tests use synthetic strings and in-memory SQLite/TF-IDF. WARN/custom/exclusion contracts and update ownership remain covered; refusal errors omit raw matches. No new SDK envelope, dependency, model call, retrieval default, real-data migration, commit or push. Metadata/raw storage/seeds and historical unchanged/derived records remain outside this repair; see `PRIVACY_SCANNER.md`. This is bounded write-path coverage, not complete DLP/erasure or independent retrieval-quality evidence.

## Batch 3e: backpressure return values and counters

Full-queue replacement used to enqueue the incoming candidate but return False and count two losses for one eviction. It now propagates the actual admission result and counts each eviction/refusal once. Original DROP_OLDEST, DROP_LOWEST and non-waiting BLOCK behavior is unchanged. Queue capacity must be a positive integer and strategy a known value; invalid configuration fails explicitly.

Initial red: **7 failed / 0.21s** (two wrong admission results, five invalid-configuration checks). Initial regression: **42 passed / 0.21s**. Expanded regression: **71 passed / 6.97s**, with fourteen new tests covering successful replacement, equal/lower refusals, BLOCK refusal, low-score filtering, duplicate updates, batch results, consumption/clear/reset and compaction. Final full local regression: **602 passed / 90.29s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode. Includes unpushed local experiment tests; not a published CI or independent quality result.

Counter semantics and remaining concurrency/RAM/retry boundaries are in `ATOM_EDGE_LIFECYCLE.md`. In particular dropped_count includes incoming full-queue refusals, not only accepted work removed later; below-threshold filtering remains uncounted. No telemetry field, dependency, model call, retrieval default or backpressure policy is added. No real database change, commit or push in this batch.

## Batch 3d: bounded SDK Episode rebuilding

Previous repair batches were pushed to main as `505792e`; its isolated staged snapshot passed 533 checks. Other local experiments/results and Wiki were not included.

The builder rejects mixed owners/sessions and duplicate atoms, and derives a UUID5 identity from owner/session/first member. SDK rebuilds a copy and replaces the scoped session snapshot in one transaction after comparing the complete live atom input. Obsolete groups are removed, member pointers persist, original positions retain timestamp-tie ordering, matching-ID usage/community metadata survives and SQL failures roll back. Below the existing three-atom SDK threshold, obsolete groups are cleared without creating new Episodes.

Initial red: **3 failed / 0.19s**, including six repeated calls producing six rows. Initial related regression: **56 passed / 6.76s**; expanded lifecycle/isolation/trace regression: **41 passed / 6.72s**, including nine new checks. First full local regression: **588 passed / 94.48s**. After tightening complete-snapshot validation, the nine new checks passed **0.18s**; final full rerun: **588 passed / 91.69s**, Windows/Python 3.12.14, isolated temporary directory, offline model-hub mode. This includes unpushed local experiment tests; it is not published CI or independent retrieval-quality evidence.

Stable identity is conditional on the same leading member, not permanent across regrouping/deletion/merge. Every call still scans/sorts/replaces the whole session: bounded stored rows, not incremental or fixed-time computation. Legacy random-ID Episodes are replaced only on owning-session rebuild; their statistics are not transferred to new identities. No production migration, dependency, model call, retrieval-default change or new commit/push in this batch. See `ATOM_EDGE_LIFECYCLE.md` for trusted raw APIs and remaining provenance/erasure/concurrency limits.

## Batch 1a: configuration writes and safe deletion

- `vibe-init` now validates JSON object shape and TOML before changing configuration. Invalid files stop configuration instead of being replaced as empty files.
- Claude project configuration uses `.mcp.json`. When only the legacy `.claude/mcp.json` exists, its entries are copied to the new file; the legacy file is retained and reported for manual review.
- Existing configuration and instruction files are backed up as `<filename>.<unique-id>.bak` before changes. Writes use a flushed temporary file in the same directory and atomic replacement. Identical bytes are not rewritten; failed backup or replacement leaves the original file unchanged. Symlink destinations are refused.
- Codex command and arguments are escaped and parsed as TOML, including Windows paths and quoted values. An existing `vibe-memory` table is retained; a comment mentioning that name no longer prevents installation. Python 3.10 uses the conditional `tomli` dependency, while 3.11+ uses `tomllib`.
- SDK `forget` resolves exact IDs first, checks both tenant and agent ownership, and accepts a prefix only when it is at least eight characters and uniquely identifies an atom in that scope. Invalid input, missing IDs, ambiguous prefixes, and foreign ownership return `False` without deletion.
- MCP and OpenAI adapter deletion now delegate to this SDK contract; their first-prefix-match fallback has been removed.

Backups may contain sensitive configuration. Keep them private and restore deliberately; do not commit them. Atomic replacement protects individual files, not a multi-file transaction or concurrent external configuration editors. Generated configuration passing a parser is not proof that a real coding-agent session connected.

The original temporary regression run contained fixture mistakes; those were fixed before recording the functional red result: **15 failed, 15 passed, no fixture errors**. After implementation, the same 30 checks passed. Expanded configuration, deletion, real MCP stdio, adapter and doctor regression: **95 passed / 13.85s** on Windows/Python 3.12.14. Full local regression: **481 passed / 82.93s**, including 35 new checks and the pre-existing local experiment tests. This is not a published-commit CI count or independent memory-quality evaluation.

## Batch 1b: scoped history, GC and graph statistics

- Session queries now default to the storage tenant and accept an explicit agent filter. SDK `history` always supplies both tenant and agent; an empty session ID is no longer treated as “all sessions.”
- A shared `get_edges_by_agent` query checks the edge tenant and both existing endpoint atoms' tenant/agent. SDK active/pending edge counts, indexer graph counts, graph-size snapshots and GC sparsification use this query.
- Statistical/maintenance queries deliberately include cold and archived endpoints. Recall's active/warm-only edge query is unchanged. Orphan and inconsistent legacy edges are excluded, not physically deleted.
- Automatic Episode aggregation now uses the same scoped session query, preventing foreign atoms from entering an Episode when session names collide. Episode deduplication and general mixed-input builder behavior remain separate open issues.

After correcting synthetic fixture pairs to respect the existing unique endpoint-pair index, the final red run had **11 failures, no fixture errors**. The repaired and expanded isolation suite passed **14 checks / 6.45s**. SDK, tenant, GC, indexer and real MCP regression passed **136 checks / 13.44s** before the last three expanded checks were added. Final full local regression: **495 passed / 78.96s** on Windows/Python 3.12.14. These checks establish the tested isolation behavior, not independent retrieval quality or a published CI count.

This batch used a temporary shared SQLite database with two tenants and two agents, identical session names, active/pending/stale edges, malformed cross-scope edges, an orphan and cold/archived atoms. No cloud/model calls or production database migration were required. Trusted low-level all-edge APIs remain available; this is not a blanket claim that every storage method or mutation path now enforces SDK ownership.

## Batch 1c: update, migrate and link ownership

- SDK `update` and `migrate` require the atom's tenant and agent to match the instance. `link` requires both endpoints to match both values, including the case where both endpoints belong to another agent in the same tenant.
- `update` accepts only `content`, `summary`, `tags`, `scope`, `confidence`, `weight` and `decay_rate`. Unsupported fields raise `ValueError` before any mutation. IDs, ownership, sessions, partitions, timestamps, Episode references and version counters cannot be changed through arbitrary keyword arguments. Partition changes remain available through `migrate`.
- This also prevents a loaded owned atom's `id` being changed to another existing atom's ID before the storage UPDATE, which could previously overwrite the other row.
- MCP link failure guidance now describes the current tenant/agent requirement. A real stdio test verifies rejected foreign-agent links leave the physical edges table empty.

Functional red result: **15 failed, 9 passed**, without fixture errors. After repair, the 24 mutation checks and SDK/tenant/MCP/adapter regressions passed together: **132 passed / 17.31s**. One additional real MCP check was then added. Fixtures use synthetic atoms in a temporary shared SQLite database. Rejected operations compare database rows before/after; legitimate metadata updates, partition migration and owned links remain covered.

The first full run had **519 passed, 1 failed / 88.06s**: the existing SDK forgetting-path probe sometimes did not retain the target fact in its Episode summary. The probe failed 8/10 repeated runs. Diagnosis isolated equal timestamps and unspecified session row order: the scoped query added in batch 1b can use an index that orders timestamp ties by random atom IDs, not batch message position. The probe does not call update/migrate/link; its labels are deterministic, and no assertion was weakened.

A new fixed-timestamp three-atom regression failed with the wrong row order. Session reads now explicitly order by `created_at, episode_position, id`, preserving existing batch positions on timestamp ties. Isolation/mutation/forgetting-path checks then passed **40 / 8.33s**; the original probe passed **10/10** repeats. Final full local regression after this correction: **521 passed / 83.33s**, Windows/Python 3.12.14. This does not fix forgetting residue, Episode deduplication or general mixed-agent EpisodeBuilder behavior, nor establish independent memory quality.

Compatibility note: undocumented arbitrary/unknown update fields previously could be applied or silently ignored; they are now rejected. Trusted raw storage access and external concurrent ownership changes are not covered by these SDK checks. HTTP synchronization, authentication and production data migration remain separate work.

## Still open

1. HTTP production gateway, real browser validation and bounded concurrency/load evidence (local boundary repaired in batch 2).
2. Remaining privacy write-path/notification gaps, historical orphan audit/migration, complete derived-memory erasure and permanent Episode identity across regrouping (scanner fixed in 3a, graph lifecycle in 3b, affected Episode invalidation/live queue consumption in 3c, bounded SDK rebuilding in 3d, sequential backpressure results/accounting in 3e).
3. Observability, supported-version compatibility, coverage and public documentation evidence.
4. MCP automatic edge-building policy and independently supported retrieval-quality improvements.

Batches 1a–1c did not change HTTP defaults; batch 2 intentionally requires HTTP authentication and explicit sessions. Retrieval defaults remain unchanged. No real configuration or user database was migrated. Python 3.10 execution, power-loss durability and real browser attack scenarios have not been verified.

## Batch 2: local HTTP security and synchronization

- Mandatory constructor/environment token, constant-time Bearer comparison, loopback-only binding, exact Host/Origin checks and no wildcard CORS. Only health/preflight are unauthenticated; data remains protected for allowed origins.
- Server-instance SDK/lock replaces class-shared memory/session state. Full session IDs round-trip explicitly; session end without an ID is rejected. SDK operations serialize under an instance RLock, outside network reads/writes.
- JSON object/framing/content-type checks, 1 MiB declared-body limit, 10-second socket timeout and generic internal errors. Standalone shutdown closes the connection after handler completion. Unknown link labels are rejected instead of silently becoming similar.
- Functional red: **9 failed**, no fixture errors. Expanded HTTP/adapter checks: **34 passed / 7.82s**. A real SQLite transaction interleaving test fails when the lock is disabled in a separate process and passes with the lock. Windows can reset an oversized upload when rejected without draining; the size-limit check sends only headers to prove rejection before body reads.

Compatibility and remaining limits are documented in `HTTP_SECURITY.md`; there are no new dependencies, real data migrations or model calls. These are local security regressions, not memory-quality evidence.

The first full run had **431 passed, 103 fixture errors / 88.46s** because Windows denied access to the default `pytest-of-ASYS` temporary directory. A targeted fixture-only run reproduced `PermissionError` before application setup. Using a checked, new unique repository-local `--basetemp` without deleting old directories yielded **534 passed / 92.40s**, Windows/Python 3.12.14. No test assertion was relaxed. No commit or push was performed.

Configuration schema references: [OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli#configure-with-configtoml), [Claude project scope](https://code.claude.com/docs/en/mcp#project-scope).

## Batch 3a: scanner false positives and overlapping redaction

- Low-confidence generic-key/card patterns require explicit credential/card labels instead of unconditional long-string matches. Chinese phone boundaries reject substrings of longer ASCII identifiers/digit sequences while retaining Chinese-adjacent numbers.
- Overlapping matches are unioned in original-coordinate space and replaced once. Leftmost/longest-at-equal-start type labels the union; every original finding remains available. Adjacent matches remain distinct.
- Existing warn/block/exclusion/custom-pattern contracts are retained. WARN documentation now correctly states that findings are returned without automatic logging. Violations contain raw matches and must remain private.
- Initial test runs were interrupted because the new SDK fixture accidentally used automatic model selection. It was corrected to explicit TF-IDF. The final 14 checks, run against HEAD's original scanner in a separate process without changing the working tree, gave **7 failed, 7 passed / 0.11s**. Repaired privacy/injection/adapter/HTTP regression: **81 passed / 7.71s**. Full local regression: **548 passed / 127.32s**, Windows/Python 3.12.14, using a checked new repository-local temporary directory.

See `PRIVACY_SCANNER.md` for the intentional unlabeled-secret/card detection tradeoff, unscanned write paths and unchanged SDK notification contract. No damaged real records were restored, no retrieval defaults changed, no new dependencies introduced and no commit/push performed. Remaining lifecycle work is deferred to its own transaction-focused batch.

## Batch 3b: transactional atom deletion and merge rewiring

- Deletion removes all incident edges before the atom within one transaction, rolling back on failure. It works with foreign-key enforcement on/off, does not globally enable enforcement, and leaves unrelated/historical orphan rows untouched.
- A shared storage merge transaction validates ownership/partition/scope, rewires both directions, preserves edge metadata and removes internal self-loops. Same-label/status pair duplicates keep the oldest row; differing labels/status or malformed incident edges refuse merging. Atom/edge insertion statements are reused via private noncommitting helpers; public inserts retain their existing commit behavior.
- Pure merged-content construction now preserves tenant/scope and rejects incompatible parents. SDK skips unrepresentable merges without deleting parents, returns the surviving merged ID on success, and invalidates its cache. Both storage operations reject an open caller transaction without changing it.
- Initial run: **8 failed / 0.22s**, comprising four functional failures (deletion, rollback and SDK survivor ID) and four missing-new-storage-entrypoint failures. After implementation the original eight passed; expanded lifecycle, GC, SDK, tenant/ownership and real MCP checks: **192 passed / 17.63s**, including 15 lifecycle checks.

First full run: **562 passed, 1 failed / 92.98s**. The existing SDK forgetting-path probe asserted the now-repaired defect that the returned store ID was absent. Its pass-through insertion observer now captures the actual incoming parent ID; it checks both parents absent, returned ID present and equal to the live merged ID. Legacy result field is retained with its measured false value. Unfixed seed/context/Episode/provenance residual assertions remain unchanged. The updated trace and lifecycle tests passed **16 / 0.42s**. Final full rerun: **563 passed / 100.76s**, Windows/Python 3.12.14 with a checked unique repository-local temporary directory.

See `ATOM_EDGE_LIFECYCLE.md` for duplicate-edge policy and remaining Episode/queue/version/erasure gaps. No actual user data was deleted/merged or migrated, no cloud/model calls added, no new dependencies, no retrieval thresholds/defaults changed, and no commit/push performed.

## Batch 3c: affected Episode invalidation and live queue consumption

- Delete/merge transactions invalidate affected same-owner Episode rows and clear surviving member pointers; retaining the old summary with a shortened member list is not treated as safe. Rollback restores the Episode and pointers. Unrelated owners/rows are preserved; no historical migration or automatic rebuilding is performed.
- Indexer reloads live endpoints before classification, rejects missing/foreign/self pairs, uses current content, and rejects content/version changes during classification. A final short BEGIN IMMEDIATE compare-and-insert closes the check/insert gap for other database connections; model callbacks remain outside transactions.
- flush_all uses consumed-queue progress rather than edge count. Positive batch limits are explicit. Below-threshold input cannot evict valid full-queue work; other backpressure/accounting behavior is unchanged.
- Original 12 checks: **11 failed, 1 passed / 0.34s**, no missing-entrypoint/fixture errors. Original expanded lifecycle/indexer run: **46 passed / 0.25s**. Expanded lifecycle/GC/scope/MCP checks: **124 passed / 35.77s** before the final guarded insertion change. Final guarded-path checks, including 16 new lifecycle cases and the updated SDK trace: **51 passed / 0.58s**. Final full local regression: **579 passed / 135.40s**, Windows/Python 3.12.14, checked unique repository-local temporary directory.
- The old forgetting trace assertion that Episode text/references survive failed after the fix (**1 failed / 0.60s**); it now asserts zero affected Episodes and no deleted-ID/summary residue. Surviving context/seed/reimport observations remain asserted. This is a changed observed behavior, not removal of remaining forgetting checks.

See `ATOM_EDGE_LIFECYCLE.md` for linear membership-scan cost, conservative invalidation tradeoff, queued RAM retention and remaining identity/provenance/erasure limits. Tests use synthetic in-memory data/TF-IDF; no production database migration or model call is added. No new dependency, retrieval default change, commit or push.
