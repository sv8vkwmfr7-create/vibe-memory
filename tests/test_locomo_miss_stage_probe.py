"""Stage classifier keeps first-stage and final losses distinct."""

from experiments.locomo_miss_stage_probe import best_rank, loss_stage


def test_classifies_lexical_and_final_evidence_loss():
    gold = {"D1:1"}
    assert loss_stage(gold, set(), set(), set()) == "before_lexical_top5"
    assert loss_stage(gold, gold, set(), set()) == "after_lexical_top5"
    assert loss_stage(gold, set(), set(), gold) == "hit"
    assert best_rank(gold, ["D1:2", "D1:1"]) == 2
    assert best_rank(gold, ["D1:2"]) is None
