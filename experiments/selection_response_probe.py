"""Offline selection boundary; structural acceptance is not quality success."""

import json


def process_selection(pack, response):
    batch_reason = None
    rows = {}
    if isinstance(response, Exception):
        batch_reason = "call_failure"
    elif isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError:
            batch_reason = "parse_error"
    if not batch_reason:
        if not isinstance(response, dict) or not isinstance(response.get("results"), list):
            batch_reason = "invalid_batch"
        elif response.get("dataset_id") != pack["dataset_id"]:
            batch_reason = "dataset_mismatch"
        else:
            case_ids = {case["case_id"] for case in pack["cases"]}
            for row in response["results"]:
                if (not isinstance(row, dict) or not isinstance(row.get("case_id"), str)
                        or row["case_id"] not in case_ids or row["case_id"] in rows):
                    batch_reason = "invalid_batch"
                    break
                rows[row["case_id"]] = row
    results = []
    for case in pack["cases"]:
        candidates = {item["id"]: item for item in case["candidates"]}
        row = rows.get(case["case_id"])
        selected = row.get("selected_ids") if row else None
        reason = batch_reason or ("missing_case" if row is None else None)
        if reason:
            pass
        elif not isinstance(selected, list) or any(not isinstance(key, str) for key in selected):
            reason = "invalid_ids"
        elif len(selected) > 2:
            reason = "over_budget"
        elif len(set(selected)) != len(selected):
            reason = "duplicate_id"
        elif any(key not in candidates for key in selected):
            reason = "unknown_id"
        if reason:
            selected = list(candidates)[:2]
        results.append({
            "case_id": case["case_id"], "status": "fallback" if reason else "selected",
            "fallback_reason": reason,
            "memories": [{"id": key, "text": candidates[key]["text"]}
                         for key in selected],
        })
    return {"dataset_id": pack["dataset_id"], "results": results}
