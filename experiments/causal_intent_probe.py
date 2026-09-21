"""Describe answer positions and intent-specific hits on frozen causal chains."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def _positions(atom_ids: set[str], edges: list[list[str]]) -> dict[str, str]:
    incoming = Counter(target for _, target in edges)
    outgoing = Counter(source for source, _ in edges)
    return {
        atom_id: (
            "middle" if incoming[atom_id] and outgoing[atom_id]
            else "initial" if outgoing[atom_id]
            else "terminal" if incoming[atom_id]
            else "isolated"
        )
        for atom_id in atom_ids
    }


def evaluate(
    corpus: dict,
    annotations: list[dict],
    rankings: dict | None = None,
    *,
    corpus_sha256: str | None = None,
) -> dict:
    atom_ids = {atom["id"] for atom in corpus["atoms"]}
    positions = _positions(atom_ids, corpus["edges"])
    if len(annotations) != len(corpus["queries"]):
        raise ValueError("Expected one annotation per query")
    ranking_rows = rankings["rows"] if rankings else None
    if ranking_rows is not None and (
        not corpus_sha256 or rankings.get("corpus_sha256") != corpus_sha256
    ):
        raise ValueError("Ranking corpus SHA256 differs from input corpus")
    if ranking_rows is not None and len(ranking_rows) != len(annotations):
        raise ValueError("Ranking query count differs")
    rows = []
    for index, (query, annotation) in enumerate(zip(corpus["queries"], annotations)):
        query_id = f"query-{index}"
        answers = set(annotation["answer_ids"])
        if (annotation["query_id"] != query_id
                or annotation["intent"] not in {"reason", "solution"}
                or not answers or not answers <= set(query["relevant_ids"])):
            raise ValueError(f"Invalid annotation for {query_id}")
        row = {
            "query_id": query_id,
            "intent": annotation["intent"],
            "answer_positions": dict(sorted(Counter(positions[aid] for aid in answers).items())),
            "all_relevant_positions": dict(sorted(Counter(
                positions[aid] for aid in query["relevant_ids"]
            ).items())),
        }
        if ranking_rows is not None:
            rank_row = ranking_rows[index]
            if rank_row["query_id"] != query_id:
                raise ValueError("Ranking query order differs")
            # The prior report uses stable atom-<corpus-index> aliases.
            answer_aliases = {
                f"atom-{i}" for i, atom in enumerate(corpus["atoms"])
                if atom["id"] in answers
            }
            row["answer_recall_at_5"] = {
                strategy: len(answer_aliases & set(rank_row[strategy]["returned_ids"])) / len(answers)
                for strategy in ("baseline", "causal_bridge", "directional_chain")
            }
            row["top1_hit"] = {
                strategy: bool(rank_row[strategy]["returned_ids"] and
                               rank_row[strategy]["returned_ids"][0] in answer_aliases)
                for strategy in ("baseline", "causal_bridge", "directional_chain")
            }
            preferred_position = "middle" if annotation["intent"] == "reason" else "terminal"
            aliases_by_position = {
                f"atom-{i}" for i, atom in enumerate(corpus["atoms"])
                if positions[atom["id"]] == preferred_position
            }
            baseline_ids = rank_row["baseline"]["returned_ids"]
            oracle_ids = sorted(baseline_ids, key=lambda aid: aid not in aliases_by_position)
            row["position_oracle_top1_hit"] = bool(oracle_ids and oracle_ids[0] in answer_aliases)
            negative_aliases = {
                f"atom-{i}" for i, atom in enumerate(corpus["atoms"])
                if atom["id"] in query.get("negative_ids", [])
            }
            row["position_oracle_negative_top1"] = bool(oracle_ids and oracle_ids[0] in negative_aliases)
            session_by_alias = {
                f"atom-{i}": atom.get("session_id")
                for i, atom in enumerate(corpus["atoms"])
            }
            anchor_session = session_by_alias.get(baseline_ids[0]) if baseline_ids else None
            same_session_position = {
                aid for aid in aliases_by_position
                if anchor_session is not None and session_by_alias[aid] == anchor_session
            }
            scoped_ids = sorted(baseline_ids, key=lambda aid: aid not in same_session_position)
            row["session_proxy_top1_hit"] = bool(scoped_ids and scoped_ids[0] in answer_aliases)
            row["session_proxy_negative_top1"] = bool(scoped_ids and scoped_ids[0] in negative_aliases)
            row["session_proxy_anchor_matches_answer"] = bool(
                anchor_session is not None and
                any(session_by_alias[aid] == anchor_session for aid in answer_aliases)
            )
        rows.append(row)
    by_intent = {}
    for intent in ("reason", "solution"):
        selected = [row for row in rows if row["intent"] == intent]
        by_intent[intent] = {
            "queries": len(selected),
            "answer_positions": dict(sorted(sum(
                (Counter(row["answer_positions"]) for row in selected), Counter()
            ).items())),
        }
        if ranking_rows is not None and selected:
            by_intent[intent]["macro_answer_recall_at_5"] = {
                strategy: sum(row["answer_recall_at_5"][strategy] for row in selected) / len(selected)
                for strategy in ("baseline", "causal_bridge", "directional_chain")
            }
            by_intent[intent]["top1_hit_rate"] = {
                strategy: sum(row["top1_hit"][strategy] for row in selected) / len(selected)
                for strategy in ("baseline", "causal_bridge", "directional_chain")
            }
            by_intent[intent]["position_oracle_top1_hit_rate"] = sum(
                row["position_oracle_top1_hit"] for row in selected
            ) / len(selected)
            by_intent[intent]["position_oracle_negative_top1_cases"] = sum(
                row["position_oracle_negative_top1"] for row in selected
            )
            by_intent[intent]["session_proxy_top1_hit_rate"] = sum(
                row["session_proxy_top1_hit"] for row in selected
            ) / len(selected)
            by_intent[intent]["session_proxy_negative_top1_cases"] = sum(
                row["session_proxy_negative_top1"] for row in selected
            )
            by_intent[intent]["session_proxy_anchor_matches_answer_cases"] = sum(
                row["session_proxy_anchor_matches_answer"] for row in selected
            )
    return {
        "dataset_id": corpus.get("dataset_id", "corpus"),
        "evaluation_is_independent": False,
        "evidence_boundary": "Intent and answer-subset annotations are assistant-authored hypotheses, not independent labels or proof of query intent. Graph positions describe manually supplied directed edges, not causal truth.",
        "conditions": {"queries": len(rows), "atoms": len(atom_ids), "ranking_comparison": rankings is not None, "production_defaults_changed": False},
        "by_intent": by_intent,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--rankings", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus_raw = args.corpus.read_bytes()
    annotations_raw = args.annotations.read_bytes()
    rankings = json.loads(args.rankings.read_text(encoding="utf-8")) if args.rankings else None
    report = evaluate(
        json.loads(corpus_raw.decode("utf-8-sig")),
        json.loads(annotations_raw.decode("utf-8-sig"))["annotations"],
        rankings,
        corpus_sha256=hashlib.sha256(corpus_raw).hexdigest(),
    )
    report["corpus_sha256"] = hashlib.sha256(corpus_raw).hexdigest()
    report["annotations_sha256"] = hashlib.sha256(annotations_raw).hexdigest()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
