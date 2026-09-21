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
    rankings = {"rows": [{"query_id": "query-0", "baseline": {"returned_ids": ["atom-1", "atom-2"]},
                           "causal_bridge": {"returned_ids": ["atom-1", "atom-2"]},
                           "directional_chain": {"returned_ids": ["atom-2"]}}]}

    report = evaluate(corpus, annotations, rankings)

    assert report["by_intent"]["solution"]["macro_answer_recall_at_5"] == {
        "baseline": 1.0, "causal_bridge": 1.0, "directional_chain": 1.0
    }
    assert report["by_intent"]["solution"]["top1_hit_rate"] == {
        "baseline": 0.0, "causal_bridge": 0.0, "directional_chain": 1.0
    }
    assert report["by_intent"]["solution"]["position_oracle_top1_hit_rate"] == 1.0


def test_position_only_rerank_can_promote_wrong_terminal_from_other_issue():
    corpus = {
        "atoms": [{"id": "wrong_fix"}, {"id": "symptom"}, {"id": "right_fix"}, {"id": "wrong_cause"}],
        "edges": [["wrong_cause", "wrong_fix"], ["symptom", "right_fix"]],
        "queries": [{"text": "issue", "relevant_ids": ["right_fix"], "negative_ids": ["wrong_fix"]}],
    }
    annotations = [{"query_id": "query-0", "intent": "solution", "answer_ids": ["right_fix"]}]
    rankings = {"rows": [{"query_id": "query-0", **{
        strategy: {"returned_ids": ["atom-1", "atom-0", "atom-2"]}
        for strategy in ("baseline", "causal_bridge", "directional_chain")
    }}]}

    report = evaluate(corpus, annotations, rankings)

    assert report["rows"][0]["position_oracle_top1_hit"] is False
    assert report["rows"][0]["position_oracle_negative_top1"] is True
