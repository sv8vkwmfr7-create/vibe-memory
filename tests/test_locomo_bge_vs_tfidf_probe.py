"""Paired evidence accounting does not treat non-gold text as judged irrelevant."""

from experiments.locomo_bge_vs_tfidf_probe import hit


def test_hit_uses_any_official_evidence_id():
    assert hit(["D1:2", "D1:3"], ["D1:3", "D2:1"])
    assert not hit(["D1:2"], ["D1:3"])
