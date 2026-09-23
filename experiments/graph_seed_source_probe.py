"""Experiment-only budget graph-seed and seed-filter comparison."""

import argparse
import hashlib
import json
import math
import statistics
import time
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from experiments.locomo_candidate_order_probe import _fts_bm25_candidates
from experiments.locomo_retrieval import build_corpus
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom
from vibe_memory.retrieval.ppr import recall
from vibe_memory.retrieval.seed_filter import SeedFilter
from vibe_memory.retrieval.strategies import GraphStrategy
from vibe_memory.retrieval import fusion
from vibe_memory.storage.sqlite_store import VibeStorage


VARIANTS = ("baseline", "candidate_pool_seeds", "candidate_pool_rejected_guard",
            "no_seed_filter")


def compare(corpus: dict, candidate_order: str = "existing", top_k: int = 5,
            include_timing: bool = False, include_rows: bool = False) -> dict:
    if top_k < 1 or candidate_order not in ("existing", "fts_bm25"):
        raise ValueError("Positive top_k and known candidate order required")
    if corpus["edges"] and candidate_order == "fts_bm25":
        raise ValueError("FTS-BM25 candidate helper does not preserve graph expansion")
    first = corpus["queries"][0]
    if any(q["agent_id"] != first["agent_id"] or q["tenant_id"] != first["tenant_id"]
           for q in corpus["queries"]):
        raise ValueError("One agent and tenant per comparison")
    store = VibeStorage(":memory:", tenant_id=first["tenant_id"])
    try:
        for atom in corpus["atoms"]:
            store.insert_atom(MemoryAtom(**{
                **atom, "created_at": datetime.fromisoformat(atom["created_at"])
            }))
        for index, (source, target) in enumerate(corpus["edges"]):
            store.insert_edge(Edge(id=f"probe-edge-{index}", from_atom_id=source,
                                   to_atom_id=target, label=EdgeLabel.CAUSAL,
                                   tenant_id=first["tenant_id"]))
        original_candidates = store.get_recall_candidates
        original_graph_search = GraphStrategy.search
        original_filter = SeedFilter.filter
        original_fusion = fusion.rrf_fusion
        limit = max(100, top_k * 20)
        totals = {name: {"any_hit": 0, "macro_recall_sum": 0.0,
                         "negative_top1": 0, "negative_any": 0,
                         "changed_rankings": 0, "rescued": 0, "lost": 0}
                  for name in VARIANTS}
        times = {name: [] for name in VARIANTS}
        candidate_hit = 0
        rows = []
        for index, query in enumerate(corpus["queries"]):
            gold = set(query["relevant_ids"])
            negative = set(query.get("negative_ids", []))
            if not gold or gold & negative:
                raise ValueError("Valid non-overlapping evidence labels required")
            store.get_recall_candidates = original_candidates
            pool = (_fts_bm25_candidates(store, query["agent_id"], query["text"],
                                         limit, query["tenant_id"])
                    if candidate_order == "fts_bm25" else
                    original_candidates(query["agent_id"], query["text"], limit,
                                        query["tenant_id"], top_k, int(limit * 0.2), 2))
            candidate_hit += bool(gold & {atom.id for atom in pool})
            store.get_recall_candidates = lambda *_args, **_kwargs: pool
            rankings = {}
            stages = {}
            for name in VARIANTS[index % len(VARIANTS):] + VARIANTS[:index % len(VARIANTS)]:
                stage = {}

                def traced_filter(self, seeds, storage):
                    kept = original_filter(self, seeds, storage)
                    stage["semantic_seeds"] = [a.id for a in seeds]
                    stage["filtered_seeds"] = [a.id for a in kept]
                    return kept

                def traced_graph(self, seeds, top_k=top_k):
                    actual = pool[:top_k] if name.startswith("candidate_pool_") else seeds
                    result = original_graph_search(self, actual, top_k=top_k)
                    if name == "candidate_pool_rejected_guard":
                        rejected = set(stage.get("semantic_seeds", [])) - set(
                            stage.get("filtered_seeds", []))
                        result = [(aid, score) for aid, score in result if aid not in rejected]
                    stage["graph_seeds"] = [a.id for a in actual]
                    stage["graph_results"] = [aid for aid, _ in result]
                    return result

                def traced_fusion(lists, top_k, weights=None, **kwargs):
                    stage["fusion_lists"] = [[aid for aid, _ in ranked] for ranked in lists]
                    stage["fusion_weights"] = weights
                    return original_fusion(lists, top_k, weights=weights, **kwargs)

                kwargs = {"seed_filter": SimpleNamespace(
                    filter=lambda seeds, _store: list(seeds))} if name == "no_seed_filter" else {}
                start = time.perf_counter()
                with ExitStack() as stack:
                    if include_rows or name == "candidate_pool_rejected_guard":
                        stack.enter_context(patch.object(GraphStrategy, "search", traced_graph))
                        if include_rows:
                            stack.enter_context(patch.object(fusion, "rrf_fusion", traced_fusion))
                        if name != "no_seed_filter":
                            stack.enter_context(patch.object(SeedFilter, "filter", traced_filter))
                    elif name == "candidate_pool_seeds":
                        stack.enter_context(patch.object(GraphStrategy, "search", traced_graph))
                    result = recall(query["text"], query["agent_id"], store,
                                    mode="budget", top_k=top_k,
                                    budget_graph_hops=2, **kwargs)["atoms"]
                if include_timing:
                    times[name].append((time.perf_counter() - start) * 1000)
                rankings[name] = [atom.id for atom in result]
                if include_rows:
                    stage["top_k"] = rankings[name]
                    stages[name] = stage
            if include_rows:
                rows.append({"query_index": index, "positive_ids": sorted(gold),
                             "negative_ids": sorted(negative),
                             "candidate_seeds": [a.id for a in pool[:top_k]],
                             "variants": stages})
            baseline_hit = bool(gold & set(rankings["baseline"]))
            for name, ids in rankings.items():
                item = totals[name]
                hits = len(gold & set(ids))
                item["any_hit"] += hits > 0
                item["macro_recall_sum"] += hits / len(gold)
                item["negative_top1"] += bool(ids and ids[0] in negative)
                item["negative_any"] += bool(negative & set(ids))
                item["changed_rankings"] += ids != rankings["baseline"]
                item["rescued"] += bool(hits) and not baseline_hit
                item["lost"] += baseline_hit and not hits
        count = len(corpus["queries"])
        negative_labeled = sum(bool(query.get("negative_ids"))
                               for query in corpus["queries"])
        report = {"questions": count, "candidate_order": candidate_order,
                  "candidate_limit": limit,
                  "candidate_any_hit": candidate_hit,
                  "negative_labeled_questions": negative_labeled,
                  "variants": {name: {**{key: (value if negative_labeled else None)
                                         if key in ("negative_top1", "negative_any") else value
                                         for key, value in item.items()
                                         if key != "macro_recall_sum"},
                                     "macro_evidence_recall": item["macro_recall_sum"] / count}
                               for name, item in totals.items()}}
        if include_timing:
            report["warm_core_latency_ms"] = {
                name: {"median": statistics.median(values),
                       "p95": sorted(values)[math.ceil(0.95 * len(values)) - 1]}
                for name, values in times.items()}
        if include_rows:
            report["rows"] = rows
        return report
    finally:
        store.conn.close()


