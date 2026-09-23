"""Experiment-only FTS candidate-order ablation on text-only LoCoMo evidence."""

import argparse
import hashlib
import json
import math
import re
import statistics
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from experiments.locomo_retrieval import build_corpus
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.retrieval.ppr import recall
from vibe_memory.storage.sqlite_store import VibeStorage


def _fts_bm25_candidates(store: VibeStorage, agent_id: str, query: str,
                         limit: int, tenant_id: str) -> list[MemoryAtom]:
    """Mirror the English graph-free FTS candidate path, changing only ORDER BY."""
    if not store._fts_enabled or re.search(r"[\u3400-\u9fff]", query):
        raise ValueError("This probe supports English FTS only")
    terms = list(dict.fromkeys(
        term.lower() for term in re.findall(r"\w+", query) if len(term) > 1
    ))[:32]
    if not terms:
        raise ValueError("This probe requires query terms")
    quoted = [f'"{term}"' for term in terms]
    matches = [" AND ".join(quoted)]
    any_match = " OR ".join(quoted)
    if any_match != matches[0]:
        matches.append(any_match)
    rows = []
    for match in matches:
        selected = [row["id"] for row in rows]
        exclude = f"AND atoms.id NOT IN ({', '.join('?' for _ in selected)})" if selected else ""
        rows.extend(store.conn.execute(
            f"""SELECT atoms.* FROM atoms_fts
                JOIN atoms ON atoms.rowid = atoms_fts.rowid
                WHERE atoms_fts MATCH ? AND atoms.tenant_id = ?
                  AND atoms.agent_id = ? AND atoms.lifecycle IN ('active', 'warm')
                  {exclude}
                ORDER BY bm25(atoms_fts), atoms_fts.rowid DESC LIMIT ?""",
            (match, tenant_id, agent_id, *selected, limit - len(rows)),
        ).fetchall())
        if len(rows) == limit:
            break
    if len(rows) < limit:
        selected = [row["id"] for row in rows]
        exclude = f"AND id NOT IN ({', '.join('?' for _ in selected)})" if selected else ""
        rows.extend(store.conn.execute(
            f"""SELECT * FROM atoms WHERE tenant_id = ? AND agent_id = ?
                  AND lifecycle IN ('active', 'warm') {exclude}
                ORDER BY created_at DESC, id LIMIT ?""",
            (tenant_id, agent_id, *selected, limit - len(rows)),
        ).fetchall())
    # ponytail: graph-free English-only copy; use a shared seam only if this policy is promoted.
    return [store._row_to_atom(row) for row in rows]


