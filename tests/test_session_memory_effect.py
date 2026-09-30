"""The experiment report must distinguish usable evidence from harmful recall."""

from experiments.session_evaluation import evaluate


def test_session_report_exposes_evidence_and_known_harmful_memories():
    data = {
        "dataset_id": "synthetic-correction-v1",
        "atoms": [
            {"id": "old", "agent_id": "agent", "tenant_id": "default", "session_id": "s1",
             "content": "The preferred timeout is 30 seconds", "summary": "timeout 30",
             "created_at": "2026-01-01T00:00:00"},
            {"id": "new", "agent_id": "agent", "tenant_id": "default", "session_id": "s2",
             "content": "Correction: the preferred timeout is 60 seconds", "summary": "timeout 60",
             "created_at": "2026-01-02T00:00:00"},
        ],
        "queries": [{"id": "q", "text": "preferred timeout", "agent_id": "agent",
                     "tenant_id": "default", "cutoff": "2026-01-03T00:00:00",
                     "relevant_ids": ["new"], "negative_ids": ["old"]}],
    }

    report = evaluate(data, top_k=2)
    for row in report["rows"]:
        assert row["evidence_hit"] == ("new" in row["returned_ids"])
        assert row["known_harmful_hit"] == ("old" in row["returned_ids"])
    assert report["evidence"].startswith("retrieval-only")
