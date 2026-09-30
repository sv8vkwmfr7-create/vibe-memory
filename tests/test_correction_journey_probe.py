"""The public MCP correction probe reports both the new and stale memory."""

from hashlib import sha256

from experiments.correction_journey_probe import DEFAULT_CORRECTION, run


REVIEW = {
    "fact_key": "orders.production.timeout",
    "scope": {"service": "orders", "environment": "production", "operation": "timeout"},
    "effective_date": "2026-09-22",
    "reviewer_id": "synthetic-reviewer",
    "verdict": "verified_current",
}


def review_with_source(tmp_path, content=DEFAULT_CORRECTION):
    source = tmp_path / "synthetic-source.txt"
    source.write_text(content, encoding="utf-8")
    return {**REVIEW, "source_ref": str(source),
            "source_sha256": sha256(source.read_bytes()).hexdigest()}


def test_correction_journey_exposes_stale_memory_risk():
    report = run()

    assert report["scenario"] == "synthetic_cross_session_correction"
    assert report["stored_sessions"] == 2
    assert report["target_in_top5"] == (report["target_rank"] is not None)
    assert report["stale_in_top5"] == (report["stale_rank"] is not None)
    assert report["answer_quality"] == "not_measured_no_answer_model"


def test_explicit_revision_without_review_cannot_prioritize_the_corrected_memory():
    report = run(revision_link=True)

    assert report["revision_link_created"]
    assert report["target_rank"] == 2
    assert report["stale_rank"] == 1
    assert report["experimental_target_rank"] == 2
    assert report["experimental_stale_rank"] == 1


def test_different_environment_without_revision_does_not_promote_new_memory():
    report = run(new_content="订单服务测试环境超时配置为60秒，正式环境仍为30秒。")

    assert not report["revision_link_created"]
    assert report["stale_rank"] == 1
    assert report["experimental_stale_rank"] == report["stale_rank"]
    assert report["experimental_target_rank"] == report["target_rank"]


def test_scope_gate_blocks_false_cross_environment_revision():
    report = run(
        revision_link=True,
        new_content="订单服务测试环境超时配置为60秒，正式环境仍为30秒。",
        new_scope={"service": "orders", "environment": "test", "operation": "timeout"},
    )

    assert report["unguarded_target_rank"] == 1
    assert not report["scope_gate_passed"]
    assert not report["known_false_link_promotes_wrong_environment"]
    assert report["experimental_stale_rank"] == 1


def test_same_scope_false_revision_without_review_does_not_promote_future_draft():
    report = run(
        revision_link=True,
        new_content="订单服务正式环境下一版草案拟将超时改为60秒，目前生效配置仍为30秒。",
    )

    assert report["scenario"] == "synthetic_same_scope_future_draft"
    assert report["scope_gate_passed"]
    assert not report["known_false_link_promotes_noncurrent"]
    assert report["experimental_target_rank"] == 2


def test_complete_synthetic_review_allows_report_only_promotion(tmp_path):
    report = run(revision_link=True, review=review_with_source(tmp_path))

    assert report["review_gate_passed"]
    assert report["experimental_target_rank"] == 1


def test_future_effective_date_blocks_promotion(tmp_path):
    report = run(revision_link=True, review={**review_with_source(tmp_path), "effective_date": "2026-09-24"})

    assert not report["review_gate_passed"]
    assert report["experimental_target_rank"] == 2


def test_unreadable_source_reference_blocks_promotion():
    report = run(revision_link=True, review={**REVIEW, "source_ref": "synthetic://missing", "source_sha256": "0" * 64})

    assert not report["review_gate_passed"]
    assert report["experimental_target_rank"] == 2


def test_changed_source_blocks_promotion(tmp_path):
    review = review_with_source(tmp_path)
    (tmp_path / "synthetic-source.txt").write_text("material changed", encoding="utf-8")
    report = run(revision_link=True, review=review)

    assert not report["review_gate_passed"]
    assert report["experimental_target_rank"] == 2


def test_source_without_claim_blocks_promotion(tmp_path):
    report = run(revision_link=True, review=review_with_source(tmp_path, "unrelated material"))

    assert not report["review_gate_passed"]
    assert report["experimental_target_rank"] == 2


def test_forged_complete_review_is_not_truth_verification(tmp_path):
    draft = "订单服务正式环境下一版草案拟将超时改为60秒，目前生效配置仍为30秒。"
    report = run(
        revision_link=True,
        new_content=draft,
        review=review_with_source(tmp_path, draft),
    )

    assert report["review_gate_passed"]
    assert report["known_false_link_promotes_noncurrent"]


def test_missing_review_fields_block_promotion(tmp_path):
    complete = review_with_source(tmp_path)
    for field in complete:
        report = run(revision_link=True, review={key: value for key, value in complete.items() if key != field})
        assert not report["review_gate_passed"], field
        assert report["experimental_target_rank"] == 2, field