def compare(corpus: dict, top_k: int = 5, include_timing: bool = False,
            diagnose_losses: bool = False) -> dict:
    if top_k < 1 or not corpus["queries"] or corpus["edges"]:
        raise ValueError("Positive top_k, questions, and graph-free corpus required")
    first = corpus["queries"][0]
    if any(q["agent_id"] != first["agent_id"] or q["tenant_id"] != first["tenant_id"]
           for q in corpus["queries"]):
        raise ValueError("One sample/agent/tenant per comparison")
    limit = max(100, top_k * 20)
    store = VibeStorage(":memory:", tenant_id=first["tenant_id"])
    try:
        for row in corpus["atoms"]:
            store.insert_atom(MemoryAtom(**{
                **row, "created_at": datetime.fromisoformat(row["created_at"])
            }))
        original = store.get_recall_candidates

        def ranked_get(agent_id, query, limit, tenant_id=None, **_):
            return _fts_bm25_candidates(store, agent_id, query, limit,
                                        tenant_id or store.tenant_id)

        counts = {name: {"recency": 0, "fts_bm25": 0}
                  for name in ("candidate_any_hit", "top5_any_hit")}
        recall_sums = {"recency": 0.0, "fts_bm25": 0.0}
        times = {"recency": [], "fts_bm25": []}
        rescued = lost = changed = 0
        loss_stage = {"evidence_absent_from_candidates": 0,
                      "evidence_present_but_not_top5": 0}
        strategies = ("semantic", "bm25", "graph", "temporal")
        ablation_hits = {name: 0 for name in strategies}
        loss_path = {"absent_from_strategy_top5": 0,
                     "strategy_top5_but_not_fused_top10": 0,
                     "fused_rank_6_to_10": 0}
        for index, query in enumerate(corpus["queries"]):
            gold = set(query["relevant_ids"])
            if not gold:
                raise ValueError("Official evidence is required")
            pools = {
                "recency": original(query["agent_id"], query["text"], limit,
                                    query["tenant_id"], top_k, int(limit * 0.2), 2),
                "fts_bm25": ranked_get(query["agent_id"], query["text"], limit,
                                       query["tenant_id"]),
            }
            for name, pool in pools.items():
                counts["candidate_any_hit"][name] += bool(gold & {a.id for a in pool})
            ids_by_order = {}
            order = ("recency", "fts_bm25") if index % 2 == 0 else ("fts_bm25", "recency")
            for name in order:
                store.get_recall_candidates = original if name == "recency" else ranked_get
                start = time.perf_counter()
                result = recall(query["text"], query["agent_id"], store,
                                mode="budget", top_k=top_k,
                                strategies=["semantic", "bm25", "graph", "temporal"],
                                budget_graph_hops=2)["atoms"]
                if include_timing:
                    times[name].append((time.perf_counter() - start) * 1000)
                ids = [atom.id for atom in result]
                ids_by_order[name] = ids
                hits = len(gold & set(ids))
                recall_sums[name] += hits / len(gold)
                counts["top5_any_hit"][name] += hits > 0
            old_hit = bool(gold & set(ids_by_order["recency"]))
            new_hit = bool(gold & set(ids_by_order["fts_bm25"]))
            rescued += new_hit and not old_hit
            lost += old_hit and not new_hit
            if old_hit and not new_hit:
                present = bool(gold & {atom.id for atom in pools["fts_bm25"]})
                loss_stage["evidence_present_but_not_top5" if present
                           else "evidence_absent_from_candidates"] += 1
                if diagnose_losses:
                    store.get_recall_candidates = ranked_get
                    from vibe_memory.retrieval import fusion
                    support = {}
                    original_rrf = fusion.rrf_fusion

                    def capture_rrf(ranked_lists, **kwargs):
                        fused = original_rrf(ranked_lists, **kwargs)
                        support["strategy"] = any(
                            aid in gold for ranked in ranked_lists for aid, _ in ranked)
                        support["fused"] = any(aid in gold for aid, _ in fused)
                        return fused

                    with patch.object(fusion, "rrf_fusion", side_effect=capture_rrf):
                        replay = recall(query["text"], query["agent_id"], store,
                                        mode="budget", top_k=top_k,
                                        strategies=list(strategies),
                                        budget_graph_hops=2)["atoms"]
                    if gold & {atom.id for atom in replay} or not support:
                        raise RuntimeError("Loss replay changed during diagnosis")
                    stage = ("absent_from_strategy_top5" if not support["strategy"]
                             else "strategy_top5_but_not_fused_top10"
                             if not support["fused"] else "fused_rank_6_to_10")
                    loss_path[stage] += 1
                    for omitted in strategies:
                        result = recall(query["text"], query["agent_id"], store,
                                        mode="budget", top_k=top_k,
                                        strategies=[name for name in strategies if name != omitted],
                                        budget_graph_hops=2)["atoms"]
                        ablation_hits[omitted] += bool(gold & {atom.id for atom in result})
            changed += ids_by_order["recency"] != ids_by_order["fts_bm25"]
        size = len(corpus["queries"])
        report = {"questions": size, "candidate_limit": limit,
                  **counts, "macro_evidence_recall": {
                      name: value / size for name, value in recall_sums.items()},
                  "rescued_questions": rescued, "lost_questions": lost,
                  "lost_question_stage": loss_stage,
                  "changed_top5_rankings": changed,
                  "limits": "English text-only; graph-free; official evidence is not exhaustive relevance"}
        if include_timing:
            report["warm_core_latency_ms"] = {
                name: {"median": statistics.median(values),
                       "p95": sorted(values)[math.ceil(0.95 * len(values)) - 1]}
                for name, values in times.items()
            }
        if diagnose_losses:
            report["lost_question_omit_one_strategy_hits"] = ablation_hits
            report["lost_question_ranking_path"] = loss_path
        return report
    finally:
        store.conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Official local locomo10.json")
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--all-samples", action="store_true")
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timing", action="store_true")
    parser.add_argument("--diagnose-losses", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.sample_index < 0 or args.max_queries < 0:
        parser.error("sample-index and max-queries must be nonnegative")
    raw = args.dataset.read_bytes()
    samples = json.loads(raw)
    if args.sample_index >= len(samples):
        parser.error("sample-index exceeds dataset size")
    if args.all_samples and (args.sample_index or args.max_queries):
        parser.error("all-samples cannot be combined with sample-index/max-queries")
    reports = []
    for index in range(len(samples)) if args.all_samples else (args.sample_index,):
        corpus, excluded = build_corpus(samples[index])
        if args.max_queries:
            corpus["queries"] = corpus["queries"][:args.max_queries]
        item = compare(corpus, args.top_k, args.timing, args.diagnose_losses)
        item.update({"sample_id": samples[index]["sample_id"], "excluded": excluded})
        reports.append(item)
    if args.all_samples:
        questions = sum(item["questions"] for item in reports)
        report = {"questions": questions, "samples": reports,
                  "candidate_any_hit": {name: sum(item["candidate_any_hit"][name]
                                                  for item in reports)
                                        for name in ("recency", "fts_bm25")},
                  "top5_any_hit": {name: sum(item["top5_any_hit"][name]
                                             for item in reports)
                                   for name in ("recency", "fts_bm25")},
                  "macro_evidence_recall": {name: sum(
                      item["macro_evidence_recall"][name] * item["questions"]
                      for item in reports) / questions
                      for name in ("recency", "fts_bm25")},
                  "rescued_questions": sum(item["rescued_questions"] for item in reports),
                  "lost_questions": sum(item["lost_questions"] for item in reports),
                  "lost_question_stage": {name: sum(item["lost_question_stage"][name]
                                                   for item in reports)
                                          for name in reports[0]["lost_question_stage"]}}
        if args.diagnose_losses:
            report["lost_question_omit_one_strategy_hits"] = {
                name: sum(item["lost_question_omit_one_strategy_hits"][name]
                          for item in reports)
                for name in ("semantic", "bm25", "graph", "temporal")
            }
            report["lost_question_ranking_path"] = {
                name: sum(item["lost_question_ranking_path"][name]
                          for item in reports)
                for name in reports[0]["lost_question_ranking_path"]
            }
    else:
        report = reports[0]
    report["source"] = "https://github.com/snap-research/locomo/blob/main/data/locomo10.json"
    report["source_sha256"] = hashlib.sha256(raw).hexdigest()
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
