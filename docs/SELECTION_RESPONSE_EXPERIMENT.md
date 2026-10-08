# Offline selection-response boundary

## Optional SDK experiment flow (2026-10-01)

`experiments.selection_flow_probe.run(memory, question, selector=None,
candidate_top_k=5)` calls real SDK recall in precision mode, then gives the
external selector a copied candidate pack. The selector returns the existing
dataset/results/selected_ids response format. Final evidence is at most two
original texts; modifying the selector's input cannot modify retained evidence.

No selector returns an observable `selector_disabled` fallback. Exceptions from
the external selector return `call_failure` without exception details; malformed
responses use the existing validator reasons. SDK recall exceptions still
propagate, and SDK failure lists remain separately visible in `recall_failures`.
No retry, network adapter, timeout enforcement or answer generation is added.

Seven flow tests use real temporary databases and offline selector callbacks.
Together with response/relation/directional regression: 27 passed. Red/green
checks observed missing implementation, disabled/failed callback behavior, and
candidate mutation before their fixes. History/future/scope examples check
evidence transport with predetermined offline selections, not selector semantic
reasoning or production safety. Those transport tests passed without extra code.

This is an opt-in experimental entry point only; SDK/MCP defaults remain
unchanged. Larger candidate depth does not itself repair ranking or make a
selector accurate. Callers own the memory lifecycle and external-call costs.

Implemented 2026-10-01 in `experiments.selection_response_probe.process_selection`.
This is an experiment-only pure result processor, not an SDK/MCP integration.

## Contract

Input is a trusted fixed candidate pack (`dataset_id`, `cases`, unique case IDs,
unique candidate IDs within each case, original candidate text) and an untrusted
response dictionary, JSON string, or an `Exception` representing external call
failure. Candidate order is the original retrieval order. Selection budget is
fixed at two memories; model-supplied text, status and reasoning are not evidence.

Valid selections, including empty selections, return original candidate text in
selected-ID order. Invalid selections fall back to the original first two.
Each row exposes `status` (`selected` / `fallback`) and `fallback_reason`.

Reasons: `parse_error`, `call_failure`, `invalid_batch`, `dataset_mismatch`,
`missing_case`, `invalid_ids`, `over_budget`, `duplicate_id`, `unknown_id`.
Malformed batch structure, duplicate/unknown case IDs and dataset mismatch
invalidate the batch. A missing or invalid individual case affects only that
case. Exception details are not copied into output.

## Verification

Focused tests were run red before implementation and green afterwards.
Offline replay of the saved `vibe-evidence-selection-v1` GLM artifact accepted
23/23 structurally valid cases, preserving all selected IDs with zero fallbacks.
Replay sources remain in the local Knowledge vault's `zcode-glm-selection-v1`
directory; they are not redistributed here.

Structural acceptance is not semantic correctness or an independent benchmark.
Fallback is not a quality win and may reproduce original-ranking mistakes.
No provider was called: this does not prove real timeout handling, latency,
price, model availability or production integration. No SDK/MCP defaults,
credentials or real memory databases were changed.

Run: `.venv/Scripts/python.exe -m pytest tests/test_selection_response_probe.py -q`

Next: use new unseen cases to compare selection quality, original-ranking
fallback quality and end-to-end time/cost before proposing production admission.

## Resolution evidence selection seam — 2026-10-03

The user's continuation of the explicitly proposed experiment-only test boundary
was treated as confirmation. New public experimental entry:
`experiments.resolution_selection_probe.run(memory, question, selector=..., scope=..., session_id='fixture')`.
This is not a production SDK/MCP feature or a change to the existing enhancement default.

The entry calls existing SDK precision Top-5, then uses public SDK history of one
synthetic session (at most100 rows; active/warm only) and the existing BM25 provider
to append **one absent positive-score winner**. Candidate count is at most six,
not a general corpus-depth or scalable evidence-coverage policy. History is
owner-scoped by the SDK. These fixture calls use temporary TF-IDF databases,
with automatic edges and Episode creation disabled.

Selector input includes full content, scope, context_before/context_after and
source_session; this source is a session reference, **not authenticated provenance**.
No expected relevance/negative labels are passed to the selector. The callback
receives a deep copy. Existing `process_selection` enforces IDs and a two-memory
output limit, retaining original evidence text even when the callback mutates its
input or fabricates text. Disabled/failing/missing/invalid callbacks visibly fall
back to the first two candidates; in the normal five-baseline fixture these are
the baseline's first two, not a repair of its omission. Empty valid selection is
allowed by the reused boundary. No provider/API/model inference is implemented.

`score_result(result, relevant_ids, negative_ids)` is a separate public report
function **after selection**: it records selected relevant IDs, selected negative
IDs and loss of baseline relevant evidence. It does not reject, replace or repair
structurally legal wrong selections. The labels are assistant-authored literal
test expectations, not independently reviewed truth. Selection output can discard
evidence because its budget is two rather than five; recording that loss is not a
claim that it has been prevented.

TDD evidence: initial missing-module collection error, then an incomplete delegate
missing the baseline field, then an actual behavior red signal: the existing
five-candidate flow cannot expose the omitted repair/context, so the selector
falls back and `status == selected` fails (0.24s). Minimal experimental candidate
augmentation makes the first test pass (0.19s). The scoring slice was also red
before `score_result` existed, then two tests passed (0.27s). Additional checks
lock already-supported fallback and deliberately legal wrong-selection behavior;
they are not falsely described as new ranking repairs.

