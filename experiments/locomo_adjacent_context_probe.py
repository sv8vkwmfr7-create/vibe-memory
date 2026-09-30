"""Report-only LoCoMo comparison: one dialogue turn versus that turn plus its predecessor."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from experiments.locomo_answer_pilot import select_cases
from experiments.locomo_retrieval import build_corpus
from vibe_memory.doctor import MCPProcess


def write_texts(atoms: list[dict], include_previous: bool) -> list[tuple[str, str | None]]:
    previous = None
    texts = []
    for atom in atoms:
        prior = previous if previous and previous["session_id"] == atom["session_id"] else None
        content = atom["content"]
        if include_previous and prior:
            content += "\nPrevious turn: " + prior["content"]
        texts.append((content, prior["id"] if include_previous and prior else None))
        previous = atom
    return texts


def replay(corpus: dict, cases: list[dict], include_previous: bool) -> dict:
    with TemporaryDirectory(prefix="vibe-locomo-adjacent-") as directory:
        db_path = str(Path(directory) / "memory.db")
        texts = write_texts(corpus["atoms"], include_previous)
        source_ids = {}
        included_previous = {}
        original_text = {atom["id"]: atom["content"] for atom in corpus["atoms"]}
        client = MCPProcess(db_path, cases[0]["id"].split("-qa-")[0], 30, sys.executable)
        start = perf_counter()
        try:
            client.request("initialize")
            for atom, (content, prior_id) in zip(corpus["atoms"], texts):
                stored = client.call_tool("vibe_store", {"content": content,
                                                         "session_id": atom["session_id"]})
                source_ids[stored["id"][:8]] = atom["id"]
                included_previous[atom["id"]] = prior_id
        finally:
            client.close()
        write_ms = round((perf_counter() - start) * 1000, 1)
        sleep(0.2)

        rows = []
        client = MCPProcess(db_path, cases[0]["id"].split("-qa-")[0], 30, sys.executable)
        try:
            client.request("initialize")
            for case in cases:
                start = perf_counter()
                result = client.call_tool("vibe_recall", {"query": case["question"],
                                                          "mode": "precision", "top_k": 5})
                recall_ms = round((perf_counter() - start) * 1000, 1)
                returned = [source_ids[item["id"]] for item in result["memories"]]
                visible = set(returned)
                possible = set(returned)
                if include_previous:
                    for item, source_id in zip(result["memories"], returned):
                        prior_id = included_previous[source_id]
                        if prior_id is not None:
                            possible.add(prior_id)
                            if original_text[prior_id] in item["content"]:
                                visible.add(prior_id)
                gold = set(case["evidence"])
                rows.append({"id": case["id"], "direct_hit": bool(gold & set(returned)),
                             "context_coverage": bool(gold & visible),
                             "context_coverage_upper": bool(gold & possible),
                             "returned_ids": returned, "returned_chars": sum(len(item["content"])
                                                                               for item in result["memories"]),
                             "recall_ms": recall_ms})
        finally:
            client.close()
        sleep(0.2)
    return {"write_ms": write_ms, "stored_turns": len(texts),
            "mean_written_chars": round(sum(len(content) for content, _ in texts) / len(texts), 1),
            "over_mcp_300_char_cap": sum(len(content) > 300 for content, _ in texts),
            "rows": rows,
            "direct_hits": sum(row["direct_hit"] for row in rows),
            "context_coverage": sum(row["context_coverage"] for row in rows),
            "context_coverage_upper": sum(row["context_coverage_upper"] for row in rows),
            "recall_p50_ms": round(median(row["recall_ms"] for row in rows), 1),
            "returned_chars_p50": median(row["returned_chars"] for row in rows)}


def run(dataset: Path) -> dict:
    raw = dataset.read_bytes()
    sample = json.loads(raw)[0]
    cases = select_cases(sample, 11)
    corpus, _ = build_corpus(sample)
    baseline = replay(corpus, cases, False)
    adjacent = replay(corpus, cases, True)
    return {"source": "https://github.com/snap-research/locomo/blob/main/data/locomo10.json",
            "source_sha256": hashlib.sha256(raw).hexdigest(), "paid_model_calls": 0,
            "sample_id": sample["sample_id"], "selection": "all 11 eligible category-1 text-only questions",
            "mode": "MCP precision Top-5; current turn first, optional previous turn in same session",
            "baseline": baseline, "previous_turn": adjacent,
            "rescued_direct": [new["id"] for old, new in zip(baseline["rows"], adjacent["rows"])
                               if not old["direct_hit"] and new["direct_hit"]],
            "lost_direct": [old["id"] for old, new in zip(baseline["rows"], adjacent["rows"])
                            if old["direct_hit"] and not new["direct_hit"]],
            "mean_top5_overlap": round(sum(len(set(old["returned_ids"]) & set(new["returned_ids"]))
                                           for old, new in zip(baseline["rows"], adjacent["rows"]))
                                       / len(cases), 2),
            "limits": "Official evidence IDs are not exhaustive relevance labels. Visible context coverage requires the entire previous turn to survive MCP's 300-character response cap; upper coverage ignores truncation and is optimistic. Previous turn is from the same session; no future turn is used. One previously tuned LoCoMo sample; no answer generation, human review, paid API or production change. One run and fixed arm order cannot establish a stable latency difference."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run(args.dataset)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        args.json.write_text(output, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(output)
