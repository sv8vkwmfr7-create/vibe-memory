import pytest

from experiments.selection_response_probe import process_selection


PACK = {"dataset_id": "test", "cases": [{"case_id": "c1", "candidates": [
    {"id": "a", "text": "original a"},
    {"id": "b", "text": "original b"},
    {"id": "c", "text": "original c"},
]}]}


def test_valid_selection_uses_only_original_candidate_text():
    response = {"dataset_id": "test", "results": [
        {"case_id": "c1", "selected_ids": ["c"], "text": "fabricated"}
    ]}
    assert process_selection(PACK, response)["results"] == [{
        "case_id": "c1", "status": "selected", "fallback_reason": None,
        "memories": [{"id": "c", "text": "original c"}],
    }]


@pytest.mark.parametrize("ids,reason", [
    (["unknown"], "unknown_id"), (["a", "a"], "duplicate_id"),
    (["a", "b", "c"], "over_budget"), ("a", "invalid_ids"),
])
def test_invalid_selection_falls_back_to_original_first_two(ids, reason):
    response = {"dataset_id": "test", "results": [
        {"case_id": "c1", "selected_ids": ids}
    ]}
    row = process_selection(PACK, response)["results"][0]
    assert row["status"] == "fallback"
    assert row["fallback_reason"] == reason
    assert row["memories"] == PACK["cases"][0]["candidates"][:2]


@pytest.mark.parametrize("response,reason", [
    ("not json", "parse_error"), (RuntimeError("private detail"), "call_failure"),
    ({"dataset_id": "wrong", "results": []}, "dataset_mismatch"),
    ({"dataset_id": "test", "results": []}, "missing_case"),
    ({"dataset_id": "test", "results": [{"case_id": "other"}]}, "invalid_batch"),
    ({"dataset_id": "test", "results": [{"case_id": "c1"}]}, "invalid_ids"),
    ({"dataset_id": "test", "results": [{"case_id": "c1"}, {"case_id": "c1"}]}, "invalid_batch"),
    ([], "invalid_batch"),
])
def test_response_failure_is_observable_without_exception_details(response, reason):
    row = process_selection(PACK, response)["results"][0]
    assert row["fallback_reason"] == reason
    assert row["status"] == "fallback"
    assert row["memories"] == PACK["cases"][0]["candidates"][:2]


def test_json_empty_selection_is_valid():
    row = process_selection(PACK, '{"dataset_id":"test","results":[{"case_id":"c1","selected_ids":[]}]}')["results"][0]
    assert row["status"] == "selected"
    assert row["memories"] == []


def test_missing_case_does_not_discard_valid_case_or_mutate_inputs():
    import copy

    pack = copy.deepcopy(PACK)
    pack["cases"].append({"case_id": "c2", "candidates": [{"id": "z", "text": "z"}]})
    before = copy.deepcopy(pack)
    response = {"dataset_id": "test", "results": [{"case_id": "c1", "selected_ids": ["c"]}]}
    rows = process_selection(pack, response)["results"]
    assert rows[0]["status"] == "selected"
    assert rows[1]["fallback_reason"] == "missing_case"
    assert rows[1]["memories"] == [{"id": "z", "text": "z"}]
    rows[1]["memories"][0]["text"] = "changed"
    assert pack == before
