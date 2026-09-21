"""Causal position and query-intent diagnosis through an anonymous report."""

from experiments.causal_intent_probe import evaluate


def test_report_distinguishes_middle_and_terminal_answers_without_leaking_text():
    corpus = {
        "dataset_id": "public-intent-fixture",
        "atoms": [
            {"id": "symptom", "content": "symptom private marker"},
            {"id": "reason", "content": "reason private marker"},
            {"id": "fix", "content": "fix private marker"},
        ],
        "edges": [["symptom", "reason"], ["reason", "fix"]],
        "queries": [
            {"text": "why private marker", "relevant_ids": ["reason", "fix"], "negative_ids": []},
            {"text": "how private marker", "relevant_ids": ["reason", "fix"], "negative_ids": []},
        ],
    }
    annotations = [
        {"query_id": "query-0", "intent": "reason", "answer_ids": ["reason"]},
        {"query_id": "query-1", "intent": "solution", "answer_ids": ["fix"]},
    ]

    report = evaluate(corpus, annotations)

    assert report["rows"][0]["answer_positions"] == {"middle": 1}
    assert report["rows"][1]["answer_positions"] == {"terminal": 1}
    assert report["by_intent"]["reason"]["answer_positions"] == {"middle": 1}
    assert report["by_intent"]["solution"]["answer_positions"] == {"terminal": 1}
    assert report["evaluation_is_independent"] is False
    assert "private marker" not in str(report)
    assert "symptom" not in str(report)


def test_intent_specific_recall_uses_existing_anonymous_rankings():
    corpus = {
        "atoms": [{"id": "symptom"}, {"id": "reason"}, {"id": "fix"}],
        "edges": [["symptom", "reason"], ["reason", "fix"]],
        "queries": [{"text": "private question", "relevant_ids": ["reason", "fix"]}],
    }
    annotations = [{"query_id": "query-0", "intent": "solution", "answer_ids": ["fix"]}]
    rankings = {"rows": [{"query_id": "query-0", "baseline": {"returned_ids": ["atom-1"]},
                           "causal_bridge": {"returned_ids": ["atom-1", "atom-2"]},
                           "directional_chain": {"returned_ids": ["atom-2"]}}]}

    report = evaluate(corpus, annotations, rankings)

    assert report["by_intent"]["solution"]["macro_answer_recall_at_5"] == {
        "baseline": 0.0, "causal_bridge": 1.0, "directional_chain": 1.0
    }
