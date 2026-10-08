from experiments.selection_flow_probe import run
from vibe_memory import VibeMemory
import pytest


def test_selector_sees_five_candidates_but_output_keeps_original_text(tmp_path):
    memory = VibeMemory(agent_id="probe", tenant_id="probe", db_path=str(tmp_path / "memory.db"), embedding_backend="tfidf")
    try:
        for index in range(6):
            memory.store(f"生产接口超时记录{index}为{index + 10}秒", auto_build_edges=False, auto_episode=False)

        def select(pack):
            candidates = pack["cases"][0]["candidates"]
            assert len(candidates) == 5
            return {"dataset_id": pack["dataset_id"], "results": [
                {"case_id": "q", "selected_ids": [candidates[4]["id"]], "text": "fabricated"}
            ]}

        result = run(memory, "生产接口超时是多少", selector=select)
        assert result["selection"]["status"] == "selected"
        assert result["selection"]["memories"] == [result["candidates"][4]]
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize("selector,reason", [(None, "selector_disabled"),
    (lambda pack: (_ for _ in ()).throw(RuntimeError("private detail")), "call_failure")])
def test_disabled_or_failed_selector_keeps_two_original_memories(tmp_path, selector, reason):
    memory = VibeMemory(agent_id="probe", tenant_id="probe", db_path=str(tmp_path / "memory.db"), embedding_backend="tfidf")
    try:
        for text in ("生产日志保留7天", "生产日志保留30天", "测试日志保留1天"):
            memory.store(text, auto_build_edges=False, auto_episode=False)
        result = run(memory, "生产日志保留多久", selector=selector)
        assert result["selection"]["status"] == "fallback"
        assert result["selection"]["fallback_reason"] == reason
        assert len(result["selection"]["memories"]) == 2
        assert result["selection"]["memories"] == result["candidates"][:2]
    finally:
        memory.storage.conn.close()


def test_selector_cannot_rewrite_original_evidence(tmp_path):
    memory = VibeMemory(agent_id="probe", tenant_id="probe", db_path=str(tmp_path / "memory.db"), embedding_backend="tfidf")
    try:
        memory.store("生产超时60秒", auto_build_edges=False, auto_episode=False)

        def select(pack):
            candidate = pack["cases"][0]["candidates"][0]
            candidate["text"] = "fabricated"
            return {"dataset_id": pack["dataset_id"], "results": [{"case_id": "q", "selected_ids": [candidate["id"]]}]}

        assert run(memory, "生产超时", selector=select)["selection"]["memories"][0]["text"] == "生产超时60秒"
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize("question,chosen", [
    ("9月15日生产超时是多少", "9月1日至9月19日生产超时30秒"),
    ("10月1日生产超时是多少", "10月3日起计划生产超时90秒，此前仍60秒"),
    ("租户甲生产超时是多少", "租户甲生产超时60秒"),
])
def test_offline_selection_preserves_history_future_and_scope_evidence(tmp_path, question, chosen):
    memory = VibeMemory(agent_id="probe", tenant_id="probe", db_path=str(tmp_path / "memory.db"), embedding_backend="tfidf")
    try:
        memory.store(chosen, auto_build_edges=False, auto_episode=False)
        memory.store("租户乙测试超时10秒", auto_build_edges=False, auto_episode=False)

        def select(pack):
            item = next(c for c in pack["cases"][0]["candidates"] if c["text"] == chosen)
            return {"dataset_id": pack["dataset_id"], "results": [{"case_id": "q", "selected_ids": [item["id"]]}]}

        result = run(memory, question, selector=select)
        assert result["selection"]["status"] == "selected"
        assert [m["text"] for m in result["selection"]["memories"]] == [chosen]
    finally:
        memory.storage.conn.close()
