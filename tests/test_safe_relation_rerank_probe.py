"""Directional relation rerank experiment with explicit safety boundaries."""

from pathlib import Path

from experiments.safe_relation_rerank_probe import run


CASES = Path(__file__).resolve().parents[1] / "experiments" / "safe_relation_rerank_cases.json"


def test_directional_chain_keeps_bridge_recall_without_changing_defaults():
    report = run(CASES)

    assert report["summary"]["half_hit_cases"] == 3
    assert report["summary"]["baseline_target_recall_at_5"] == 0.0
    assert report["summary"]["causal_bridge_target_recall_at_5"] == 1.0
    assert report["summary"]["directional_chain_target_recall_at_5"] == 1.0
    assert report["conditions"]["production_defaults_changed"] is False


def test_directional_chain_rejects_convergence_reversal_and_no_edge_changes():
    report = run(CASES)
    guards = {row["case_id"]: row for row in report["rows"] if row["role"] == "guard"}

    assert guards["no-causal-edge"]["baseline_ids"] == guards["no-causal-edge"]["directional_ids"]
    assert guards["jointly-wrong-convergence"]["causal_bridge_negative_top1"] is True
    assert guards["jointly-wrong-convergence"]["directional_negative_top1"] is False
    assert guards["reversed-direction"]["directional_negative_top1"] is False
    assert report["summary"]["directional_negative_top1_cases"] == 0
    assert report["summary"]["synthetic_guards_passed"] is True


def test_report_is_repeatable_but_not_default_eligible_without_independent_evidence():
    first = run(CASES)
    second = run(CASES)

    assert first == second
    assert first["dataset_id"] == "safe-relation-rerank-v1"
    assert first["evaluation_is_independent"] is False
    assert first["summary"]["eligible_for_default"] is False
