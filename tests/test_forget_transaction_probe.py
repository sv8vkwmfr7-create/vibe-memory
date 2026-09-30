"""One temporary-database check for atomic cleanup and scoped source suppression."""

from experiments.forget_transaction_probe import run


def test_atomic_source_forgetting_rolls_back_and_protects_other_sources():
    report = run()
    assert report["rollback_restored_all_rows"]
    assert report["missing_lineage_rejected"]
    assert report["foreign_parent_rejected"]
    assert report["unknown_source_rejected"]
    assert report["second_writer_blocked_during_transaction"]
    assert report["deleted_ids"] == ["chain-copy", "copy", "mixed-summary", "original"]
    assert report["deleted_edges"] == ["incident-chain", "incident-original"]
    assert report["after"]["local_ids"] == ["keep", "keep-2"]
    assert report["after"]["edge_ids"] == ["foreign-edge", "protected-edge"]
    assert report["after"]["forgotten_fts_matches"] == 0
    assert report["after"]["foreign_ids"] == ["foreign-keep", "foreign-original"]
    assert set(report["after"]["retrieved_ids"]).issubset({"keep", "keep-2"})
    assert report["after"] == report["after_restart"]
    assert report["new_id_same_source_blocked_after_restart"]
    assert report["peer_import_blocked_after_commit"]
    assert report["protected_source_import_allowed"]
    assert report["foreign_same_source_import_allowed"]
    assert report["relabeled_source_bypass_restores_fact"]
    assert report["direct_storage_bypass_restores_fact"]
    assert not report["complete_forgetting_demonstrated"]
