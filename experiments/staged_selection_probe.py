"""Experimental applicability annotations, never a production filter."""
from copy import deepcopy
from datetime import date
import json

from experiments.selection_response_probe import process_selection


def run(pack, *, assessor, selector):
    if len(pack['cases']) != 1:
        raise ValueError('This experiment accepts one question at a time')
    try:
        decision = assessor(deepcopy(pack))
        if isinstance(decision, str):
            decision = json.loads(decision)
        case = pack['cases'][0]
        if (not isinstance(decision, dict) or decision.get('dataset_id') != pack['dataset_id']
                or decision.get('case_id') != case['case_id']
                or decision.get('scope_status') not in ('specified', 'ambiguous')
                or 'target_date' not in decision):
            raise ValueError('Invalid applicability response')
        target = decision['target_date']
        if target is not None and (not isinstance(target, str) or date.fromisoformat(target).isoformat() != target):
            raise ValueError('Invalid target date')
        assessments = decision.get('assessments')
        expected_ids = {item['id'] for item in case['candidates']}
        if (not isinstance(assessments, list) or len(assessments) != len(expected_ids)
                or any(not isinstance(item, dict) or not isinstance(item.get('id'), str)
                       or item['id'] not in expected_ids
                       or item.get('status') not in ('applicable', 'inapplicable', 'uncertain')
                       for item in assessments)
                or len({item['id'] for item in assessments}) != len(expected_ids)):
            raise ValueError('Invalid candidate assessments')
    except Exception:
        selection = process_selection(pack, RuntimeError())['results'][0]
        selection['fallback_reason'] = 'applicability_invalid'
        return {'applicability_status': 'fallback', 'applicability': None, 'selection': selection}
    second_pack = deepcopy(pack)
    second_pack['cases'][0]['applicability'] = deepcopy(decision)
    try:
        response = selector(second_pack)
    except Exception:
        response = RuntimeError()
    return {'applicability_status': 'accepted', 'applicability': decision,
            'selection': process_selection(pack, response)['results'][0]}
