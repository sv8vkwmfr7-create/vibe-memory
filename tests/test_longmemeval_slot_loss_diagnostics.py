"""A loss diagnosis must distinguish sole-evidence loss from partial recall loss."""

from experiments.longmemeval_slot_loss_diagnostics import displacement


def test_displacement_distinguishes_total_partial_and_unlabelled_changes():
    baseline = ["a", "b", "c", "d", "e"]
    candidate = ["a", "b", "c", "d", "x"]
    facts = displacement(baseline, candidate, {"e"})
    assert facts["removed_sole_evidence"]
    assert facts["retained_first_four"]
    assert facts["removed_ids"] == ["e"] and facts["added_ids"] == ["x"]
    assert not displacement(baseline, candidate, {"a", "e"})["removed_sole_evidence"]
    assert not displacement(baseline, candidate, {"e", "x"})["removed_sole_evidence"]
    assert not displacement(baseline, baseline, {"e"})["removed_sole_evidence"]
