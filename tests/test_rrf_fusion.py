import pytest

from vibe_memory.retrieval.fusion import rrf_fusion


def test_empty_inputs_and_zero_result_limit():
    assert rrf_fusion([]) == []
    assert rrf_fusion([[], []]) == []
    assert rrf_fusion([[('a', 10)]], top_k=0) == []


def test_single_list_uses_one_based_ranks_not_original_scores():
    result = rrf_fusion([[('a', -50), ('b', 999)]], k=0)
    assert result == [('a', 1.0), ('b', 0.5)]


def test_overlap_accumulates_once_per_ranked_list_and_changes_order():
    result = rrf_fusion([[('a', 5), ('b', 4)], [('c', 3), ('b', 2)]], k=60)
    assert [key for key, _ in result] == ['b', 'a', 'c']
    assert result[0][1] == pytest.approx(2 / 62)
    assert result[1][1] == pytest.approx(1 / 61)


def test_weights_and_top_k_are_applied_without_mutating_inputs():
    inputs = [[('a', 5)], [('b', 1)]]
    weights = [0, 2]
    assert rrf_fusion(inputs, k=0, top_k=1, weights=weights) == [('b', 2.0)]
    assert inputs == [[('a', 5)], [('b', 1)]]
    assert weights == [0, 2]


def test_ties_preserve_first_encounter_and_missing_weights_use_one():
    assert rrf_fusion([[('a', 1)], [('b', 1)]], k=0, weights=[1]) == [('a', 1), ('b', 1)]


def test_hashable_identifiers_and_empty_strategy_keep_weight_positions():
    assert rrf_fusion([[], [((1, 'a'), 1)]], k=0, weights=[99, 2]) == [((1, 'a'), 2)]
