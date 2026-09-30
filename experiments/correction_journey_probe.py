"""Offline MCP replay: an old setting, a correction, then a new-session recall."""

import json
import sys
from hashlib import sha256
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from vibe_memory.doctor import MCPProcess

DEFAULT_CORRECTION = "用户纠正：订单服务正式环境超时配置已改为60秒，旧的30秒结论不再适用。"
QUERY_SCOPE = {"service": "orders", "environment": "production", "operation": "timeout"}
QUERY_DATE = date(2026, 9, 23)


def review_gate(review: dict | None, new_content: str) -> bool:
    if not isinstance(review, dict):
        return False
    if review.get("scope") != QUERY_SCOPE or review.get("fact_key") != "orders.production.timeout":
        return False
    if review.get("verdict") != "verified_current":
        return False
    if not all(isinstance(review.get(key), str) and review[key].strip()
               for key in ("source_ref", "source_sha256", "reviewer_id")):
        return False
    try:
        source = Path(review["source_ref"]).read_bytes()
        return (date.fromisoformat(review["effective_date"]) <= QUERY_DATE
                and sha256(source).hexdigest() == review["source_sha256"]
                and new_content in source.decode("utf-8"))
    except (KeyError, TypeError, ValueError, OSError, UnicodeError):
        return False

