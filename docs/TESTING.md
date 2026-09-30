# Tests and coverage

Install the development dependencies in your chosen virtual environment:

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/ -v --tb=short --cov=vibe_memory --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml
```

The same coverage command is configured in `.github/workflows/test.yml` for Python 3.10–3.13 on Ubuntu. Each job uploads only `coverage.xml` as `coverage-python-<version>`, including on test failure; a missing report fails the upload step. A configured workflow is not evidence of a completed hosted run. No minimum percentage is enforced yet: first establish reproducible baselines and prioritize uncovered behaviors rather than inventing a threshold.

Coverage measures the complete `vibe_memory` package, including currently unused modules; no low-coverage module is omitted to improve the score. Line coverage, branch coverage and the terminal report's combined percentage are different measures. Passing tests or high coverage do not prove independent retrieval quality, security, every optional model backend or every platform/version.

Subprocess measurement uses the standard `coverage.py` `patch = ["subprocess"]` configuration. Development dependencies require coverage with TOML support >=7.10 and pytest-cov >=7.0; production dependencies are unchanged. MCP test clients close stdin and wait for normal EOF exit, allowing coverage to flush, with a bounded kill-and-fail fallback for a hung process. The new exit check validates an actual server process rather than a mock. Abruptly killed processes may still lose measurements.

Official references: [pytest-cov reporting](https://pytest-cov.readthedocs.io/en/latest/reporting.html), [pytest-cov subprocess migration](https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html), [coverage configuration](https://coverage.readthedocs.io/en/latest/config.html#run-patch), [GitHub artifact inputs and matrix naming](https://github.com/actions/upload-artifact).

## Local baseline boundaries

Latest batch 3u (2026-10-01), after per-instance SDK serialization: **833 passed / 135.35s**, Windows/Python 3.12.14, using the coverage command above with `-q` and an isolated pytest temporary root. Package lines: **4,008/4,636 (86.45%)**; branches: **1,223/1,584 (77.21%)**; combined rounded score 84%. MCP remains 159/167 lines and 57/62 branches. Local XML SHA256: `8d71c0237716a51e9f4f1cfb08319e974cab364a533254566386cdb9edd17ba8`, 222,640 bytes. Runtime/dependency versions and base commit are unchanged from below, with additional uncommitted repairs. Model-hub offline environment flags were not explicitly set for this invocation; this run is not evidence that all network access was blocked. No live cloud-model integration was added. Hosted matrix and real Python 3.10 verification are still pending. Earlier measurements below are historical baselines, not the latest tree.

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
