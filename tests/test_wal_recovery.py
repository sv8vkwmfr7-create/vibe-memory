from experiments.wal_recovery_validation import validate_transactions, validate_crash


def test_wal_transaction_visibility_and_checkpoint_release(tmp_path):
    report = validate_transactions(str(tmp_path / "transaction.db"))
    assert report["uncommitted_hidden"]
    assert report["competing_writer_blocked"]
    assert report["snapshot_retained"]
    assert report["committed_visible_after_snapshot"]
    assert report["checkpoint_pinned"][0] == 1
    assert report["checkpoint_released"] == [0, 0, 0]


def test_killed_writer_keeps_committed_memory_and_discards_pending_update(tmp_path):
    report = validate_crash(str(tmp_path / "crash.db"))
    assert report["child_killed"]
    assert report["wal_bytes_before_reopen"] > 0
    assert report["committed_preserved"]
    assert report["uncommitted_discarded"]
    assert report["committed_recalled"]
    assert report["integrity_check"] == "ok"
    assert report["fts_external_content_integrity"] == "ok"
