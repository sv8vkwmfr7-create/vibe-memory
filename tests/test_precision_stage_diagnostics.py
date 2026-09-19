"""Frozen stage diagnostics; characterize the failure before changing defaults."""

from pathlib import Path

from experiments.precision_stage_diagnostics import run


CASES = Path(__file__).resolve().parents[1] / "experiments" / "precision_stage_cases.json"


def test_three_causal_reasons_are_found_by_graph_and_fusion_then_lost_by_rerank():
    report = run(CASES)
    half_hits = [row for row in report["rows"] if row["role"] == "half_hit"]

    assert len(half_hits) == 3
    assert {row["baseline_failure_stage"] for row in half_hits} == {"final_rerank"}
    assert all(row["target_ranks"]["graph"] is not None for row in half_hits)
    assert all(row["target_ranks"]["fused"] is not None for row in half_hits)
    assert all(row["target_ranks"]["final"] is None for row in half_hits)
    assert report["summary"]["baseline_target_recall_at_5"] == 0.0
    assert report["summary"]["causal_bridge_target_recall_at_5"] == 1.0


def test_guards_expose_no_edge_stability_and_jointly_wrong_bridge_risk():
    report = run(CASES)
    guards = {row["case_id"]: row for row in report["rows"] if row["role"] == "guard"}

    assert guards["no-causal-edge"]["baseline_ids"] == guards["no-causal-edge"]["bridge_ids"]
    assert guards["jointly-wrong-bridge"]["baseline_negative_top1"] is False
    assert guards["jointly-wrong-bridge"]["bridge_negative_top1"] is True
    assert report["summary"]["safe_to_enable_bridge_by_default"] is False


def test_stage_report_is_repeatable_and_carries_evidence_limits():
    first = run(CASES)
    second = run(CASES)

    assert first == second
    assert first["dataset_id"] == "precision-stage-diagnostics-v1"
    assert first["evaluation_is_independent"] is False
    assert "not" in first["evidence_boundary"].lower()
