"""Check the experiment's observed deletion boundaries, not a new SDK contract."""

from experiments.forget_action_probe import run


def test_forget_probe_exposes_copy_and_reimport_boundaries():
    report = run()
    assert report["before"]["original_present"]
    assert report["forget_returned"] is True
    assert report["after"]["original_present"] is False
    assert report["after"]["original_in_storage"] is False
    assert report["after"]["original_in_semantic_cache"] is False
    assert report["after"]["original_in_bm25_cache"] is False
    assert report["after"]["derived_copy_present"] is True
    assert report["after_restart"]["original_present"] is False
    assert report["after_restart"]["derived_copy_present"] is True
    assert report["after_reimport"]["original_present"] is True
    assert report["complete_forgetting_demonstrated"] is False
    assert report["production_changed"] is False
