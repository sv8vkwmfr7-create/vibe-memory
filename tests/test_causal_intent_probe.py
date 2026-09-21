"""Causal position and query-intent diagnosis through an anonymous report."""

import hashlib
import json

import pytest

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
    digest = hashlib.sha256(json.dumps(corpus).encode()).hexdigest()
    rankings["corpus_sha256"] = digest

    report = evaluate(corpus, annotations, rankings, corpus_sha256=digest)

    assert report["by_intent"]["solution"]["macro_answer_recall_at_5"] == {
        "baseline": 1.0, "causal_bridge": 1.0, "directional_chain": 1.0
    }
    assert report["by_intent"]["solution"]["top1_hit_rate"] == {
        "baseline": 0.0, "causal_bridge": 0.0, "directional_chain": 1.0
    }
    assert report["by_intent"]["solution"]["position_oracle_top1_hit_rate"] == 1.0


def test_position_only_rerank_can_promote_wrong_terminal_from_other_issue():
    corpus = {
        "atoms": [{"id": "wrong_fix", "session_id": "other"},
                  {"id": "symptom", "session_id": "current"},
                  {"id": "right_fix", "session_id": "current"},
                  {"id": "wrong_cause", "session_id": "other"}],
        "edges": [["wrong_cause", "wrong_fix"], ["symptom", "right_fix"]],
        "queries": [{"text": "issue", "relevant_ids": ["right_fix"], "negative_ids": ["wrong_fix"]}],
    }
    annotations = [{"query_id": "query-0", "intent": "solution", "answer_ids": ["right_fix"]}]
    rankings = {"rows": [{"query_id": "query-0", **{
        strategy: {"returned_ids": ["atom-1", "atom-0", "atom-2"]}
        for strategy in ("baseline", "causal_bridge", "directional_chain")
    }}]}
    digest = hashlib.sha256(json.dumps(corpus).encode()).hexdigest()
    rankings["corpus_sha256"] = digest

    report = evaluate(corpus, annotations, rankings, corpus_sha256=digest)

    assert report["rows"][0]["position_oracle_top1_hit"] is False
    assert report["rows"][0]["position_oracle_negative_top1"] is True
    assert report["rows"][0]["session_proxy_top1_hit"] is True
    assert report["rows"][0]["session_proxy_negative_top1"] is False


def test_session_proxy_fails_when_first_anchor_belongs_to_wrong_issue():
    corpus = {
        "atoms": [{"id": "wrong_start", "session_id": "other"},
                  {"id": "wrong_fix", "session_id": "other"},
                  {"id": "right_fix", "session_id": "current"},
                  {"id": "right_start", "session_id": "current"}],
        "edges": [["wrong_start", "wrong_fix"], ["right_start", "right_fix"]],
        "queries": [{"text": "issue", "relevant_ids": ["right_fix"], "negative_ids": ["wrong_fix"]}],
    }
    annotations = [{"query_id": "query-0", "intent": "solution", "answer_ids": ["right_fix"]}]
    rankings = {"rows": [{"query_id": "query-0", **{
        strategy: {"returned_ids": ["atom-0", "atom-1", "atom-2"]}
        for strategy in ("baseline", "causal_bridge", "directional_chain")
    }}]}
    digest = hashlib.sha256(json.dumps(corpus).encode()).hexdigest()
    rankings["corpus_sha256"] = digest

    report = evaluate(corpus, annotations, rankings, corpus_sha256=digest)

    assert report["rows"][0]["session_proxy_anchor_matches_answer"] is False
    assert report["rows"][0]["session_proxy_top1_hit"] is False
    assert report["rows"][0]["session_proxy_negative_top1"] is True


def test_rankings_from_a_different_corpus_order_are_rejected():
    original_corpus = {
        "atoms": [{"id": "answer"}, {"id": "other"}],
        "edges": [],
        "queries": [{"text": "question", "relevant_ids": ["answer"]}],
    }
    corpus = {**original_corpus, "atoms": list(reversed(original_corpus["atoms"]))}
    original_hash = hashlib.sha256(json.dumps(original_corpus).encode()).hexdigest()
    current_hash = hashlib.sha256(json.dumps(corpus).encode()).hexdigest()
    annotations = [{"query_id": "query-0", "intent": "reason", "answer_ids": ["answer"]}]
    rankings = {
        "corpus_sha256": original_hash,
        "rows": [{"query_id": "query-0", **{
            strategy: {"returned_ids": ["atom-0"]}
            for strategy in ("baseline", "causal_bridge", "directional_chain")
        }}],
    }

    with pytest.raises(ValueError, match="corpus SHA256"):
        evaluate(corpus, annotations, rankings, corpus_sha256=current_hash)