def run(revision_link: bool = False, new_content: str = DEFAULT_CORRECTION,
        new_scope: dict[str, str] | None = None, review: dict | None = None) -> dict:
    if new_scope is None:
        new_scope = QUERY_SCOPE
    with TemporaryDirectory(prefix="vibe-correction-probe-") as directory:
        db_path = str(Path(directory) / "memory.db")
        stored = []
        write_ms = []
        for session, content, scope in (
            ("session-old", "订单服务正式环境超时配置为30秒。", QUERY_SCOPE),
            ("session-correction", new_content, new_scope),
        ):
            client = MCPProcess(db_path, "correction-probe", 10, sys.executable)
            try:
                client.request("initialize")
                start = perf_counter()
                stored.append(client.call_tool("vibe_store", {
                    "content": content, "session_id": session, "scope": scope,
                })["id"][:8])
                write_ms.append(round((perf_counter() - start) * 1000, 3))
            finally:
                client.close()

        client = MCPProcess(db_path, "correction-probe", 10, sys.executable)
        try:
            client.request("initialize")
            start = perf_counter()
            result = client.call_tool("vibe_recall", {
                "query": "订单服务正式环境超时配置是多少秒？", "mode": "precision", "top_k": 5,
                "scope": QUERY_SCOPE,
            })
            recall_ms = round((perf_counter() - start) * 1000, 3)
            link_ms = None
            linked_recall_ms = None
            if revision_link:
                start = perf_counter()
                linked = client.call_tool("vibe_link", {
                    "from_id": stored[0], "to_id": stored[1], "label": "revision",
                })
                link_ms = round((perf_counter() - start) * 1000, 3)
                if linked.get("error") or linked.get("label") != "修正推翻":
                    raise RuntimeError(f"Could not create explicit revision: {linked}")
                start = perf_counter()
                linked_result = client.call_tool("vibe_recall", {
                    "query": "订单服务正式环境超时配置是多少秒？", "mode": "precision", "top_k": 5,
                    "scope": QUERY_SCOPE,
                })
                linked_recall_ms = round((perf_counter() - start) * 1000, 3)
            else:
                linked_result = result
        finally:
            client.close()

        # Windows can release the terminated MCP process's SQLite handle just after wait().
        sleep(0.2)

    returned = [memory["id"] for memory in result["memories"]]
    def rank(atom_id: str) -> int | None:
        return returned.index(atom_id) + 1 if atom_id in returned else None

    stale_rank, target_rank = rank(stored[0]), rank(stored[1])
    linked_ids = [memory["id"] for memory in linked_result["memories"]]
    unguarded_ids = list(linked_ids)
    if (revision_link and stored[0] in unguarded_ids and stored[1] in unguarded_ids
            and unguarded_ids.index(stored[0]) < unguarded_ids.index(stored[1])):
        unguarded_ids.remove(stored[1])
        unguarded_ids.insert(unguarded_ids.index(stored[0]), stored[1])
    scopes = {memory["id"]: memory["scope"] for memory in linked_result["memories"]}
    scope_gate_passed = bool(
        revision_link and all(QUERY_SCOPE.values())
        and scopes.get(stored[0]) == QUERY_SCOPE
        and scopes.get(stored[1]) == QUERY_SCOPE
    )
    review_gate_passed = review_gate(review, new_content)
    experimental_ids = unguarded_ids if scope_gate_passed and review_gate_passed else linked_ids
    true_correction = new_content == DEFAULT_CORRECTION
    different_environment = new_scope != QUERY_SCOPE
    wrong_promotion = bool(
        not true_correction and revision_link and stored[1] in experimental_ids
        and stored[0] in experimental_ids
        and experimental_ids.index(stored[1]) < experimental_ids.index(stored[0])
    )
    return {
        "scenario": ("synthetic_cross_session_correction" if true_correction else
                     "synthetic_cross_environment_non_revision" if different_environment else
                     "synthetic_same_scope_future_draft"),
        "first_memory_role": "superseded_production_30_seconds" if true_correction else "current_production_30_seconds",
        "second_memory_role": ("corrected_production_60_seconds" if true_correction else
                               "separate_test_environment_60_seconds" if different_environment else
                               "noncurrent_future_draft_60_seconds"),
        "stored_sessions": 2,
        "query_session": "new_process_after_both_writes",
        "mode": "precision",
        "top_k": 5,
        "target_rank": target_rank,
        "stale_rank": stale_rank,
        "target_in_top5": target_rank is not None,
        "stale_in_top5": stale_rank is not None,
        "revision_link_created": revision_link,
        "linked_target_rank": linked_ids.index(stored[1]) + 1 if stored[1] in linked_ids else None,
        "linked_stale_rank": linked_ids.index(stored[0]) + 1 if stored[0] in linked_ids else None,
        "unguarded_target_rank": unguarded_ids.index(stored[1]) + 1 if stored[1] in unguarded_ids else None,
        "unguarded_stale_rank": unguarded_ids.index(stored[0]) + 1 if stored[0] in unguarded_ids else None,
        "scope_gate_passed": scope_gate_passed,
        "review_gate_passed": review_gate_passed,
        "experimental_target_rank": experimental_ids.index(stored[1]) + 1 if stored[1] in experimental_ids else None,
        "experimental_stale_rank": experimental_ids.index(stored[0]) + 1 if stored[0] in experimental_ids else None,
        "known_false_link_promotes_wrong_environment": different_environment and wrong_promotion,
        "known_false_link_promotes_noncurrent": wrong_promotion,
        "write_tool_ms": write_ms,
        "recall_tool_ms": recall_ms,
        "link_tool_ms": link_ms,
        "linked_recall_tool_ms": linked_recall_ms,
        "paid_model_calls": 0,
        "answer_quality": "not_measured_no_answer_model",
        "evidence_boundary": "Synthetic assistant-authored case; revision and review fields are externally asserted, not independently verified by this probe. In non-correction controls, stale/target field names refer only to first/second stored IDs, not truth. Scope/review field matching cannot prove a correction is current. Experimental reorder is report-only. MCP tool round trips exclude process startup and answer generation. One run is not a latency distribution or independent quality evaluation.",
    }


if __name__ == "__main__":
    cross_environment = "订单服务测试环境超时配置为60秒，正式环境仍为30秒。"
    cases = (
        ("true_revision", {"revision_link": True}),
        ("cross_environment_no_link", {"new_content": cross_environment,
                                        "new_scope": {"service": "orders", "environment": "test", "operation": "timeout"}}),
        ("cross_environment_false_link", {"revision_link": True, "new_content": cross_environment,
                                           "new_scope": {"service": "orders", "environment": "test", "operation": "timeout"}}),
        ("same_scope_future_false_link", {"revision_link": True,
                                           "new_content": "订单服务正式环境下一版草案拟将超时改为60秒，目前生效配置仍为30秒。"}),
    )
    print(json.dumps({name: run(**options) for name, options in cases},
                     ensure_ascii=False, indent=2))
