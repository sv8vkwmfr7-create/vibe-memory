"""Observed SDK path gaps, using synthetic temporary databases only."""

from experiments.forget_sdk_path_probe import run


def test_sdk_path_trace_distinguishes_storage_recall_and_prompt_residuals():
    report = run()
    seed = report["seed"]
    assert seed["persisted_clone_recalled_before_forget"]
    assert seed["forget_returned_true"] and seed["rows_after_forget"] == 0
    assert seed["persisted_clone_not_returned_after_forget"]
    assert not seed["unpersisted_template_returned_after_forget"]
    assert not seed["mac_prompt_contains_fact_after_forget"]
    assert seed["same_client_rebootstrap_count"] == 0
    assert seed["reopen_without_seed_config_returns_fact"] is False
    assert seed["configured_rebootstrap_count"] == 0
    assert not seed["configured_rebootstrap_restores_fact_with_new_id"]
    batch = report["batch_episode"]
    assert batch["stored_assistant_atoms"] == 3 and batch["episodes_before_forget"] == 1
    assert batch["all_atom_sources_are_session_id"]
    assert batch["forget_returned_true"] and batch["target_row_absent"]
    assert batch["surviving_context_contains_fact"]
    assert not batch["returned_atom_context_contains_fact"]
    assert not batch["returned_content_or_summary_contains_fact"]
    assert not batch["mac_prompt_contains_fact_after_forget"]
    assert batch["episodes_after_forget"] == 0
    assert not batch["episode_summary_contains_fact"]
    assert not batch["episode_references_deleted_atom"]
    assert batch["reimport_uses_fresh_ids"] and batch["reimport_restores_recall"]
    merge = report["merge"]
    assert merge["active_atom_count_after_two_stores"] == 1
    assert merge["both_parent_rows_absent"]
    assert not merge["returned_second_atom_not_persisted"]
    assert merge["returned_second_atom_is_live_merged"]
    assert merge["source_names_immediate_parent_ids"] and merge["previous_version_points_to_deleted_parent"]
    assert not merge["forget_original_id_returned_true"]
    assert merge["merged_fact_still_recalled"]
    assert merge["forget_live_merged_id_returned_true"] and not merge["fact_recalled_after_live_delete"]
    assert not report["production_changed"]
