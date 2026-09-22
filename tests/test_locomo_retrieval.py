"""LoCoMo dialogue-evidence adapter boundaries."""

from datetime import datetime, timedelta

from experiments.locomo_retrieval import build_corpus, diagnose_budget_candidate_pool
from experiments.session_evaluation import evaluate


def test_build_corpus_uses_only_existing_text_evidence_and_session_times():
    sample = {
        "sample_id": "conv-test",
        "conversation": {
            "session_1_date_time": "1:56 pm on 8 May, 2023",
            "session_1": [
                {"dia_id": "D1:1", "speaker": "A", "text": "The service failed."},
                {"dia_id": "D1:2", "speaker": "B", "text": "Screenshot", "img_url": "https://example.test/image"},
            ],
        },
        "qa": [
            {"question": "What failed?", "evidence": ["D1:1"]},
            {"question": "Missing evidence?", "evidence": ["D9:9"]},
            {"question": "Image evidence?", "evidence": ["D1:2"]},
            {"question": "No evidence?", "evidence": []},
        ],
    }

    corpus, excluded = build_corpus(sample)

    assert len(corpus["atoms"]) == 2
    assert corpus["atoms"][0]["created_at"] == "2023-05-08T13:56:00"
    assert corpus["edges"] == []
    assert corpus["queries"] == [{
        "id": "conv-test-qa-0", "text": "What failed?", "agent_id": "conv-test",
        "tenant_id": "locomo", "cutoff": "2023-05-08T13:56:01",
        "relevant_ids": ["D1:1"],
    }]
    assert excluded == {"missing_evidence": 1, "image_evidence": 1, "no_evidence": 1}


def test_budget_candidate_diagnostic_exposes_gold_lost_before_ranking():
    start = datetime(2023, 5, 8)
    common = {"agent_id": "a", "tenant_id": "locomo", "session_id": "s"}
    atoms = [{**common, "id": "gold", "content": "Caroline joined the LGBTQ support group on May 7",
              "summary": "Caroline joined the LGBTQ support group on May 7",
              "created_at": start.isoformat()}]
    atoms += [{**common, "id": f"noise-{i}", "content": "Caroline plans a group outing",
               "summary": "Caroline plans a group outing",
               "created_at": (start + timedelta(minutes=i + 1)).isoformat()}
              for i in range(100)]
    corpus = {"dataset_id": "synthetic-candidate-cap", "atoms": atoms, "edges": [],
              "queries": [{"id": "q", "text": "When did Caroline join the LGBTQ support group?",
                           "agent_id": "a", "tenant_id": "locomo",
                           "cutoff": (start + timedelta(days=1)).isoformat(),
                           "relevant_ids": ["gold"]}]}

    rows = evaluate(corpus)["rows"]
    assert next(row for row in rows if row["method"] == "keyword")["recall"] == 1
    assert next(row for row in rows if row["method"] == "budget")["recall"] == 0
    assert diagnose_budget_candidate_pool(corpus, rows, 5) == {
        "candidate_limit": 100, "evidence_any_in_pool": 0,
        "bm25_hit_budget_miss": 1, "of_those_absent_from_pool": 1,
        "of_those_present_but_unranked": 0,
    }