New tests: **7** public experiment/SDK checks for omitted repair and full context,
immutable evidence, accepted-but-wrong selection reported as negative, disabled,
exception, missing case, unknown ID fallbacks, and dropped relevant evidence.
Combined regression **46 passed /2.69s**, Windows/Python3.12.14, new unique pytest
directory and model-hub offline flags:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_resolution_selection_probe.py tests/test_selection_flow_probe.py tests/test_selection_response_probe.py tests/test_retrieval_projection.py tests/test_rrf_fusion.py tests/test_longmemeval_lexical_slot_probe.py -q --basetemp <new-unique-directory>
```

These are **scripted selector transport/evaluation tests**, not measurements of
semantic model reasoning. The original production six-row omission is still
unresolved. No new full-suite, independent quality, graph-supported selection,
real dates/current-state judgment, answer generation, timeout, token budget,
latency/RSS, hosted-model or price evidence. Paid API calls0; callback failures
are injected, not real network timeouts. Existing production ranking/source
schema, real databases and host configurations unchanged. Original44closed/
9excluded/12open and Start Plan/independent blind-label deferrals remain.

Next: freeze a label-free full-content/context candidate pack and evaluate actual
selections on negation, old/current/history/future scope, and joint evidence, while
keeping scoring labels separate and reporting valid-but-wrong outputs. Assistant
judgments remain non-independent development data; cannot stand in for Start Plan
host-model availability, timing or cost. Do not promote this experimental session
history cap or one BM25 winner to production defaults without coverage/safety proof.

## Frozen context pack and current-assistant reading — 2026-10-03

The same confirmed experiment/temporary-SDK seam now exports and scores a pack:

```powershell
.venv/Scripts/python.exe -m experiments.resolution_selection_probe export --cases experiments/resolution_context_cases.json --pack results/resolution_context_pack.json --baseline results/resolution_context_baseline.json
.venv/Scripts/python.exe -m experiments.resolution_selection_probe score --cases experiments/resolution_context_cases.json --pack results/resolution_context_pack.json --baseline results/resolution_context_baseline.json --response results/resolution_context_response.json --report results/resolution_context_report.json
```

Eight fresh synthetic SDK instances, no graph/automatic edges/Episodes, TF-IDF;
eight recall calls per export (exports and pytest replays are not independent
samples). Every case exposes six candidates. Input pack has **12,023 characters**,
including JSON formatting, not a token estimate or complete conversation cost.
Expected/negative labels, baseline ranking and alias mapping are separate from
the selector pack. Original `m/n` role-bearing IDs were noticed and replaced by
case-seeded neutral `c*` aliases before final saving/scoring. Final pack SHA-256:
`b9f9d327626818719a84c61fef5644d9a35b7f6091e0280c0f76088a14f61889`.
Candidate order still reveals the normal retrieval-plus-supplement pipeline;
this is **not a blind/independent evaluation**, especially because the same
assistant authored the source cases and knew their expectations.

The current assistant read the exported full-content/context candidates and
saved choices to `resolution_context_response.json` before final scoring.
This is a manually mediated current-assistant development probe, not a scripted
callback that searches scoring labels, an autonomous SDK model adapter, a ZCode
or GLM run, or a new standalone API inference. No answer generation measured.
No raw private conversations, real DB or host configuration were used.

| Case | Current-assistant choice | Observed boundary |
|---|---|---|
| q01 successful repair | c4 | Previously omitted single evidence recovered |
| q02 unsuccessful attempt | empty | Did not use failed action as a successful remedy |
| q03 obsolete/current query | empty | Current applicability missing |
| q04 different service | empty | Billing evidence not an orders remedy |
| q05 future unexecuted draft | empty | Future plan not a completed current repair |
| q06 historical-date query | c1 | Old-version record valid for the requested date retained |
| q07 unresolved conflicting account | empty | No unsupported successful-remedy commitment |
| q08 cause plus resolution | c6 | Only resolution present; cause never entered candidate pack |

All eight responses structurally accepted, zero fallbacks; none of five explicit
negative/risk cases selected its labeled target. This does **not** mean8/8 quality
success. Two single-evidence positives recovered, but q08 recovered only1/2 of
the required evidence. Its source text references another record `m1`; that is
literal fixture context, not a verified graph edge or resolvable production ID.
The cause is outside the selector candidates, so a better selection cannot
recover it. All source/session statements remain assistant-authored assertions;
q07's risk label does not prove the conflicting original statement false.
Empty selection is valid abstention and supplies no missing answer.

Integrity repair: the first export hashed LF text before Windows `write_text`
wrote CRLF bytes; scoring correctly stopped at a hash mismatch. A public CLI
test reproduced mismatched recorded/file hashes. Export now writes the exact
hashed UTF-8 bytes (`write_bytes`), not a relaxed hash comparison. Another red
CLI test exposed acceptance of responses declaring a different pack hash;
scoring now rejects that mismatch. Hashes bind artifact bytes only, not truthful
labels, reviewer identity or model origin. Neutral-ID re-export, saved response
and final scoring all use the matching final hash.

Three new tests (pack excludes labels, saved-byte hash identity, wrong-pack
response rejection) bring this module to10 tests. **49 related tests passed /
3.33s**, Python3.12.14, new unique pytest root/model-hub offline flags. Production
ranking remains unchanged and its original omission still exists; no new full
suite, independent holdout, graph trial, automated model comparison, actual
timeout/cost/latency or real-host answer acceptance. Paid standalone API calls0;
current conversation usage is not measured by this report. Original44/9/12 and
Start Plan/96-row human-review deferrals remain.

Next priority: controlled **associated evidence candidate coverage**, using
existing SDK link/history/recall and correct relation/owner/scope/lifecycle
boundaries, not a global Top-K increase or returning invented referenced IDs.
Require a two-evidence positive and crossed-scope/negation/obsolete/unsupported
edge negatives, then rerun selection. Also retain date/outcome/scope limitations
with selected evidence before any downstream integration: the reused selection
response emits only original text/ID, while full context currently stays in the
candidate pack rather than an automatic final evidence bundle. Independent
quality and true host-model cost remain separate gates for production admission.

## Opt-in reference coverage and selected context — 2026-10-03

`resolution_selection_probe.run(..., include_references=True)` now appends at
most one outward REFERENCE target to the existing Top-5 plus lexical winner
(at most7 candidates). Default remainsFalse. It uses existing public SDK
link/history/recall and storage retrieval-edge APIs; no production changes.
Targets must be in the same synthetic session's latest100 live history rows,
with exactly matching endpoint scopes and any requested scope constraints.
Storage enforces live owner/tenant endpoints; reverse references and adjacency
are not followed. One hop and deterministic edge-ID ordering are ceilings,
not a high-degree ranking or cross-session coverage solution. Edge reads/history
may load more rows than the candidate cap; no resource bound or latency claim.

The callback sees reference endpoint IDs/label/source, NOT verified truth.
`run` returns `selected_evidence` copied from original candidates in selection
order, including text,scope,context_before,context_after,source_session; callback
mutations cannot rewrite these fields. This applies to selected and fallback
results, without changing the existing ID/text selection contract. Export/score
CLI and production injection are NOT wired to this new opt-in evidence bundle;
the previous frozen pack/report/hash and 1/2 result remain historical evidence.

TDD joint fixture first failed on the missing opt-in argument. After minimal
implementation, the same linked fixture goes from root-cause candidate missing
to both repair and cause available (6→7 candidates); a predetermined callback
selects2/2 and retains both original contexts. This is candidate coverage and
transport proof, NOT measured semantic-model accuracy. Scope-negative then
failed when no query scope was supplied; exact endpoint-scope equality repaired
that bypass. Lifecycle setup initially attempted unsupported SDK.update fields;
the fixture now uses approved public storage.update_atom, not private methods
or SQL assertions. Seven boundary variants cover scope,cold,archived,reverse,
adjacent,deleted,other-agent. Three more variants show unverified,obsolete and
negated references can still enter as candidates: wrong scripted selections
are scored as negatives, and attempted context rewriting is ignored. No rule
silently promotes edge existence into a successful resolution or true cause.

11 new test instances,21 in this module; related **60 passed/4.29s**,
Python3.12.14 and a new temporary pytest root. No full-suite rerun, independent
evaluation, API/model/host invocation, cost or latency measurement. Original
44closed/9excluded/12open unchanged. Next: connect this explicit experiment to
a new versioned frozen pack and score-time evidence bundle, then separately
evaluate choices; never reuse the previous response for a changed pack. Keep
production/Start Plan acceptance and human review deferred.

## Versioned reference export and frozen-context scoring — 2026-10-03

The export/score CLI is now wired to the experiment-only reference branch.
`export --include-references` uses dataset `resolution-reference-v2`; without
the flag the dataset stays `resolution-context-v1`. Fixture `references` declare
from_id/to_id using private fixture aliases; exporter creates SDK REFERENCE edges
with pinned time/UUID, in both on/off arms, and remaps exported relation endpoints
to neutral candidate IDs. Declared edges are caller assertions, not truth labels.
Only edges actually used to append a candidate appear in the selector pack.
Scoring labels and alias mappings still stay outside the selector input.

New source: `experiments/resolution_reference_v2_cases.json`,11 synthetic cases:
the prior8 developmental cases plus unverified,obsolete,negated reference causes.
q08's textual fixture alias was replaced with a generic associated-record
reference; an actual SDK link now connects its two records. This is not a fresh
blind holdout: the same assistant wrote/reused cases and knows expected labels.

```powershell
.venv/Scripts/python.exe -m experiments.resolution_selection_probe export --cases experiments/resolution_reference_v2_cases.json --pack results/resolution_reference_v2_off_pack.json --baseline results/resolution_reference_v2_off_baseline.json
.venv/Scripts/python.exe -m experiments.resolution_selection_probe export --cases experiments/resolution_reference_v2_cases.json --pack results/resolution_reference_v2_pack.json --baseline results/resolution_reference_v2_baseline.json --include-references
# After reading the new pack, save a NEW response declaring its exact hash.
.venv/Scripts/python.exe -m experiments.resolution_selection_probe score --cases experiments/resolution_reference_v2_cases.json --pack results/resolution_reference_v2_pack.json --baseline results/resolution_reference_v2_baseline.json --response results/resolution_reference_v2_response.json --report results/resolution_reference_v2_report.json
```

On/off baseline evidence is identical; every original6-candidate prefix is
identical. q01–07 remain6 candidates, q08–11 grow6→7, total66→70. q08 relevant
candidate coverage is1/2→2/2; q09–11 also acquire risk candidates, so coverage
alone is NOT quality. On pack18,005 formatted JSON characters, off16,289;
these are not tokens, latency or billing totals. On pack SHA256
`cc0b4b62d2630e888dcddd1e3e5d7d6aad3b98b9cab9b7d7fa6a43e69c91a0ab`
replayed byte-identically in a new temporary directory. Recall failure arrays
are empty in both arms; this is operational status, not answer correctness.

Current assistant actually read the on-pack and saved a NEW response before
running scoring. q01 selects c4, q06 c1, q08 c6+c1, q09 c5, q10 c2, q11 c6;
q02–05/q07 select nothing.11 structurally accepted,0fallbacks,0 labeled negative
targets selected. q08 retains both observed repair and root cause; q09–11 retain
only recovery observations and leave the cause unknown. Do NOT call this11/11
complete-answer accuracy: those three questions ask for a cause that is not
established, and neither a final answer nor an independent model was evaluated.
The report has7 selected evidence records, copied from frozen candidates in
selection order with original text/scope/before/after/session. Response-supplied
context is ignored; valid empty choices produce empty evidence, while unknown-ID
fallbacks preserve original fallback contexts. Four existing artifact hashes
(old pack/baseline/response/report) were checked before/after and unchanged.

Five new test instances: versioned public export (missing argument red), CLI
opt-in (unsupported flag red), selected/empty/unknown response scoring
(missing selected_evidence red). All went green after minimal experiment edits.
Module26 tests; related **65 passed/5.89s**; separate existing SDK/MCP regressions
**77 passed/35.55s**, Python3.12.14/new temporary roots. An initial regression
command named a nonexistent test_sdk.py and collected0; only the corrected run
above is counted. No full-suite rerun, production modifications, real-host/API
model inference, independent evaluation, cost or timeout/latency evidence.

Next controlled question: when multiple references compete for the single extra
slot, does endpoint-ID ordering hide valid evidence behind a misleading or
unsupported relation? Keep candidate coverage, choice quality, final-answer
completeness and total user cost separate. SDK/MCP injection/automatic model
adapters remain unwired; Start Plan and96-row human review remain deferred.

## Reference competition: two slots help, do not solve coverage — 2026-10-03

New source `experiments/resolution_reference_competition_cases.json` contains4
assistant-authored synthetic cases, with identical five maintenance distractors.
r01/r02 swap source record order; UUIDs are pinned serially, so this also swaps
target-ID ordering. Single-slot expansion admits the first target by endpoint
ID, not semantic validity: r01 shows a disproved guess and hides the valid cause,
while r02 shows the cause. This establishes ID-order bias, not a claim that any
real-world store-order change always changes arbitrary UUID ordering.

An explicit experiment-only `reference_limit=2` / `--reference-limit 2` now
compares two DISTINCT outward targets. Default remains1; include_references
remainsFalse by default; SDK precision Top-5 and final selection budget2 unchanged.
Export with references and limit2 uses `resolution-reference-v3`, with at most8
total candidates. Limit must be integer1 or2 (reject bool/noninteger/out-of-range);
duplicate target IDs do not consume another slot. The original anchor set stays
fixed, preventing expansion into a second hop. Owner/live/session/scope/direction
checks are unchanged and tested with both limits. Candidate caps do not bound
the storage query or history-loading cost.

```powershell
.venv/Scripts/python.exe -m experiments.resolution_selection_probe export --cases experiments/resolution_reference_competition_cases.json --pack results/resolution_reference_competition_single_pack.json --baseline results/resolution_reference_competition_single_baseline.json --include-references
.venv/Scripts/python.exe -m experiments.resolution_selection_probe export --cases experiments/resolution_reference_competition_cases.json --pack results/resolution_reference_competition_double_pack.json --baseline results/resolution_reference_competition_double_baseline.json --include-references --reference-limit 2
# Read each pack, save its own response/hash, then run score with matching files.
```

Each on-budget arm has its own pack/baseline/response/report. Current assistant
read each frozen pack and saved choices before scoring; knows authored labels,
so NOT blind, independent, or an external/automatic model evaluation.

| Case | Required positive evidence | Selected with1 slot | Selected with2 slots | Remaining limit |
| --- | --- | --- | --- | --- |
| r01 bad target first | repair+cause | repair only | repair+cause | both candidate contents needed |
| r02 good target first | repair+cause | repair+cause | repair+cause | same2-target competition |
| r03 good target third | repair+cause | repair only | repair only | both slots occupied by risk targets; cause absent |
| r04 no verified cause | repair only | repair only | repair only | no root cause is established |

Both reports:4 structurally accepted,0fallbacks,0 labeled negative targets
selected. r03 still lacks one REQUIRED positive, despite structural success;
r04 has no verified cause to invent. Two slots improve one bounded case, not
the whole problem or final-answer accuracy. No content-aware ranking is yet
implemented; wrong ID ordering still matters beyond the admitted prefix.

Baselines and original7-candidate prefixes are identical; total candidates
28→32, formatted JSON7,264→8,691 characters (not tokens or cost). Double pack
SHA256 `2344466a1d381d037a7afde40f53737c33827e39018e2e1840c738c1bc3da61d`
replayed byte-identically. Default single-slot export of the previous11-case
source also replayed the previous `cc0b4b62...` hash; old packs/reports unchanged.

14 additional test instances: two-slot public export (missing argument red),
invalid limits4 variants (no rejection red), duplicate-target regression,
CLI export (unsupported argument red), and7 existing boundary cases repeated
with limit2. Module40; related **79 passed/6.67s**, Python3.12.14/new temporary
roots. No new full-suite or SDK/MCP rerun this turn (prior77 is historical).
Production defaults, original44/9/12, deferred Start Plan/human review unchanged.
Next: bounded content-aware comparison of competing references, preserving
negative/date/scope context and explicit missing-evidence reporting. Measure
additional input/calls before production integration; do not simply keep raising
Top-K or treat provenance/confidence as verified truth.

## Bounded reference-content review stage — 2026-10-03

`export --include-references --review-references` now freezes dataset
`resolution-reference-review-v4`. The existing run collects diagnostic previews
of at most3 DISTINCT eligible outward targets; original reference_limit1/2
still governs its normal final candidate pool. Preview needs explicit reference
opt-in, preserves owner/live/session/scope/direction checks, and is not multi-hop.
The review pack separates target `candidates` from the original at-most6
`anchor_evidence` contextual records. Only reference target IDs may be chosen;
existing structural validation still allows at most2, preserves legal empty
choices and exposes fallback. No keyword heuristic converts negation/date or
"confirmed" language into verified truth. Beyond the first3 targets, ID-order
coverage bias remains; this is not a complete high-degree solution.

```powershell
.venv/Scripts/python.exe -m experiments.resolution_selection_probe export --cases experiments/resolution_reference_competition_cases.json --pack results/resolution_reference_content_pack.json --baseline results/resolution_reference_content_baseline.json --include-references --review-references
# Read target and anchor contexts, save a NEW review response, then score:
.venv/Scripts/python.exe -m experiments.resolution_selection_probe score --cases experiments/resolution_reference_competition_cases.json --pack results/resolution_reference_content_pack.json --baseline results/resolution_reference_content_baseline.json --response results/resolution_reference_content_response.json --report results/resolution_reference_content_report.json
```

Current assistant read this new pack, saved reference choices r01c5/r02c5/r03c4/
r04empty BEFORE scoring. The same assistant authored/knows the reused fixture
labels: NOT blind or independent, not GLM/ZCode, not an automated semantic
ranker. r03's formerly hidden third cause is now selected by content; disproved,
obsolete and unverified causes are not selected.4 structurally accepted,
0fallbacks,0 labeled negative targets selected. r04 still has no known root cause.

Report marks `evaluation_stage=reference_review`. It proposes a pool by copying
frozen anchors plus original selected target evidence (6+≤2, never response-
supplied anchor/context text). Proposal sizes7/7/7/6; post-choice scoring shows
required positive evidence2/2,2/2,2/2,1/1 in these proposed pools. The added
`proposed_pool_relevant_ids` and `missing_proposed_relevant_ids` distinguish
coverage from choice or complete answers. Existing selected/lost fields remain
unchanged: reference-only outputs deliberately omit the repair anchors, so those
fields must NOT be read as final selection quality. A wrong structurally legal
review or fallback can still insert risk targets into a proposal. Proposals are
NOT a final memory selection, SDK injection, or generated answer. No live
two-stage model adapter or content reranker is wired.

Input:9 review targets plus24 anchors across4cases,33 evidence records,
9,201 formatted JSON characters vs prior double-slot8,691 (510more characters).
This is not tokens, whole-turn usage, total workflow input or price. Integrating
review before final selection may add another model round; its end-to-end time,
timeout/quota and total cost are NOT measured. Paid standalone API calls0;
this conversation's usage is unmeasured. Full text has no new character/token
cap, and underlying storage reads are not bounded by preview count.

Pack SHA256`c91aa765cff01fcfbb6d05ca32608869d0c81d3b94f69f727eed9a76f60a93d6`
replayed identically; previous v3 double-slot pack replayed unchanged too. All
old artifacts retained.3 additional test instances (missing export option,
unsupported CLI flag/proposal coverage fields, missing opt-in rejection red→
green); existing14 scope/lifecycle/owner/direction boundary instances now also
check preview exclusion. Module43; related **82 passed/7.05s**, Python3.12.14,
new temporary roots. No new full suite or production SDK/MCP regression run.
Next: consume proposals in a separately frozen final2-memory selection, preserve
review failure/empty behavior, and explicitly report missing evidence before
any production or host integration. Original44/9/12 and deferred Start Plan/
human review unchanged.

## Separately frozen final selection (2026-10-03)

`freeze_final_pack` and CLI `finalize` consume the frozen v4 review pack and
structurally validated response, not a mutable scored proposal or quality labels.
The CLI checks source/pack/response binding before writing new v5 artifacts.
Original anchors are retained; successful review choices append original target
evidence. Empty review adds nothing. Failed review adds no fallback targets,
because first-two fallback may forward excluded/obsolete assertions. This is a
bridge policy, not semantic proof that anchors are safe. A legal wrong review
still enters the pool, and a legal wrong final choice remains wrong in scoring.
Upstream statuses and pack/baseline/response hashes remain in the final audit.
The old v4 report's naive proposal is retained as historical evidence, not used.

Replay command:

```powershell
.venv/Scripts/python.exe -m experiments.resolution_selection_probe finalize --cases experiments/resolution_reference_competition_cases.json --review-pack results/resolution_reference_content_pack.json --review-baseline results/resolution_reference_content_baseline.json --response results/resolution_reference_content_response.json --pack results/resolution_final_selection_pack.json --baseline results/resolution_final_selection_baseline.json
.venv/Scripts/python.exe -m experiments.resolution_selection_probe score --cases experiments/resolution_reference_competition_cases.json --pack results/resolution_final_selection_pack.json --baseline results/resolution_final_selection_baseline.json --response results/resolution_final_selection_response.json --report results/resolution_final_selection_report.json
```

Current assistant read the frozen final pack and saved choices before scoring:
r01 c2/c5, r02 c1/c5, r03 c1/c4, r04 c0 only. Four structural accepts, zero
fallbacks/labelled negatives; required selection coverage 2/2,2/2,2/2,1/1.
r04 has no confirmed cause, so this is NOT four complete correct answers.
`missing_candidate_relevant_ids` and `missing_selected_relevant_ids` separate
coverage loss from selection loss. No answer generation or production injection.
Same assistant knew labels: NOT blind, independent, GLM or model-adapter proof.

Final pool sizes 7/7/7/6 (27 records), 6,462 formatted JSON characters;
SHA256 `041d93fff70d54235747cbd29da456bc605ad94510ab23bd3e885429ff270183`.
Review+final pack inputs total 15,663 characters (9,201+6,462), excluding prompts,
responses and protocol overhead. This is NOT token usage or price. A real
two-stage workflow needs both model stages, yet no API calls, host integration,
timeout/quota/latency or end-to-end cost were measured here. Conversation usage
is unmeasured; separate paid API calls zero. Fourth-reference truncation, lexical
scope risk and unbounded evidence text/underlying reads remain experiment limits.

TDD: missing bridge red, successful frozen-context green; failure forwarding red
then suppressed; unsupported CLI red then bound export/scoring green. Five new
instances, module 48, related **87 passed/8.10s** in fresh temporary roots.
Empty review/final, API exception, unknown IDs and legal wrong choices covered.
No new full suite or production regression run. Next: controlled answer/unknown-
cause evaluation with failures, then independent review and real-host total cost;
do not enable production from these four synthetic cases. Original 44/9/12 and
deferred Start Plan/human blind review remain unchanged.

## Offline answer boundary and scripted faults (2026-10-03)

`freeze_answer_pack` and CLI `answers` export v6 from frozen v5 plus its bound
response, preserving selected original text/context and review/final statuses.
No labels or scored report are passed to the answer input. Failure retains the
existing first-two final fallback (potential noise), explicitly marked; empty
selection remains empty. Instruction separates cause/repair, requests local ID
citations, prohibits cross-case fill-in, and asks for unknown when unsupported.
This prompt is NOT a semantic enforcement mechanism or production safeguard.

```powershell
.venv/Scripts/python.exe -m experiments.resolution_selection_probe answers --cases experiments/resolution_reference_competition_cases.json --pack results/resolution_final_selection_pack.json --baseline results/resolution_final_selection_baseline.json --response results/resolution_final_selection_response.json --report results/resolution_answer_pack.json
```

Normal answer pack hash `22ec3a4268ff78259a46e5380273c3c921ae85b6a399cb0045dfa64295dc2f55`,
3,210 characters. Scripted fault pack hash
`1b010950c321d2d1ad56868dee77900984234c65daedd0bf8f0d7036342f4d09`,
2,676 characters. Fault r01 review unknown-ID then repair-only, r02 empty final,
r03 legal excluded reference then repair+excluded choice, r04 unknown final-ID
then maintenance-noise fallback. Fault selection report records one fallback and
one labelled negative case, not a silently corrected successful selection.

Current assistant read both packs, authored eight answer records, then manually
reviewed them in `resolution_answer_review.json`. Normal: three record-supported
cause/repair answers, one root-unknown/repair-only. Fault: two root-unknown/repair-
only answers, two both-unknown. These are four cases replayed twice, NOT eight
independent examples or first-pass accuracy. During review, fault r01's initial
abstention sentence named an omitted cause detail known from prior context; it
was removed in revision, with before/after hashes recorded. Program checks did
not prevent that leakage. Final citations/semantics are same-assistant judgments,
NOT independent model, GLM, blind assessment or automatic entailment checks.
Unknown answers are bounded partial answers, not recovered evidence or complete
task success. All original packs/reports preserved.

TDD missing public exporter and unsupported CLI red→green; five added instances,
module53, related **92 passed/8.03s** in a fresh temporary root. Original context,
upstream failure, module exception, empty selection, unknown-ID fallback and CLI
hash binding checked. No new full suite, live model/host calls or production
SDK/MCP regression. Separate API cost zero; conversation usage and workflow
latency unknown. Normal three-stage pack input sum18,873 characters excludes
responses/protocol; not token count or price. Next: fresh paraphrased/adversarial
answer evidence and invalid-citation controls, then independent/live-host checks.
Do not tune production from the revised same-author walkthrough; deferred
Start Plan/human96-row review and original44/9/12 remain unchanged.

## First-answer adversarial fixture and citation controls (2026-10-03)

New answer-only v7 fixture (`experiments/resolution_answer_adversarial_pack.json`)
has six cases/10 records: paraphrased cause, withdrawn explanation, test-old vs
production-new scope, unresolved conflicting drafts, embedded malicious
instruction, empty evidence. It bypasses retrieval/selection, deliberately
supplying polluted evidence; not proof of actual SDK leakage or recall quality.
Pack2,004 characters, hash `a66f4277fd90159602b018622b352ac96880e730fdb61f662a43ce51ab48be9a`.
Same assistant authored/read it, then saved the first response before scoring.
`resolution_answer_adversarial_first_response.json` hash
`b5bd0cc164dd3c6066c87773633507e52507233e3919ee8048561e80d3b453eb`
remains unchanged after review. This is first SAVED response, not blind model
first-pass accuracy. Manual same-author review recorded bounded answers for all
six, without claiming independent truth or general injection resistance.

`check_answer_citations`/`check-answers` validate exact input/response hash binding,
complete unique case rows and explicit ASCII `[ID]` membership per case; preserve
answer text and always mark `semantic_support=not_checked`. Unknown/cross-case
IDs are invalid, citations to local records are `valid_ids`, absence is `none`,
never semantic success. This is not a general Markdown parser, fact checker or
production guard. CLI checks require no labelled source file or baseline.

```powershell
.venv/Scripts/python.exe -m experiments.resolution_selection_probe check-answers --pack experiments/resolution_answer_adversarial_pack.json --response results/resolution_answer_adversarial_first_response.json --report results/resolution_answer_adversarial_first_citation_report.json
.venv/Scripts/python.exe -m experiments.resolution_selection_probe check-answers --pack experiments/resolution_answer_adversarial_pack.json --response results/resolution_answer_adversarial_control_response.json --report results/resolution_answer_adversarial_control_citation_report.json
```

First answers: zero invalid citations, NOT six verified correct answers.
Six scripted bad controls: two illegal IDs detected, three valid-ID semantic
errors (scope/version, arbitrary conflict decision, injection claim), one uncited
fabrication classified `none`. All semantics remain unverified by the checker;
manual assessment is in `resolution_answer_adversarial_review.json`. Controls
are NOT observed model failures. No scoring-based edits to the first response.

TDD missing checker and unsupported CLI red→green. Seven additional instances,
module60; related **99 passed/8.77s**. Tests include unknown/cross-case IDs,
legal-ID false claim remaining semantically unverified, uncited text not marked
correct, missing/duplicate/empty/unknown case rows, CLI wrong-pack rejection.
No new full suite, production SDK/MCP regression, paid standalone API or host
model call; conversation tokens/cost unmeasured. Retain old records and defaults.
Next: reproduce/fix the experiment's lexical supplement scope boundary with a
public temporary SDK fixture, before independent quality/real-host cost checks.
The v7 scope control simulates pollution, not evidence that the production SDK
leaks. Original44/9/12 and deferred Start Plan/human review remain unchanged.

## Experiment-only hard scope boundary (2026-10-03)

Two real temporary-SDK red tests demonstrated pollution: the billing repair was
absent from the raw top5 yet appended by the unfiltered lexical supplement;
with only a billing record, SDK recall retained it for an orders request.
SDK `scope` is documented ranking boost, NOT exclusion or authorization. The
fix is four changed experiment lines: require all requested scope keys exactly
match in history pool before BM25, and in baseline atoms before creating anchors.
Original raw top5 remains audit-only. No production SDK semantics changed.
Empty/None scope preserves behavior; extra stored keys are permitted, missing or
mismatched requested keys excluded. Values are not casefolded/trimmed: the
experiment's exact matching is intentionally stricter than SDK boosting.

Nine new test instances: both red→green paths, four missing/mismatched service/
environment conditions, three None/empty/partial scope positive controls. Module
69, related **108 passed/9.51s**; existing SDK/MCP/scope regression **82 passed/
31.67s**. No new full suite. No internal mocks or SQL assertions in new tests.

`resolution_scope_cases.json` exported a new boundary pack, sizes5/0/1,
SHA256 `027ee312b7560e66076b788f04541fe5a022ef9d95bf4bba8d5d058116482a5c`.
Saved boundary selections empty/empty/c0 show zero marked negatives/fallbacks,
NOT independent selection or answer accuracy. `resolution_scope_boundary_validation.json`
records the checks. Original eleven-case export re-run to new files:
q04 candidate count6→5, total70→69, all other cases and raw baselines equal.
New pack hash `59ca6c06805e0f8313b828b1d67183c6ef0909452351bd9c14bfea8f900a9296`.
Legacy schema dataset IDs are retained, but scoped pack bytes/identity differ;
old responses MUST NOT be reused (existing score binding rejects wrong hashes).
Old files retained; unscoped four-case double-slot replay hash2344466a... identical.

Limits: raw recall5 and session history100 are truncated BEFORE scope filtering;
eligible records beyond these bounds may still be missing, with no capacity or
coverage guarantee. Caller-asserted scope is not truth; raw baseline is not safe
answer input. Not a production data-leak fix or claim of semantic correctness.
Separate paid APIs0, conversation usage unmeasured, no host/price measurement.
Next: directed coverage check for truncation-before-filtering, then independent
quality/host acceptance, without blindly increasing Top-K/history bounds.
Original44/9/12, deferred Start Plan/human review and production defaults remain.

## Retrieval diagnostics (2026-10-03)

The experiment now records session hydration counts, lifecycle/scope exclusions,
eligible window truncation and empty/nonempty candidate status in export audit
records and score reports. Evidence sufficiency remains `not_assessed` and
`session_read_bounded` is false. Missing diagnostics in legacy records are null,
not proof of an untruncated search. Selector inputs remain unchanged.

Two new tests were red before implementation; the 101-row fixture also checks
truncation. The resolution and selection-response modules passed 88 tests in
8.29 seconds. Three scope cases were exported/scored into
`results/resolution_scope_diagnostic_{pack,baseline,report}.json`; selector pack
hash remains `027ee312b7560e66076b788f04541fe5a022ef9d95bf4bba8d5d058116482a5c`.
Answer-input propagation was completed in the next TDD slice: `answers` reads
case-keyed diagnostics from the hash-bound baseline and copies them into the
answer case, without changing selected evidence or reading them from model
responses. Missing/null diagnostics remain absent for legacy answer inputs.
The existing CLI integration test was extended, failed on the missing field,
then passed; both modules passed 88 tests in 8.55 seconds. Diagnostics describe
upstream retrieval, not final selection sufficiency or semantic truth.
No production or full-suite claim.

Full CLI-chain verification now covers export → scripted reference review →
finalize → scripted empty final selection → answers. A temporary two-case
fixture has 101 eligible rows plus one excluded billing row, and a separate
empty scoped pool. Diagnostics survive finalize and answers unchanged; final
evidence is empty even when the upstream candidate status is nonempty.
This is a retrieval snapshot, not selected-evidence sufficiency. The new test
passed immediately, so no implementation change or red-green fix is claimed.
Both modules passed 89 tests in 9.56 seconds; no real model call was made.

## Synthetic warm cost baseline (2026-10-03)

Run `.venv/Scripts/python.exe -m experiments.resolution_cost_probe --report
results/resolution_cost_report.json`. The opt-in stdlib probe builds four
temporary TF-IDF databases via SDK store, uses one warmup and three samples,
checks loaded/eligible/excluded counts, and captures the existing selector JSON.
It leaves production unchanged and closes/removes its temporary databases.

| Session rows | Context chars per row | Separate session-read median ms | Full run median ms | Selector JSON chars / UTF-8 bytes |
| --- | --- | --- | --- | --- |
| 100 | 0 | 1.02 | 5.13 | 990 / 1196 |
| 500 | 0 | 4.80 | 10.23 | 990 / 1196 |
| 1000 | 0 | 9.37 | 18.76 | 990 / 1196 |
| 1000 | 1000 | 13.71 | 25.23 | 5990 / 16196 |

All runs keep 100 eligible orders rows and five candidates; remaining rows
are billing. This demonstrates hydration growth despite a fixed eligible pool,
and payload growth despite a fixed candidate count. Separate reads are NOT
a profiled component of the full run: subtracting these timings is invalid.
Full run includes recall and scripted empty selection, excludes fixture setup,
real model, cold start, concurrency and memory peaks. These are selector inputs,
not final-answer or host prompt measurements. Tokens and model fees remain
unknown, with zero model calls. No new pytest run or production performance SLA.

At the measured scale, do not introduce SQL changes solely from this baseline.
Next measure long-context input budgets and evidence preservation before
considering truncation; larger-scale and real-host costs remain unverified.

## Opt-in selector input budget (2026-10-03)

Experiment `run(..., max_selector_chars=N)` now checks compact JSON character
length (`ensure_ascii=False`) before invoking an enabled selector. Positive
integer limits are caller-supplied; None preserves the unbounded default.
Exceeding the limit yields empty memories with fallback `input_over_budget`;
audit candidates and complete context remain untouched. Exact equality is
allowed. Diagnostics record length, limit and over-budget status. A disabled
selector retains its existing fallback behavior, irrespective of this flag.

The long-context test was red before implementation; a boundary control checks
that complete context is transmitted and selection matches the unlimited case.
Both modules passed 91 tests in 9.19 seconds. No production change/model call.
This guard is only on the live experiment run callback, not CLI exports,
reference-review batches or final-answer inputs. It is not a token, billing,
serialization-memory or total host context bound. Next cover frozen batch
inputs without truncating evidence or claiming that fallback improves quality.

## Frozen batch output budget (2026-10-03)

CLI export/finalize/answers accept optional `--max-pack-chars N` (positive
integer). The complete pretty-printed output JSON, including whitespace,
newline and answer provenance hashes, is checked before any output write.
Exceeding it exits nonzero with `input_over_budget`, actual/allowed lengths,
and leaves existing output files unchanged. No evidence is shortened, no
empty replacement is exported, and omission preserves the previous behavior.
This covers reference-review export, frozen final selection and answer inputs.
It differs from the callback's compact JSON counting; both are character,
not token or host-context budgets. Score/check-answers reject this option.

Three CLI stage cases failed before implementation and passed after; related
modules passed 94 tests in 9.93 seconds. Existing no-budget flows also passed.
The check happens after generation/serialization, so it does not bound reading
or peak memory and cannot prevent manual use of old over-budget files.
No production/model-call/independent-quality claim. Next verify exact-length
acceptance and malformed budget arguments before real-host integration.

Boundary verification completed: export/finalize/answers accept the exact
serialized character length and reproduce identical output bytes; a limit
one character smaller rejects without changing any output. Zero, negative,
fractional, boolean-looking and nonnumeric CLI values are rejected before
reading missing input files or writing outputs. Extended stage tests and five
argument cases passed immediately; no implementation fix was needed.
Related modules passed 99 tests in 13.10 seconds. Next reprioritize remaining
review issues rather than treating more synthetic controls as quality gains.

## Filter before the eligible history window (2026-10-03)

Public temporary SDK fixture reproduced the missing-evidence case: one older
orders repair,100 newer billing maintenance rows. Target absent from raw top5
and latest100 history; old experiment candidates empty. Red→green: reuse existing
public storage session read with explicit owner/tenant, filter active/warm and
requested scope first, then take latest100 eligible rows before BM25/reference
preview. Target recovered as the one lexical supplement; candidate budget<=6
anchors remains, and production recall/top5 contract unchanged.

Important budget correction: SDK `history(limit=100)` already calls an unbounded
session read and hydrates all records before slicing. Neither old nor new path
has a100-row database/physical-memory/latency cap. New path does not intentionally
expand that existing full-session read, but identical resource cost is NOT
measured or guaranteed. Scope filtering before the window means cross-scope
records no longer consume eligible slots;100 is an eligible-pool limit only.

Negative ceiling/isolation control:101 same-scope owned rows, old reference cause
outside eligible100, repair still admitted, another agent's same-session strong
lexical record excluded. Old target remains unavailable to preview; do NOT claim
all coverage fixed. Raw top5 can still truncate before scope, one lexical slot
cannot recover every lost item, and beyond100 eligible records remain excluded.

Two new instances/module71; related **110 passed/10.72s** in a fresh temporary
root. No new full suite or production regression (prior82 is historical).
Scope boundary pack027ee312... and unscoped double-slot2344466a... replay
identically to fresh files, old artifacts retained. Engineering boundary only,
no new model/answer/host/API or token/cost/time evidence. Defaults and44/9/12,
deferred Start Plan/human review unchanged. See
`results/resolution_scope_window_validation.json`. Next: expose filtered-window
and insufficient-evidence diagnostics in experiments, not hidden success or a
blind Top-K increase; independent quality and true-host cost remain required.
