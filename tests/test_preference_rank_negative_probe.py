"""Finding gold and contradictory advice simultaneously is not a safe answer."""

from experiments.preference_rank_negative_probe import judged


def test_preference_metrics_do_not_hide_contradictory_top1():
    result = judged(["old", "current"], "current", {"old"})
    assert result["target_top5"] and not result["target_top1"]
    assert result["known_negative_top1"]
    assert result["known_negative_ids"] == ["old"]
    assert not judged([], "current", {"old"})["known_negative_top1"]
