"""End-to-end probe replays memory through the public MCP boundary."""

import json
from pathlib import Path

import pytest

from experiments.answer_effect_probe import CASES, MODEL_CACHE, replay_case, run


def test_correction_case_replays_two_sessions_before_a_new_process_recall():
    replay = replay_case(CASES[0])

    assert replay["stored_sessions"] == 2
    assert replay["query_session"] == "new_process_after_writes"
    assert any("30秒" in memory for memory in replay["memories"])
    assert any("60秒" in memory for memory in replay["memories"])
    assert replay["recall_ms"] > 0


def test_custom_source_case_uses_its_own_question_and_scope():
    case = {"id": "source-case", "question": "当前是否支持中文双字检索？",
            "scope": {"service": "vibe-memory", "operation": "chinese-recall"},
            "writes": (("旧版本不支持中文双字检索。", {"service": "vibe-memory", "operation": "chinese-recall"}),
                       ("新版本支持中文双字检索。", {"service": "vibe-memory", "operation": "chinese-recall"}))}

    replay = replay_case(case)

    assert replay["question"] == case["question"]
    assert replay["scope"] == case["scope"]
    assert len(replay["memories"]) == 2


def test_replay_queries_requested_scope_after_other_environment_write():
    production = {"service": "orders", "environment": "production", "operation": "timeout"}
    testing = {**production, "environment": "test"}
    case = {"question": "正式环境的超时是多少？", "scope": production,
            "writes": (("正式环境超时为30秒。", production),
                       ("测试环境超时为60秒。", testing))}

    replay = replay_case(case)

    assert replay["scope"] == production


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_one_case_compares_full_answers_with_and_without_mcp_memory():
    report = run(CASES[:1])

    assert report["model_load_ms"] > 0
    assert report["paid_model_calls"] == 0
    assert len(report["cases"]) == 1
    assert set(report["cases"][0]["answers"]) == {"no_memory", "mcp_memory", "latest_only"}
    assert report["cases"][0]["answers"]["mcp_memory"]["prompt_tokens"] > report["cases"][0]["answers"]["no_memory"]["prompt_tokens"]


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_source_case_repeats_with_its_answer_choices():
    scope = {"service": "vibe-memory", "operation": "chinese-recall"}
    case = {"id": "source-case", "question": "当前是否支持中文双字检索？",
            "scope": scope, "expected": "支持", "choices": ["支持", "不支持"],
            "writes": (("旧版本不支持中文双字检索。", scope),
                       ("新版本支持中文双字检索。", scope))}

    report = run((case,), repeats=2)

    assert report["case_count"] == 1
    assert report["repeat_count"] == 2
    assert len(report["cases"]) == 2
    assert all(item["question"] == case["question"] for item in report["cases"])
    assert all(item["answers"]["mcp_memory"]["prompt_tokens"] > item["answers"]["no_memory"]["prompt_tokens"] for item in report["cases"])


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_english_unknown_is_counted_as_abstention():
    cases = json.loads((Path(__file__).parents[1] / "experiments" / "source_backed_answer_cases.json").read_text(encoding="utf-8"))
    report = run((cases[0],))

    assert report["cases"][0]["answers"]["mcp_memory"]["text"] == "unknown"
    assert report["cases"][0]["answers"]["mcp_memory"]["abstained"]


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_latest_only_context_is_compared_without_changing_mcp_recall():
    cases = json.loads((Path(__file__).parents[1] / "experiments" / "source_backed_answer_cases.json").read_text(encoding="utf-8"))
    report = run((cases[0],))
    answers = report["cases"][0]["answers"]

    assert set(answers) == {"no_memory", "mcp_memory", "latest_only"}
    assert answers["no_memory"]["prompt_tokens"] < answers["latest_only"]["prompt_tokens"] < answers["mcp_memory"]["prompt_tokens"]
    assert len(report["cases"][0]["returned_memories"]) == 2


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_prompt_clarification_uses_same_recalled_memories():
    scope = {"service": "vibe-memory", "operation": "scope-boost"}
    case = {"id": "prompt-check", "question": "作用域匹配会过滤候选吗？",
            "scope": scope, "expected": "不会", "choices": ["会", "不会"],
            "writes": (("旧版本：尚无作用域匹配提升。", scope),
                       ("当前版本：作用域匹配只提升排序，不过滤候选。", scope))}

    report = run((case,), compare_prompt=True)
    item = report["cases"][0]

    assert set(item["answers"]) == {"no_memory", "mcp_memory", "latest_only", "clarified_prompt"}
    assert len(item["returned_memories"]) == 2
    assert item["answers"]["clarified_prompt"]["prompt_tokens"] > item["answers"]["mcp_memory"]["prompt_tokens"]


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_direct_question_compares_answer_on_the_same_mcp_recall():
    scope = {"service": "vibe-memory", "operation": "scope-boost"}
    case = {"id": "direct-question-check", "question": "scope 匹配会过滤候选吗？",
            "direct_question": "scope 匹配是会过滤候选，还是不会过滤候选？",
            "scope": scope, "expected": "不会", "choices": ["会", "不会"],
            "writes": (("旧版本：还没有 scope 匹配提升。", scope),
                       ("当前版本：scope 匹配只提升排序，不会过滤候选。", scope))}

    item = run((case,), compare_question=True)["cases"][0]

    assert item["question"] == case["question"]
    assert item["direct_question"] == case["direct_question"]
    assert len(item["returned_memories"]) == 2
    assert set(item["answers"]) == {"no_memory", "mcp_memory", "latest_only",
                                    "direct_no_memory", "direct_mcp_memory"}


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_explicit_local_model_path_is_reported_without_changing_default():
    report = run(CASES[:1], model_path=MODEL_CACHE,
                 model_id="Qwen/Qwen2.5-0.5B-Instruct", model_revision="local-test-revision")

    assert report["model"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert report["model_revision"] == "local-test-revision"


@pytest.mark.skipif(not MODEL_CACHE.exists(), reason="offline answer model not cached")
def test_marked_current_context_uses_only_recalled_matching_scope():
    cases = json.loads((Path(__file__).parents[1] / "experiments" / "version_context_holdout_cases.json").read_text(encoding="utf-8"))

    report = run(tuple(cases), compare_selection=True)

    assert [item["selected_memories"] for item in report["cases"]] == [
        [cases[0]["writes"][1][0]],
        [cases[1]["writes"][0][0]],
        [cases[2]["writes"][0][0]],
    ]
    assert all(len(item["returned_memories"]) == 2 for item in report["cases"])
    assert all("marked_current" in item["answers"] for item in report["cases"])
