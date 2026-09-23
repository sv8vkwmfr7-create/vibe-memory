"""Experiment-only graph-seed source and negative controls."""

import json
from pathlib import Path

from experiments.graph_seed_source_probe import _graph_corpus, compare


def test_candidate_pool_graph_seeds_can_lose_a_source_case():
    data = json.loads(Path("experiments/causal_source_cases.json").read_text(encoding="utf-8"))
    report = compare(_graph_corpus(data))

    assert report["candidate_any_hit"] == 3
    assert report["variants"]["baseline"]["any_hit"] == 3
    assert report["variants"]["candidate_pool_seeds"]["any_hit"] == 2
    assert report["variants"]["candidate_pool_seeds"]["lost"] == 1
    assert report["variants"]["no_seed_filter"]["any_hit"] == 3


def test_rejected_seed_guard_only_removes_identified_graph_reentries():
    data = json.loads(Path("experiments/causal_source_cases.json").read_text(encoding="utf-8"))
    report = compare(_graph_corpus(data), include_rows=True)

    assert report["variants"]["candidate_pool_seeds"]["negative_any"] == 3
    assert report["variants"]["candidate_pool_rejected_guard"]["negative_any"] == 1
    assert report["variants"]["candidate_pool_rejected_guard"]["lost"] == 1
    for row in report["rows"]:
        guarded = row["variants"]["candidate_pool_rejected_guard"]
        rejected = set(guarded["semantic_seeds"]) - set(guarded["filtered_seeds"])
        assert rejected.isdisjoint(guarded["graph_results"])


def test_candidate_pool_graph_seeds_do_not_clear_wrong_service_top1():
    data = json.loads(Path("experiments/relevance_diagnostic_cases.json").read_text(
        encoding="utf-8"))
    wrong_service = next(case for case in data["cases"] if case["case_id"] == "wrong-service")
    report = compare(_graph_corpus(wrong_service))

    assert report["variants"]["candidate_pool_seeds"]["any_hit"] == 1
    assert report["variants"]["candidate_pool_seeds"]["negative_top1"] == 1
    assert report["variants"]["candidate_pool_rejected_guard"]["any_hit"] == 0
    assert report["variants"]["candidate_pool_rejected_guard"]["negative_top1"] == 1
    assert report["variants"]["no_seed_filter"]["negative_top1"] == 1


def test_unlabeled_negative_metric_is_not_reported_as_zero():
    data = json.loads(Path("experiments/relevance_diagnostic_cases.json").read_text(
        encoding="utf-8"))
    positive = next(case for case in data["cases"] if case["case_id"] == "positive-control")
    report = compare(_graph_corpus(positive))

    assert report["candidate_order"] == "existing"
    assert report["negative_labeled_questions"] == 0
    assert report["variants"]["baseline"]["negative_any"] is None
