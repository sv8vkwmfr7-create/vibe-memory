"""Experiment boundary: known-ID cleanup and limited reimport suppression."""

from experiments.forget_plan_probe import run


def test_known_forget_plan_preserves_unrelated_items_and_shows_bypass():
    result = run()
    assert result["unknown_id_rejected_before_mutation"]
    assert result["deleted_ids"] == ["original", "derived-copy"]
    assert result["deleted_edge_ids"] == ["incident-edge"]
    assert result["after"]["retrieved_ids"] == result["after_restart"]["retrieved_ids"]
    assert result["after"]["target_rows"] == 0
    assert result["after"]["incident_edges"] == 0
    assert result["after"]["unrelated_rows"] == 2
    assert result["after"]["unrelated_edges"] == 1
    assert result["known_id_reimport_blocked"] and result["known_source_reimport_blocked"]
    assert result["unlabeled_new_id_reimported"]
    assert "new-id" in result["after_unlabeled_reimport"]["retrieved_ids"]
    assert not result["complete_forgetting_demonstrated"]
