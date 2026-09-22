"""LoCoMo dialogue-evidence adapter boundaries."""

from experiments.locomo_retrieval import build_corpus


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
