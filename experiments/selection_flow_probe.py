"""Opt-in experiment flow, not a production SDK or model adapter."""
from experiments.selection_response_probe import process_selection
from copy import deepcopy


def run(memory, question, *, selector=None, candidate_top_k=5):
    recalled = memory.recall(question, mode="precision", top_k=candidate_top_k)
    candidates = [{"id": atom.id, "text": atom.content} for atom in recalled["atoms"]]
    pack = {"dataset_id": "selection-flow-probe", "cases": [
        {"case_id": "q", "question": question, "candidates": candidates}
    ]}
    if selector is None:
        selection = {"case_id": "q", "status": "fallback", "fallback_reason": "selector_disabled",
                     "memories": [dict(item) for item in candidates[:2]]}
        return {"candidates": candidates, "selection": selection,
                "recall_failures": recalled.get("failures", [])}
    try:
        response = selector(deepcopy(pack))
    except Exception:
        response = RuntimeError()
    selection = process_selection(pack, response)["results"][0]
    return {"candidates": candidates, "selection": selection,
            "recall_failures": recalled.get("failures", [])}
