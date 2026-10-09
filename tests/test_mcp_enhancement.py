import json
from pathlib import Path
import subprocess
import sys


def exchange(tmp_path, calls):
    messages = [{"jsonrpc": "2.0", "id": i, "method": "tools/call",
                 "params": {"name": name, "arguments": args}}
                for i, (name, args) in enumerate(calls, 1)]
    process = subprocess.run(
        [sys.executable, "-m", "vibe_memory.mcp_server", "--db-path", str(tmp_path / "memory.db"),
         "--vibe-dir", str(tmp_path / "state")],
        input="".join(json.dumps(m) + "\n" for m in messages), capture_output=True,
        text=True, encoding="utf-8", timeout=20,
    )
    assert process.returncode == 0
    return [json.loads(line) for line in process.stdout.splitlines()]


def payload(response):
    return json.loads(response["result"]["content"][0]["text"])


def test_enhancement_default_and_disabled_setting_survive_restart(tmp_path):
    replies = exchange(tmp_path, [("vibe_settings", {}), ("vibe_settings", {"enhanced": False})])
    assert payload(replies[0])["enhanced"] is True
    assert payload(replies[1])["enhanced"] is False
    assert payload(exchange(tmp_path, [("vibe_settings", {})])[0])["enhanced"] is False


def test_recall_reports_pending_host_selection_and_disabled_budget(tmp_path):
    calls = [("vibe_store", {"content": f"生产超时记录{i}为{i+20}秒"}) for i in range(6)]
    calls += [("vibe_recall", {"query": "生产超时", "top_k": 10}),
              ("vibe_settings", {"enhanced": False}),
              ("vibe_recall", {"query": "生产超时", "top_k": 10})]
    replies = exchange(tmp_path, calls)
    enhanced, disabled = payload(replies[6]), payload(replies[8])
    assert enhanced["selection_status"] == "pending_host_selection"
    assert len(enhanced["memories"]) == 5
    assert enhanced["selection_verified"] is False
    assert disabled["selection_status"] == "disabled"
    assert len(disabled["memories"]) == 2


def test_invalid_setting_does_not_change_persisted_value(tmp_path):
    replies = exchange(tmp_path, [("vibe_settings", {"enhanced": False}),
                                  ("vibe_settings", {"enhanced": "true"}),
                                  ("vibe_settings", {"unknown": True}),
                                  ("vibe_settings", {})])
    assert "error" in replies[1] and "error" in replies[2]
    assert payload(replies[3])["enhanced"] is False


def test_enhanced_recall_preserves_mode_budgets(tmp_path):
    calls = [("vibe_store", {"content": f"生产超时记录{i}为{i+20}秒"}) for i in range(20)]
    calls += [("vibe_recall", {"query": "生产超时", "mode": mode})
              for mode in ("precision", "recall", "budget")]
    calls += [("vibe_settings", {"enhanced": False})]
    calls += [("vibe_recall", {"query": "生产超时", "mode": mode})
              for mode in ("precision", "recall", "budget")]
    replies = exchange(tmp_path, calls)
    assert [payload(reply)["count"] for reply in replies[20:23]] == [5, 15, 3]
    assert [payload(reply)["count"] for reply in replies[24:]] == [2, 2, 2]


def test_session_start_follows_persisted_enhancement_after_restart(tmp_path):
    calls = [("vibe_store", {"content": f"生产超时记录{i}为{i+20}秒"}) for i in range(6)]
    calls += [("vibe_session_start", {"context": "生产超时"}),
              ("vibe_settings", {"enhanced": False})]
    enabled = payload(exchange(tmp_path, calls)[6])
    disabled = payload(exchange(tmp_path, [("vibe_session_start", {"context": "生产超时"})])[0])
    assert enabled["memories_recalled"] == 5
    assert enabled["selection_status"] == "pending_host_selection"
    assert enabled["selection_verified"] is False
    assert enabled["selection_instructions"]
    assert disabled["memories_recalled"] == 2
    assert disabled["enhanced"] is False
    assert disabled["selection_status"] == "disabled"
    assert disabled["selection_instructions"] is None


def test_recall_preserves_full_evidence_with_enhancement_on_and_off(tmp_path):
    content = "生产超时调查。" + "尚未确认原因。" * 60 + "最终结论：仅测试环境改为60秒，生产仍为30秒。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": content, "summary": "生产超时调查", "session_id": "original-session-123456789"}),
        ("vibe_recall", {"query": "生产超时"}),
        ("vibe_settings", {"enhanced": False}),
        ("vibe_recall", {"query": "生产超时"}),
    ])
    stored = payload(replies[0])
    for reply in (replies[1], replies[3]):
        evidence = payload(reply)["memories"][0]
        assert evidence["content"] == content
        assert evidence["full_id"] == stored["id"]
        assert evidence["id"] == stored["id"][:8]
        assert evidence["full_session_id"] == "original-session-123456789"


