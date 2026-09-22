"""Characterize deliberate false-edge contamination at the public report seam."""

from pathlib import Path

from experiments.causal_wrong_anchor_probe import run


CASES = Path(__file__).resolve().parents[1] / "experiments" / "causal_source_cases.json"


def test_false_cross_case_edges_can_harm_bridge_without_changing_defaults():
    report = run(CASES)

    assert report["source_sha256"] == "88124e526f8d653884332f549b3ef9fbff324b6bf50965b87ded3a744c482fbd"
    assert report["evaluation_is_independent"] is False
    assert report["conditions"]["production_defaults_changed"] is False
    assert len(report["variants"]) == 3
    assert all(row["added_false_edges"] == 2 for row in report["variants"])
    assert report["variants"][0]["poisoned"]["causal_bridge"]["negative_top1"] is True
    assert report["variants"][2]["clean"]["causal_bridge"]["recall"] == 1.0
    assert report["variants"][2]["poisoned"]["causal_bridge"]["recall"] == 0.0
    assert all(
        row["poisoned"]["directional_chain"]["negative_top1"] is False
        for row in report["variants"]
    )
    assert "plugin grandchildren" not in str(report)
