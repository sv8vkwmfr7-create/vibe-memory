"""Frozen half-query-content support gate on the saved lexical-slot report."""

import argparse
import hashlib
import json
from pathlib import Path

import sklearn
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from experiments.longmemeval_lexical_slot_probe import lexical_slot, score
from experiments.longmemeval_tfidf_baseline import SHA256, prepare
from vibe_memory.retrieval.strategies import BM25Strategy


def content_support(query: str, document: str) -> dict:
    tokenizer = BM25Strategy()
    terms = set(tokenizer._tokenize(query)) - ENGLISH_STOP_WORDS
    shared = terms & set(tokenizer._tokenize(document))
    # ponytail: exact tokens only; synonyms/factual support require separate validation.
    return {"query_content_terms": sorted(terms), "shared_terms": sorted(shared),
            "allowed": bool(terms) and 2 * len(shared) >= len(terms)}


def run(dataset: Path, report: Path) -> dict:
    raw, report_raw = dataset.read_bytes(), report.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError("dataset SHA-256 mismatch")
    cases = json.loads(raw)
    selected = [case for case in cases if not case["question_id"].endswith("_abs")]
    prior = json.loads(report_raw)
    if len(cases) != 500 or len({case["question_id"] for case in cases}) != 500 or len(selected) != 470:
        raise ValueError("expected 500 unique cases, 470 non-abstention")
    if prior["source_sha256"] != SHA256 or [row["id"] for row in prior["rows"]] != [case["question_id"] for case in selected]:
        raise ValueError("saved report source/IDs/order mismatch")
    rows = []
    for case, previous in zip(selected, prior["rows"]):
        atoms, evidence = prepare(case)
        by_id = {atom.id: atom for atom in atoms}
        baseline = previous["baseline_ids"]
        lexical = previous["bm25_top1"]
        if len(baseline) != 5 or len(set(baseline)) != 5 or not set(baseline) <= by_id.keys():
            raise ValueError("invalid baseline Top-5")
        if lexical_slot(baseline, lexical) != previous["candidate_ids"]:
            raise ValueError("saved slot rule mismatch")
        if score(baseline, evidence) != previous["baseline"] or score(previous["candidate_ids"], evidence) != previous["candidate"]:
            raise ValueError("saved evidence score mismatch")
        support = content_support(case["question"], by_id[lexical[0][0]].content.split(": ", 1)[1]) if lexical else {"allowed": False, "query_content_terms": [], "shared_terms": []}
        candidate = lexical_slot(baseline, lexical) if support["allowed"] else list(baseline)
        rows.append({"id": previous["id"], "type": previous["type"],
                     "baseline_ids": baseline, "ungated_ids": previous["candidate_ids"],
                     "candidate_ids": candidate, "support": support,
                     "baseline": previous["baseline"], "ungated": previous["candidate"],
                     "candidate": score(candidate, evidence), "tfidf_hit": previous["tfidf_hit"]})
    def summarize(group):
        return {"count": len(group),
                "baseline_hits": sum(row["baseline"]["hit"] for row in group),
                "ungated_hits": sum(row["ungated"]["hit"] for row in group),
                "candidate_hits": sum(row["candidate"]["hit"] for row in group),
                "tfidf_hits": sum(row["tfidf_hit"] for row in group),
                "changed_lists": sum(row["baseline_ids"] != row["candidate_ids"] for row in group),
                "rescued_ids": [row["id"] for row in group if not row["baseline"]["hit"] and row["candidate"]["hit"]],
                "lost_ids": [row["id"] for row in group if row["baseline"]["hit"] and not row["candidate"]["hit"]],
                "previous_rescues_retained": sum(not row["baseline"]["hit"] and row["ungated"]["hit"] and row["candidate"]["hit"] for row in group),
                "previous_losses_recovered": sum(row["baseline"]["hit"] and not row["ungated"]["hit"] and row["candidate"]["hit"] for row in group),
                "mean_evidence_recall": sum(row["candidate"]["evidence_recall"] for row in group) / len(group)}
    stopwords = sorted(ENGLISH_STOP_WORDS)
    return {"source_sha256": SHA256, "slot_report_sha256": hashlib.sha256(report_raw).hexdigest(),
            "rule": "Keep frozen BM25-top1 slot only if at least half the distinct non-stopword query tokens occur in winner content. No content terms means unchanged. No threshold sweep or label-based routing.",
            "sklearn_version": sklearn.__version__, "stopwords": stopwords,
            "stopwords_sha256": hashlib.sha256("\n".join(stopwords).encode()).hexdigest(),
            "summary": summarize(rows), "by_type": {kind: summarize([row for row in rows if row["type"] == kind]) for kind in sorted({row["type"] for row in rows})},
            "rows": rows, "evaluation_is_independent": False, "eligible_for_default": False,
            "paid_api_calls": 0, "production_defaults_changed": False,
            "limits": "Offline ablation on 470 previously inspected cases, hypothesis chosen after six-loss diagnosis. Saved MiniLM and BM25 winner ranks/scores inherited; no re-encoding or BM25 ranking changes. Exact-word support is not answer correctness or harm detection. English stopword list, not a Chinese gate. No new downloads, final answers, independent review, live SDK/MCP timing, onboarding/memory measurement or default changes."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--report", type=Path, default=Path("results/longmemeval_lexical_slot_probe.json"))
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.dataset, args.report)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