def test_session_start_delivers_full_evidence_with_enhancement_on_and_off(tmp_path):
    content = "生产超时调查。" + "尚未确认原因。" * 60 + "最终结论：生产仍为30秒。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": content, "summary": "生产超时调查"}),
        ("vibe_session_start", {"context": "生产超时"}),
        ("vibe_settings", {"enhanced": False}),
        ("vibe_session_start", {"context": "生产超时"}),
    ])
    for reply in (replies[1], replies[3]):
        started = payload(reply)
        evidence = started["memories"][0]
        assert evidence["content"] == content
        assert evidence["full_id"] == payload(replies[0])["id"]
        assert started["selection_verified"] is False


def test_evidence_distinguishes_shared_session_prefix_and_keeps_scope_qualifiers(tmp_path):
    production = "生产超时调查。" + "尚未确认原因。" * 60 + "2026-10-02确认：生产未改为60秒，仍为30秒。"
    testing = "生产超时调查对照。" + "测试观察记录。" * 60 + "2026-10-03计划：仅测试环境可能改为60秒，尚未生效。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": production, "summary": "生产超时60秒", "session_id": "shared00-production",
                        "scope": {"environment": "production"}}),
        ("vibe_store", {"content": testing, "summary": "生产超时60秒", "session_id": "shared00-testing",
                        "scope": {"environment": "test"}}),
        ("vibe_recall", {"query": "生产超时调查"}),
        ("vibe_session_start", {"context": "生产超时调查"}),
    ])
    for reply in replies[2:]:
        memories = {m["full_id"]: m for m in payload(reply)["memories"]}
        first = memories[payload(replies[0])["id"]]
        second = memories[payload(replies[1])["id"]]
        assert first["session_id"] == second["session_id"] == "shared00"
        assert first["full_session_id"] == "shared00-production"
        assert second["full_session_id"] == "shared00-testing"
        assert first["content"] == production
        assert second["content"] == testing
        assert first["scope"] == {"environment": "production"}
        assert second["scope"] == {"environment": "test"}


def test_oversized_evidence_is_explicitly_omitted_not_silently_truncated(tmp_path):
    oversized = "生产超时调查。" + "记录。" * 7000 + "末尾结论：生产仍为30秒。"
    small = "生产超时调查：测试环境为60秒，不能作为生产结论。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": oversized}),
        ("vibe_store", {"content": small}),
        ("vibe_recall", {"query": "生产超时调查"}),
        ("vibe_session_start", {"context": "生产超时调查"}),
        ("vibe_settings", {"enhanced": False}),
        ("vibe_recall", {"query": "生产超时调查"}),
        ("vibe_session_start", {"context": "生产超时调查"}),
    ])
    for reply in (replies[2], replies[3], replies[5], replies[6]):
        data = payload(reply)
        assert [m["content"] for m in data["memories"]] == [small]
        assert data.get("count", data.get("memories_recalled")) == 1
        assert data["evidence_budget"]["omitted_ids"] == [payload(replies[0])["id"]]
        assert data["evidence_budget"]["complete"] is False
        assert len(json.dumps(data["memories"], ensure_ascii=False)) <= 20000
        assert "mcp_evidence_budget_exceeded" in data["failures"]


def test_enhanced_public_tools_deliver_duration_and_evidence_scope_policy(tmp_path):
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": "截至2026-10-01，我学射箭至今有六周。"}),
        ("vibe_recall", {"query": "学射箭"}),
        ("vibe_session_start", {"context": "学射箭"}),
    ])
    for reply in replies[1:]:
        data = payload(reply)
        instructions = data["selection_instructions"]
        assert "For duration questions, distinguish" in instructions
        assert "应先简短询问用户指哪一种" in instructions
        assert "不是整个记忆库" in instructions
        assert "Candidate delivery does not verify selection." in instructions
        assert data["selection_status"] == "pending_host_selection"
        assert data["selection_verified"] is False
    session = payload(replies[2])
    assert session["memories"]
    assert session["selection_instructions"] in Path(session["inject_file"]).read_text(encoding="utf-8")


def test_empty_session_injection_preserves_policy_and_disabled_setting(tmp_path):
    session = payload(exchange(tmp_path, [
        ("vibe_session_start", {"context": "火星旅行"}),
    ])[0])
    injection = Path(session["inject_file"]).read_text(encoding="utf-8")
    assert session["memories"] == []
    assert session["selection_instructions"] in injection
    assert "no evidence returned for this query" in injection
    assert "no relevant memories" not in injection
    disabled = payload(exchange(tmp_path, [
        ("vibe_settings", {"enhanced": False}),
        ("vibe_session_start", {"context": "火星旅行"}),
    ])[1])
    assert disabled["selection_instructions"] is None
    assert disabled["selection_status"] == "disabled"
    assert disabled["selection_verified"] is False
    assert "For duration questions" not in Path(disabled["inject_file"]).read_text(encoding="utf-8")