def _graph_corpus(data: dict) -> dict:
    return {"atoms": [{**atom, "agent_id": "graph-probe", "tenant_id": "graph-probe",
                       "summary": atom["content"], "created_at": "2026-09-19T00:00:00"}
                      for atom in data["atoms"]],
            "edges": data["edges"],
            "queries": [{**q, "agent_id": "graph-probe", "tenant_id": "graph-probe"}
                        for q in data["queries"]]}


def _aggregate(reports: list[dict]) -> dict:
    count = sum(item["questions"] for item in reports)
    negative_labeled = sum(item["negative_labeled_questions"] for item in reports)
    return {
        "questions": count,
        "candidate_any_hit": sum(item["candidate_any_hit"] for item in reports),
        "negative_labeled_questions": negative_labeled,
        "variants": {
            name: {
                **{key: sum(item["variants"][name][key] for item in reports)
                   for key in ("any_hit", "changed_rankings", "rescued", "lost")},
                "macro_evidence_recall": sum(
                    item["variants"][name]["macro_evidence_recall"] * item["questions"]
                    for item in reports) / count,
                "negative_top1": sum(item["variants"][name]["negative_top1"] or 0
                                     for item in reports) if negative_labeled else None,
                "negative_any": sum(item["variants"][name]["negative_any"] or 0
                                    for item in reports) if negative_labeled else None,
            } for name in VARIANTS},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Official local locomo10.json")
    parser.add_argument("--all-samples", action="store_true")
    parser.add_argument("--graph-fixtures", action="store_true")
    parser.add_argument("--timing", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    samples = json.loads(raw)
    locomo = []
    for sample in samples if args.all_samples else samples[:1]:
        corpus, excluded = build_corpus(sample)
        item = compare(corpus, "fts_bm25", include_timing=args.timing)
        item.update({"sample_id": sample["sample_id"], "excluded": excluded})
        locomo.append(item)
    report = {"source": "https://github.com/snap-research/locomo/blob/main/data/locomo10.json",
              "source_sha256": hashlib.sha256(raw).hexdigest(),
              "locomo_aggregate": _aggregate(locomo), "locomo": locomo}
    if args.graph_fixtures:
        paths = (Path("experiments/causal_source_cases.json"),
                 Path("experiments/relevance_diagnostic_cases.json"))
        source, diagnostic = (json.loads(path.read_text(encoding="utf-8")) for path in paths)
        cases = [(source["dataset_id"], source)] + [
            (case["case_id"], case) for case in diagnostic["cases"]]
        graph_reports = [{"case_id": name, **compare(_graph_corpus(case),
                                                      include_timing=args.timing,
                                                      include_rows=True)}
                         for name, case in cases]
        report["graph_fixtures"] = {
            "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in paths},
            "aggregate": _aggregate(graph_reports), "cases": graph_reports,
            "limits": "Assistant-paraphrased/source-mapped and assistant-authored synthetic labels; not independent graph evidence",
        }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
