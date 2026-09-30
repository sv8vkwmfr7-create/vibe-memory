"""Replay the six lexical-slot losses without changing the selection rule."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from experiments.longmemeval_lexical_slot_probe import lexical_slot, score
from experiments.longmemeval_tfidf_baseline import SHA256, prepare
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


def displacement(baseline, candidate, evidence):
    return {"removed_ids": sorted(set(baseline) - set(candidate)),
            "added_ids": sorted(set(candidate) - set(baseline)),
            "baseline_evidence_ids": sorted(set(baseline) & evidence),
            "candidate_evidence_ids": sorted(set(candidate) & evidence),
            "retained_first_four": baseline[:4] == candidate[:4],
            "removed_sole_evidence": len(set(baseline) & evidence) == 1 and not set(candidate) & evidence}


def run(dataset: Path, report: Path):
    raw, report_raw = dataset.read_bytes(), report.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError("dataset SHA-256 mismatch")
    prior = json.loads(report_raw)
    if prior["source_sha256"] != SHA256 or len(prior["rows"]) != 470:
        raise ValueError("expected pinned full 470-row slot report")
    cases = {case["question_id"]: case for case in json.loads(raw)}
    if len(cases) != 500 or len({row["id"] for row in prior["rows"]}) != 470:
        raise ValueError("duplicate or missing input cases")
    losses = [row for row in prior["rows"] if row["baseline"]["hit"] and not row["candidate"]["hit"]]
    if [row["id"] for row in losses] != prior["summary"]["lost_ids"] or len(losses) != 6:
        raise ValueError("expected the original six losses")
    rows = []
    for row in losses:
        case = cases[row["id"]]
        atoms, evidence = prepare(case)
        store = VibeStorage(":memory:", tenant_id="longmemeval")
        try:
            for atom in atoms:
                store.insert_atom(atom)
            stored = store.get_atoms_by_agent(row["id"])
            index = BM25Strategy()
            index.fit([atom.content for atom in stored])
            lexical = [(stored[i].id, value) for i, value in index.search(case["question"], top_k=5)]
            candidate = lexical_slot(row["baseline_ids"], lexical)
            if lexical[:1] != [tuple(item) for item in row["bm25_top1"]] or candidate != row["candidate_ids"]:
                raise ValueError("lexical score/selection replay mismatch")
            if score(row["baseline_ids"], evidence) != row["baseline"] or score(candidate, evidence) != row["candidate"]:
                raise ValueError("evidence score mismatch")
            facts = displacement(row["baseline_ids"], candidate, evidence)
            atoms_by_id = {atom.id: atom for atom in stored}
            winner = atoms_by_id[lexical[0][0]]
            removed = atoms_by_id[facts["removed_ids"][0]]
            query_tokens = set(index._tokenize(case["question"]))
            rows.append({"id": row["id"], "type": row["type"], **facts,
                         "bm25_winner_score": lexical[0][1],
                         "winner_role": winner.content.split(":", 1)[0],
                         "removed_role": removed.content.split(":", 1)[0],
                         "query_tokens": sorted(query_tokens),
                         "winner_shared_tokens": sorted(query_tokens & set(index._tokenize(winner.content))),
                         "removed_shared_tokens": sorted(query_tokens & set(index._tokenize(removed.content))),
                         "total_official_evidence_turns": len(evidence),
                         "baseline_evidence_recall": row["baseline"]["evidence_recall"],
                         "candidate_evidence_recall": row["candidate"]["evidence_recall"]})
        finally:
            store.conn.close()
    return {"source_sha256": SHA256, "slot_report_sha256": hashlib.sha256(report_raw).hexdigest(),
            "rows": rows, "summary": {"replayed_losses": len(rows),
                "removed_sole_evidence": sum(row["removed_sole_evidence"] for row in rows),
                "winner_roles": dict(Counter(row["winner_role"] for row in rows))},
            "production_defaults_changed": False, "paid_api_calls": 0,
            "evaluation_is_independent": False,
            "limits": "Post-hoc diagnosis of six observed failures, not a new benchmark or fix. Original fixed Top-5 rule and scores replayed. No raw dialogue/answers saved, model encoding, generation or timing measurement. Unlabelled lexical winners are not assumed irrelevant or harmful. Roles/term overlap are observations, not validated routing rules."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--report", type=Path, default=Path("results/longmemeval_lexical_slot_probe.json"))
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.dataset, args.report)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