def test_fully_omitted_session_injection_preserves_policy_and_budget_warning(tmp_path):
    oversized = "生产超时调查。" + "记录。" * 7000 + "末尾结论：生产仍为30秒。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": oversized}),
        ("vibe_session_start", {"context": "生产超时调查"}),
    ])
    session = payload(replies[1])
    injection = Path(session["inject_file"]).read_text(encoding="utf-8")
    assert session["memories"] == []
    assert session["evidence_budget"]["omitted_ids"] == [payload(replies[0])["id"]]
    assert session["selection_instructions"] in injection
    assert "Evidence omitted due to character budget." in injection
    assert "mcp_evidence_budget_exceeded" in session["failures"]
    assert session["selection_verified"] is False


def test_combined_evidence_budget_preserves_whole_records(tmp_path):
    first = "生产超时方案A。" + "证据。" * 4000 + "方案A仍未生效。"
    second = "生产超时方案B。" + "说明。" * 4000 + "方案B只适用于测试。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": first}),
        ("vibe_store", {"content": second}),
        ("vibe_recall", {"query": "生产超时"}),
        ("vibe_session_start", {"context": "生产超时"}),
    ])
    for reply in replies[2:]:
        data = payload(reply)
        assert len(data["memories"]) == 1
        assert data["memories"][0]["content"] in (first, second)
        assert len(data["evidence_budget"]["omitted_ids"]) == 1
        assert {data["memories"][0]["full_id"], *data["evidence_budget"]["omitted_ids"]} == {
            payload(replies[0])["id"], payload(replies[1])["id"]}
        assert data["evidence_budget"]["used_chars"] <= 20000


def test_enhanced_recall_delivers_date_policy_without_rewriting_evidence(tmp_path):
    unknown_day = "2026/09/29 10:00\nuser: 支付服务生产环境的发布审批策略已经更新，但这份记录没有说明更新后的策略内容。"
    explicit_day = "2026/09/29 10:00\nuser: 支付服务测试环境的发布审批策略于2026年9月27日更新为人工审批。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": unknown_day}),
        ("vibe_store", {"content": explicit_day}),
        ("vibe_recall", {"query": "支付服务发布审批"}),
    ])
    recalled = payload(replies[2])
    assert {m["content"] for m in recalled["memories"]} == {unknown_day, explicit_day}
    instructions = recalled["selection_instructions"]
    assert "创建时间、记录时间与事件发生时间、配置生效时间应分别判断" in instructions
    assert "不得仅凭日期标题或记录先后顺序" in instructions
    assert "正文明确给出的发生日期、生效日期应按其语义和适用范围使用" in instructions
    assert "未明确的日期保持未知" in instructions
    assert "不要改写证据原文" in instructions
    assert recalled["selection_status"] == "pending_host_selection"
    assert recalled["selection_verified"] is False


def test_session_injects_date_policy_and_preserves_explicit_event_day(tmp_path):
    content = "2026/09/29 10:00\nuser: 支付服务生产环境的发布审批策略于2026年9月27日更新为人工审批。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": content}),
        ("vibe_session_start", {"context": "支付服务发布审批"}),
    ])
    session = payload(replies[1])
    instructions = session["selection_instructions"]
    assert "不得仅凭日期标题或记录先后顺序" in instructions
    assert "未明确的日期保持未知" in instructions
    assert [m["content"] for m in session["memories"]] == [content]
    injection = Path(session["inject_file"]).read_text(encoding="utf-8")
    assert instructions in injection
    assert [m["content"] for m in json.loads(injection.splitlines()[-1])] == [content]
    assert session["selection_verified"] is False


def test_disabled_enhancement_keeps_date_evidence_without_selection_policy(tmp_path):
    content = "2026/09/29 10:00\nuser: 支付服务生产环境的发布审批策略于2026年9月27日更新为人工审批。"
    replies = exchange(tmp_path, [
        ("vibe_store", {"content": content}),
        ("vibe_settings", {"enhanced": False}),
        ("vibe_recall", {"query": "支付服务发布审批"}),
        ("vibe_session_start", {"context": "支付服务发布审批"}),
    ])
    for reply in replies[2:]:
        data = payload(reply)
        assert data["enhanced"] is False
        assert data["selection_status"] == "disabled"
        assert data["selection_instructions"] is None
        assert data["selection_verified"] is False
        assert [m["content"] for m in data["memories"]] == [content]
    injection = Path(payload(replies[3])["inject_file"]).read_text(encoding="utf-8")
    assert "创建时间、记录时间与事件发生时间" not in injection
    assert [m["content"] for m in json.loads(injection.splitlines()[-1])] == [content]
