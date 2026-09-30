"""Offline answer-effect probe using public MCP recall and a cached local model."""

import argparse
import json
from math import ceil
from statistics import median
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from vibe_memory.doctor import MCPProcess

SCOPE = {"service": "orders", "environment": "production", "operation": "timeout"}
TEST_SCOPE = {**SCOPE, "environment": "test"}
QUESTION = "订单服务正式环境当前超时配置是多少秒？"
CASES = (
    {"id": "correction", "expected": "60", "writes": (
        ("订单服务正式环境超时配置为30秒。", SCOPE),
        ("用户纠正：订单服务正式环境当前超时配置已改为60秒，旧的30秒结论不再适用。", SCOPE))},
    {"id": "future_draft", "expected": "30", "writes": (
        ("订单服务正式环境当前超时配置为30秒。", SCOPE),
        ("订单服务正式环境下一版草案拟将超时改为60秒，目前生效配置仍为30秒。", SCOPE))},
    {"id": "different_environment", "expected": "30", "writes": (
        ("订单服务正式环境当前超时配置为30秒。", SCOPE),
        ("订单服务测试环境超时配置为60秒，正式环境仍为30秒。", TEST_SCOPE))},
)
MODEL_REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
MODEL_CACHE = (Path.home() / ".cache" / "huggingface" / "hub"
               / "models--Qwen--Qwen2.5-0.5B-Instruct" / "snapshots" / MODEL_REVISION)


def replay_case(case: dict) -> dict:
    question = case.get("question", QUESTION)
    scope = case.get("scope", SCOPE)
    with TemporaryDirectory(prefix="vibe-answer-effect-") as directory:
        db_path = str(Path(directory) / "memory.db")
        write_start = perf_counter()
        for index, (content, write_scope) in enumerate(case["writes"]):
            client = MCPProcess(db_path, "answer-effect-probe", 10, sys.executable)
            try:
                client.request("initialize")
                client.call_tool("vibe_store", {
                    "content": content, "scope": write_scope, "session_id": f"session-{index}",
                })
            finally:
                client.close()
        write_setup_ms = round((perf_counter() - write_start) * 1000, 3)

        start = perf_counter()
        client = MCPProcess(db_path, "answer-effect-probe", 10, sys.executable)
        try:
            client.request("initialize")
            result = client.call_tool("vibe_recall", {
                "query": question, "mode": "precision", "top_k": 5, "scope": scope,
            })
        finally:
            client.close()
        recall_ms = round((perf_counter() - start) * 1000, 3)
        # Windows can release the terminated MCP process's SQLite handle just after wait().
        sleep(0.2)
    return {
        "memories": [memory["content"] for memory in result["memories"]],
        "question": question,
        "scope": scope,
        "stored_sessions": 2,
        "query_session": "new_process_after_writes",
        "write_setup_ms": write_setup_ms,
        "recall_ms": recall_ms,
    }


