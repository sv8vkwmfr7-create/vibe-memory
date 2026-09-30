"""Experiment-only fixed slot selection must not consume gold labels."""

from experiments.longmemeval_lexical_slot_probe import lexical_slot, rank_fused_ids, score


def test_fixed_slot_keeps_first_four_and_does_not_mutate_input():
    ids = ["a", "b", "c", "d", "gold"]
    candidate = lexical_slot(ids, [("noise", 1.0)])
    assert candidate == ["a", "b", "c", "d", "noise"]
    assert ids[-1] == "gold"
    assert score(ids, {"gold"})["hit"]
    assert not score(candidate, {"gold"})["hit"]  # Positive lexical score is not safety.


def test_duplicate_empty_and_nonpositive_winners_leave_ranking_unchanged():
    ids = ["a", "b", "c", "d", "e"]
    for lexical in ([], [("e", 1.0)], [("z", 0.0)], [("z", -1.0)]):
        assert lexical_slot(ids, lexical) == ids
    assert lexical_slot(["a"], [("z", 1.0)]) == ["a", "z"]


def test_fixed_equal_rank_fusion_consensus_ties_and_top5_budget():
    ids = ["a", "b", "c", "d", "e"]
    lexical = [("x", 100.0), ("b", 1.0), ("y", 0.5), ("z", 0.4), ("v", 0.3)]
    candidate = rank_fused_ids(ids, lexical)
    assert candidate == ["b", "a", "x", "c", "y"]
    assert len(set(candidate)) == 5
    assert rank_fused_ids(ids, lexical) == candidate
    assert rank_fused_ids(ids, [("x", 0.0)]) == ids
    assert ids == ["a", "b", "c", "d", "e"]
