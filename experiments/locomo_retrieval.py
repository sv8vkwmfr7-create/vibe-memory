"""Text-only LoCoMo dialogue-evidence recall through the existing local evaluator."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from experiments.session_evaluation import evaluate


def build_corpus(sample: dict) -> tuple[dict, dict[str, int]]:
    conversation = sample["conversation"]
    sessions = sorted(
        (key for key in conversation if re.fullmatch(r"session_\d+", key)),
        key=lambda key: int(key.split("_")[1]),
    )
    atoms = []
    image_ids = set()
    for session in sessions:
        timestamp = datetime.strptime(
            conversation[f"{session}_date_time"], "%I:%M %p on %d %B, %Y"
        ).isoformat()
        for turn in conversation[session]:
            atom_id = turn["dia_id"]
            if turn.get("img_url"):
                image_ids.add(atom_id)
            content = f'{turn["speaker"]}: {turn["text"]}'
            atoms.append({
                "id": atom_id, "agent_id": sample["sample_id"],
                "tenant_id": "locomo", "session_id": session,
                "content": content, "summary": content, "created_at": timestamp,
            })
    ids = {atom["id"] for atom in atoms}
    if len(ids) != len(atoms):
        raise ValueError("Duplicate LoCoMo dialogue IDs")
    cutoff = (max(datetime.fromisoformat(atom["created_at"]) for atom in atoms)
              + timedelta(seconds=1)).isoformat()
    excluded = {"missing_evidence": 0, "image_evidence": 0, "no_evidence": 0}
    queries = []
    for index, qa in enumerate(sample["qa"]):
        evidence = qa.get("evidence") or []
        if not evidence:
            excluded["no_evidence"] += 1
        elif not set(evidence) <= ids:
            excluded["missing_evidence"] += 1
        elif set(evidence) & image_ids:
            excluded["image_evidence"] += 1
        else:
            queries.append({
                "id": f'{sample["sample_id"]}-qa-{index}', "text": qa["question"],
                "agent_id": sample["sample_id"], "tenant_id": "locomo",
                "cutoff": cutoff, "relevant_ids": evidence,
            })
    return {
        "dataset_id": f'locomo-{sample["sample_id"]}-text-dialogue',
        "atoms": atoms, "edges": [], "queries": queries,
    }, excluded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Official local locomo10.json")
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--max-queries", type=int, default=0,
                        help="First N eligible questions; 0 runs all")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.sample_index < 0 or args.max_queries < 0:
        parser.error("sample-index and max-queries must be nonnegative")
    raw = args.dataset.read_bytes()
    samples = json.loads(raw)
    if args.sample_index >= len(samples):
        parser.error("sample-index exceeds dataset size")
    corpus, excluded = build_corpus(samples[args.sample_index])
    eligible_count = len(corpus["queries"])
    if args.max_queries:
        corpus["queries"] = corpus["queries"][:args.max_queries]
    result = evaluate(corpus, top_k=args.top_k)
    methods = {}
    for method in ("no_memory", "keyword", "tfidf", "budget"):
        rows = [row for row in result["rows"] if row["method"] == method]
        methods[method] = {
            "macro_evidence_recall": sum(row["recall"] for row in rows) / len(rows),
            "any_evidence_hit_rate": sum(row["recall"] > 0 for row in rows) / len(rows),
            "all_evidence_hit_rate": sum(row["recall"] == 1 for row in rows) / len(rows),
        }
    report = {
        "source": "https://github.com/snap-research/locomo/blob/main/data/locomo10.json",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "sample_id": samples[args.sample_index]["sample_id"],
        "question_selection": "first eligible questions in official order",
        "eligible_questions": eligible_count,
        "evaluated_questions": len(corpus["queries"]),
        "excluded": excluded, "top_k": args.top_k,
        "unit": "dialogue turn; official evidence IDs",
        "limits": "text-only evidence retrieval, no image/QA answer scoring; graph has no edges",
        "methods": methods,
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
