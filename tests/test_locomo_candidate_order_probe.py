"""Experiment-only candidate order comparison."""

from datetime import datetime, timedelta

import pytest

from experiments.locomo_candidate_order_probe import compare


def test_bm25_candidate_order_rescues_old_evidence_at_the_100_atom_cap():
    start = datetime(2023, 5, 8)
    base = {"agent_id": "a", "tenant_id": "locomo", "session_id": "s"}
    atoms = [{**base, "id": "gold", "content": "Caroline joined the LGBTQ support group on May 7",
              "summary": "Caroline joined the LGBTQ support group on May 7",
              "created_at": start.isoformat()}]
    atoms += [{**base, "id": f"noise-{i}", "content": "Caroline plans a group outing",
               "summary": "Caroline plans a group outing",
               "created_at": (start + timedelta(minutes=i + 1)).isoformat()}
              for i in range(100)]
    corpus = {"dataset_id": "synthetic", "atoms": atoms, "edges": [],
              "queries": [{"id": "q", "text": "When did Caroline join the LGBTQ support group?",
                           "agent_id": "a", "tenant_id": "locomo",
                           "cutoff": (start + timedelta(days=1)).isoformat(),
                           "relevant_ids": ["gold"]}]}

    report = compare(corpus, top_k=5)

    assert report["candidate_any_hit"] == {"recency": 0, "fts_bm25": 1}
    assert report["top5_any_hit"] == {"recency": 0, "fts_bm25": 1}
    assert report["rescued_questions"] == 1
    assert report["lost_questions"] == 0

    corpus["queries"][0]["text"] = "何时加入支持小组"
    with pytest.raises(ValueError, match="English FTS only"):
        compare(corpus, top_k=5)