def run(cases: tuple[dict, ...] = CASES, repeats: int = 1, *, compare_prompt: bool = False,
        compare_question: bool = False, compare_selection: bool = False,
        model_path: Path | None = None,
        model_id: str | None = None, model_revision: str | None = None) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    if model_path is not None and (not model_id or not model_revision):
        raise ValueError("Explicit model_path requires model_id and model_revision")
    local_model = model_path or MODEL_CACHE
    if not local_model.exists():
        raise FileNotFoundError(f"Cached local model not found: {local_model}")
    from transformers import AutoModelForCausalLM, AutoTokenizer

    load_start = perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(local_model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(local_model, local_files_only=True)
    model.eval()
    model_load_ms = round((perf_counter() - load_start) * 1000, 3)

    def answer(memories: list[str], recall_ms: float, case: dict, *, clarified: bool = False) -> dict:
        context = "\n".join(f"{index}. {memory}" for index, memory in enumerate(memories, 1)) or "（无）"
        choices = case.get("choices", ["30", "60"])
        instruction = ("只依据给出的记忆回答。区分环境和已生效配置与草案；"
                       + ("若记忆明确给出当前结论，选对应选项；只有无法确认时才答未知。" if clarified else "证据不足就答未知。")
                       + f"只输出{'、'.join(choices)}或未知。")
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": f"记忆：\n{context}\n问题：{case.get('question', QUESTION)}"},
        ]
        tokens = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt",
        )["input_ids"]
        start = perf_counter()
        generated = model.generate(tokens, max_new_tokens=32, do_sample=False,
                                   pad_token_id=tokenizer.eos_token_id)
        generation_ms = round((perf_counter() - start) * 1000, 3)
        text = tokenizer.decode(generated[0][tokens.shape[-1]:], skip_special_tokens=True).strip()
        normalized = text.rstrip("。.!！ 秒")
        if normalized.casefold() == "unknown":
            normalized = "未知"
        return {
            "text": text,
            "normalized": normalized if normalized in set(choices) | {"未知"} else None,
            "prompt_tokens": tokens.shape[-1],
            "generated_tokens": generated.shape[-1] - tokens.shape[-1],
            "generation_ms": generation_ms,
            "question_to_answer_ms": round(recall_ms + generation_ms, 3),
        }

    results = []
    for repeat in range(repeats):
        for case in cases:
            replay = replay_case(case)
            no_memory = answer([], 0, case)
            mcp_memory = answer(replay["memories"], replay["recall_ms"], case)
            latest_only = answer([case["writes"][-1][0]], 0, case)
            answers = {"no_memory": no_memory, "mcp_memory": mcp_memory,
                       "latest_only": latest_only}
            if compare_prompt:
                answers["clarified_prompt"] = answer(replay["memories"], replay["recall_ms"], case, clarified=True)
            if compare_question:
                direct_case = {**case, "question": case["direct_question"]}
                answers["direct_no_memory"] = answer([], 0, direct_case)
                answers["direct_mcp_memory"] = answer(replay["memories"], replay["recall_ms"], direct_case)
            selected_memories = None
            selection_reason = None
            if compare_selection:
                statuses = case.get("write_statuses", [])
                marked = [content for (content, write_scope), status in zip(case["writes"], statuses)
                          if status == "current" and write_scope == case.get("scope", SCOPE)
                          and content in replay["memories"]]
                valid = (len(statuses) == len(case["writes"])
                         and all(status in {"current", "superseded", "draft"} for status in statuses))
                selected_memories = marked if valid and len(marked) == 1 else replay["memories"]
                selection_reason = "single_marked_current" if valid and len(marked) == 1 else "unchanged_ambiguous_or_missing"
                answers["marked_current"] = answer(selected_memories, replay["recall_ms"], case)
            for result in answers.values():
                result["correct"] = result["normalized"] == case["expected"]
                result["abstained"] = result["normalized"] == "未知"
                stale = case.get("stale_value", "30" if case["id"] == "correction" else None)
                result["stale_answer"] = stale is not None and result["normalized"] == stale
            results.append({"id": case["id"], "repeat": repeat + 1,
                            "question": replay["question"], "expected": case["expected"],
                            "direct_question": case.get("direct_question"),
                            "source_commit": case.get("source_commit"),
                            "source_path": case.get("source_path"),
                            "returned_memories": replay["memories"],
                            "selected_memories": selected_memories,
                            "selection_reason": selection_reason,
                            "write_setup_ms": replay["write_setup_ms"],
                            "recall_ms": replay["recall_ms"],
                            "answers": answers})

    def latency_summary(condition: str) -> dict:
        values = sorted(item["answers"][condition]["question_to_answer_ms"] for item in results)
        return {"p50_ms": round(median(values), 3),
                "p95_nearest_rank_ms": values[ceil(0.95 * len(values)) - 1]}

    return {
        "model": model_id or "Qwen/Qwen2.5-0.5B-Instruct",
        "model_revision": model_revision or MODEL_REVISION,
        "model_load_ms": model_load_ms, "cases": results,
        "case_count": len(cases), "repeat_count": repeats,
        "latency": {condition: latency_summary(condition) for condition in
                    (("no_memory", "mcp_memory", "latest_only")
                     + (("clarified_prompt",) if compare_prompt else ())
                     + (("direct_no_memory", "direct_mcp_memory") if compare_question else ())
                     + (("marked_current",) if compare_selection else ()))},
        "mode": "precision", "top_k": 5, "paid_model_calls": 0,
        "evidence_boundary": "Assistant-selected and paraphrased cases with assistant-scored expected answers; source commits are traceability, not independent labels. latest_only supplies the last written case text directly and excludes evidence selection/retrieval: it is an input ablation, not a deployable condition or guaranteed accuracy upper bound. Offline cached CPU model; no download or paid API. MCP query-to-answer includes process startup/recall and generation but excludes prior writes, model load, electricity, memory footprint and human review. P95 is nearest-rank descriptive only for this small local sample."
        + (" marked_current uses assistant-authored current/superseded/draft labels and exact scope after unchanged MCP recall; it is an oracle-style diagnostic, not automatic version identification or deployable evidence verification."
           if compare_selection else ""),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, help="JSON array of public experiment cases")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--compare-prompt", action="store_true", help="Compare a clarified abstention instruction on identical MCP memories")
    parser.add_argument("--compare-question", action="store_true", help="Compare a direct question on identical MCP memories and original prompt")
    parser.add_argument("--compare-selection", action="store_true", help="Report-only comparison using assistant-marked current writes within exact query scope")
    parser.add_argument("--model-path", type=Path, help="Locally downloaded model directory; never downloads")
    parser.add_argument("--model-id", help="Source model ID for an explicit model path")
    parser.add_argument("--model-revision", help="Source revision for an explicit model path")
    args = parser.parse_args()
    cases = tuple(json.loads(args.cases.read_text(encoding="utf-8"))) if args.cases else CASES
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(run(cases, repeats=args.repeats, compare_prompt=args.compare_prompt,
                         compare_question=args.compare_question, compare_selection=args.compare_selection,
                         model_path=args.model_path,
                         model_id=args.model_id, model_revision=args.model_revision), ensure_ascii=False, indent=2))
