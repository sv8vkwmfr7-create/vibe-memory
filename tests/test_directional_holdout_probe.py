"""Private-corpus directional rerank comparison through its report interface."""

from experiments.directional_holdout_probe import evaluate


PUBLIC_FIXTURE = {
    "dataset_id": "directional-holdout-test",
    "atoms": [
        {"id": "anchor-0", "session_id": "s", "content": "orders orders export export request hangs timeout incident"},
        {"id": "cause", "session_id": "s", "content": "database connection pool exhausted; increase capacity"},
        {"id": "anchor-1", "session_id": "s", "content": "orders export request request hangs hangs timeout retry"},
        {"id": "noise-0", "session_id": "n", "content": "orders export request hangs timeout dashboard"},
        {"id": "noise-1", "session_id": "n", "content": "orders export request hangs timeout archive"},
        {"id": "noise-2", "session_id": "n", "content": "orders export request hangs timeout staging"},
        {"id": "noise-3", "session_id": "n", "content": "orders export request hangs timeout benchmark"},
    ],
    "edges": [["anchor-0", "cause"], ["cause", "anchor-1"]],
    "queries": [
        {
            "text": "orders export request hangs timeout",
            "relevant_ids": ["cause"],
            "negative_ids": ["noise-0", "noise-1", "noise-2", "noise-3"],
        }
    ],
}


def test_report_compares_three_strategies_without_private_identifiers_or_text():
    report = evaluate(PUBLIC_FIXTURE)

    assert set(report["aggregates"]) == {"baseline", "causal_bridge", "directional_chain"}
    assert report["aggregates"]["baseline"]["macro_recall"] == 0.0
    assert report["aggregates"]["directional_chain"]["macro_recall"] == 1.0
    assert report["conditions"]["production_defaults_changed"] is False
    assert report["evaluation_is_independent"] is False
    diagnostic = report["rows"][0]["directional_diagnostic"]
    assert diagnostic["common_anchor_count"] >= 2
    assert diagnostic["supported_candidate_count"] == 1
    assert diagnostic["outcome"] == "triggered"
    rendered = str(report)
    assert "database connection pool exhausted" not in rendered
    assert "anchor-0" not in rendered


def test_report_is_repeatable_and_exposes_ranking_changes():
    first = evaluate(PUBLIC_FIXTURE)
    second = evaluate(PUBLIC_FIXTURE)

    assert first == second
    assert first["rows"][0]["query_id"] == "query-0"
    assert first["rows"][0]["directional_chain"]["ranking_changed"] is True
    assert first["directional_diagnostics"]["outcome_counts"] == {"triggered": 1}
