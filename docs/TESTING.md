# Tests and coverage

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
