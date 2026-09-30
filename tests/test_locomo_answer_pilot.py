"""Selection and scoring boundaries for the report-only answer pilot."""

from experiments.locomo_answer_pilot import normalize, select_cases, token_f1


def test_select_cases_keeps_only_eligible_single_hop_text_answers():
    sample = {
        "sample_id": "example", "conversation": {
            "session_1_date_time": "1:56 pm on 8 May, 2023",
            "session_1": [
                {"dia_id": "D1:1", "speaker": "A", "text": "I live in Paris."},
                {"dia_id": "D1:2", "speaker": "B", "text": "A picture", "img_url": "https://example.test/pic"},
            ],
        },
        "qa": [
            {"question": "Where?", "answer": "Paris", "category": 1, "evidence": ["D1:1"]},
            {"question": "What picture?", "answer": "A picture", "category": 1, "evidence": ["D1:2"]},
            {"question": "When?", "answer": "May", "category": 2, "evidence": ["D1:1"]},
        ],
    }

    assert [case["id"] for case in select_cases(sample, 2)] == ["example-qa-0"]
    assert normalize("The Paris!") == normalize("Paris")
    assert normalize("unknown") != normalize("Paris")
    assert token_f1("She lives in Paris", "Paris") > 0
    assert token_f1("London", "Paris") == 0
