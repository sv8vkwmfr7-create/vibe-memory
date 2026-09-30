"""Small paired LoCoMo answer probe through unchanged MCP precision recall."""

import argparse
from collections import Counter
import hashlib
import json
import re
import sys
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from experiments.locomo_retrieval import build_corpus
from vibe_memory.doctor import MCPProcess


def normalize(value: object) -> str:
    words = re.findall(r"[a-z0-9]+", str(value).lower())
    return " ".join(word for word in words if word not in {"a", "an", "the"})


def token_f1(prediction: str, expected: object) -> float:
    predicted, gold = Counter(normalize(prediction).split()), Counter(normalize(expected).split())
    overlap = sum((predicted & gold).values())
    return round(2 * overlap / (sum(predicted.values()) + sum(gold.values())), 3) if overlap else 0.0


def select_cases(sample: dict, count: int) -> list[dict]:
    corpus, _ = build_corpus(sample)
    eligible = {query["id"] for query in corpus["queries"]}
    return [
        {"id": f'{sample["sample_id"]}-qa-{index}', "question": qa["question"],
         "answer": qa["answer"], "category": qa["category"],
         "evidence": qa["evidence"]}
        for index, qa in enumerate(sample["qa"])
        if f'{sample["sample_id"]}-qa-{index}' in eligible
        and qa["category"] == 1 and qa["answer"] is not None
    ][:count]


def run(dataset: Path, model_path: Path, count: int = 11) -> dict:
    if count < 1:
        raise ValueError("count must be positive")
    raw = dataset.read_bytes()
    sample = json.loads(raw)[0]
    cases = select_cases(sample, count)
    if len(cases) != count:
        raise ValueError("not enough text-only category-1 questions")
    if not model_path.is_dir():
        raise FileNotFoundError(model_path)
    from transformers import AutoModelForCausalLM, AutoTokenizer

    load_start = perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True)
    model.eval()
    model_load_ms = round((perf_counter() - load_start) * 1000, 1)

    def answer(question: str, memories: list[str]) -> tuple[str, float, int]:
        context = "\n".join(memories) if memories else "(none)"
        messages = [
            {"role": "system", "content": "Answer the question briefly using the supplied memory when useful. If unsure, say unknown."},
            {"role": "user", "content": f"Memory:\n{context}\nQuestion: {question}"},
        ]
        tokens = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        )["input_ids"]
        start = perf_counter()
        generated = model.generate(tokens, max_new_tokens=48, do_sample=False,
                                   pad_token_id=tokenizer.eos_token_id)
        elapsed = round((perf_counter() - start) * 1000, 1)
        return tokenizer.decode(generated[0][tokens.shape[-1]:], skip_special_tokens=True).strip(), elapsed, tokens.shape[-1]

    with TemporaryDirectory(prefix="vibe-locomo-answer-") as directory:
        db_path = str(Path(directory) / "memory.db")
        client = MCPProcess(db_path, sample["sample_id"], 30, sys.executable)
        write_start = perf_counter()
        source_ids = {}
        try:
            client.request("initialize")
            corpus, _ = build_corpus(sample)
            for atom in corpus["atoms"]:
                stored = client.call_tool("vibe_store", {"content": atom["content"], "session_id": atom["session_id"]})
                source_ids[stored["id"][:8]] = atom["id"]
        finally:
            client.close()
        write_ms = round((perf_counter() - write_start) * 1000, 1)
        sleep(0.2)

        client = MCPProcess(db_path, sample["sample_id"], 30, sys.executable)
        rows = []
        try:
            client.request("initialize")
            for case in cases:
                baseline, baseline_ms, baseline_tokens = answer(case["question"], [])
                recall_start = perf_counter()
                found = client.call_tool("vibe_recall", {"query": case["question"], "mode": "precision", "top_k": 5})
                recall_ms = round((perf_counter() - recall_start) * 1000, 1)
                memories = [item["content"] for item in found["memories"]]
                augmented, augmented_ms, augmented_tokens = answer(case["question"], memories)
                expected = normalize(case["answer"])
                rows.append({
                    "id": case["id"], "category": case["category"],
                    "evidence_hit": bool(set(case["evidence"]) & {source_ids.get(item["id"]) for item in found["memories"]}),
                    "returned_count": len(memories),
                    "no_memory": {"strict_match": normalize(baseline) == expected,
                                  "token_f1": token_f1(baseline, case["answer"]),
                                  "abstained": normalize(baseline) == "unknown",
                                  "generation_ms": baseline_ms, "prompt_tokens": baseline_tokens},
                    "mcp_memory": {"strict_match": normalize(augmented) == expected,
                                   "token_f1": token_f1(augmented, case["answer"]),
                                   "abstained": normalize(augmented) == "unknown",
                                   "recall_ms": recall_ms, "generation_ms": augmented_ms,
                                   "query_to_answer_ms": round(recall_ms + augmented_ms, 1),
                                   "prompt_tokens": augmented_tokens},
                })
        finally:
            client.close()

    return {
        "source": "https://github.com/snap-research/locomo/blob/main/data/locomo10.json",
        "source_sha256": hashlib.sha256(raw).hexdigest(), "sample_id": sample["sample_id"],
        "selection": f"first {count} official-order category-1 QAs with text-only evidence",
        "model": model_path.name, "model_load_ms": model_load_ms,
        "stored_turns": len(corpus["atoms"]), "write_setup_ms": write_ms,
        "mode": "MCP precision Top-5", "paid_model_calls": 0,
        "rows": rows,
        "summary": {condition: {
            "strict_match": sum(row[condition]["strict_match"] for row in rows),
            "mean_token_f1": round(sum(row[condition]["token_f1"] for row in rows) / len(rows), 3),
            "abstained": sum(row[condition]["abstained"] for row in rows),
            "generation_p50_ms": round(median(row[condition]["generation_ms"] for row in rows), 1),
        } for condition in ("no_memory", "mcp_memory")},
        "limits": "All ten LoCoMo conversations were used in prior retrieval tuning: not independent holdout. Strict normalized exact match undercounts valid paraphrases; token F1 measures overlap, not semantic correctness, and mismatches are not certified factual errors. One conversation/category, no images, original timestamps not restored by MCP writes. Query-to-answer excludes one-time model load and corpus writes. No paid API; local electricity and human review unmeasured. No production default change.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("model_path", type=Path)
    parser.add_argument("--count", type=int, default=11)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run(args.dataset, args.model_path, args.count)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        args.json.write_text(output, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(output)
