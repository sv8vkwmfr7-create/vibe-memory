"""Direction-controlled public replay at the existing experiment report boundary."""

import json
from pathlib import Path

from experiments.safe_relation_rerank_probe import run


CASES = Path(__file__).resolve().parents[1] / "experiments" / "safe_relation_rerank_cases.json"


def test_cause_to_effect_edges_do_not_inherit_legacy_directional_gain(tmp_path):
    data = json.loads(CASES.read_text(encoding="utf-8"))
    for case in data["cases"]:
        if case["role"] == "half_hit":
            assert case["target_id"] == "cause"
            case["edges"] = [["cause", "anchor-0"], ["cause", "anchor-1"]]
    data["dataset_id"] = "causal-direction-controlled-v1"
    controlled = tmp_path / "causal-direction.json"
    controlled.write_text(json.dumps(data), encoding="utf-8")

    legacy_report = run(CASES)
    controlled_report = run(controlled)

    assert legacy_report["summary"]["half_hit_cases"] == 3
    assert legacy_report["summary"]["directional_chain_target_recall_at_5"] == 1.0
    assert controlled_report["summary"]["half_hit_cases"] == 3
    assert controlled_report["summary"]["baseline_target_recall_at_5"] == 0.0
    assert controlled_report["summary"]["causal_bridge_target_recall_at_5"] == 1.0
    assert controlled_report["summary"]["directional_chain_target_recall_at_5"] == 0.0
    assert controlled_report["summary"]["eligible_for_default"] is False


def test_wrong_cause_fork_does_not_get_directional_top1_promotion(tmp_path):
    data = json.loads(CASES.read_text(encoding="utf-8"))
    wrong_cause = next(
        case for case in data["cases"] if case["case_id"] == "jointly-wrong-convergence"
    )
    wrong_cause["edges"] = [
        ["negative-bridge", "anchor-0"],
        ["negative-bridge", "anchor-1"],
    ]
    controlled = tmp_path / "wrong-cause-fork.json"
    controlled.write_text(json.dumps(data), encoding="utf-8")

    report = run(controlled)
    guard = next(row for row in report["rows"] if row["case_id"] == "jointly-wrong-convergence")

    assert guard["causal_bridge_negative_top1"] is True
    assert guard["directional_negative_top1"] is False
    assert report["summary"]["eligible_for_default"] is False
