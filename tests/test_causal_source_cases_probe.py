"""Source-traceable, assistant-labeled causal direction diagnostics."""

import json
from pathlib import Path

from experiments.directional_holdout_probe import evaluate


CASES = Path(__file__).resolve().parents[1] / "experiments" / "causal_source_cases.json"


def test_causal_source_cases_keep_cause_effect_and_remedy_separate():
    data = json.loads(CASES.read_text(encoding="utf-8"))

    assert data["edges"] == [
        ["console-cause", "console-effect-0"],
        ["console-cause", "console-effect-1"],
        ["proxy-cause", "proxy-effect-0"],
        ["proxy-cause", "proxy-effect-1"],
        ["poller-cause", "poller-effect-0"],
        ["poller-cause", "poller-effect-1"],
    ]
    assert [query["relevant_ids"] for query in data["queries"]] == [
        ["console-cause"], ["proxy-cause"], ["poller-cause"]
    ]
    assert not any("remedy" in endpoint for edge in data["edges"] for endpoint in edge)


def test_source_traced_directional_replay_reports_no_directional_gain():
    data = json.loads(CASES.read_text(encoding="utf-8"))

    report = evaluate(data)

    assert report["conditions"]["atoms"] == 12
    assert report["conditions"]["queries"] == 3
    assert report["conditions"]["production_defaults_changed"] is False
    assert report["evaluation_is_independent"] is False
    assert report["aggregates"]["baseline"]["macro_recall"] == 2 / 3
    assert report["aggregates"]["causal_bridge"]["macro_recall"] == 1.0
    assert report["aggregates"]["directional_chain"]["macro_recall"] == 2 / 3
    assert report["directional_diagnostics"]["outcome_counts"] == {
        "no_primary_outgoing_candidate": 3
    }
    assert all(row["directional_chain"]["negative_hits"] >= 1 for row in report["rows"])
    assert "console-cause" not in str(report)
    assert "plugin grandchildren" not in str(report)
