from copy import deepcopy
import json
import pytest

from experiments.staged_selection_probe import run


PACK = {'dataset_id': 'resolution-selection-probe', 'cases': [{
    'case_id': 'q', 'question': '2026-09-12应使用哪个配置？', 'as_of': '2026-10-01',
    'candidates': [{'id': 'c1', 'text': '旧配置适用至2026-09-17。'},
                   {'id': 'c2', 'text': '新配置从2026-09-18起适用。'}]}]}
DECISION = {'dataset_id': 'resolution-selection-probe', 'case_id': 'q',
            'target_date': '2026-09-12', 'scope_status': 'specified',
            'assessments': [{'id': 'c1', 'status': 'uncertain'},
                            {'id': 'c2', 'status': 'inapplicable'}]}


def test_uncertain_and_other_original_evidence_survive_into_selection():
    original = deepcopy(PACK)

    def selector(pack):
        assert pack['cases'][0]['candidates'] == PACK['cases'][0]['candidates']
        assert pack['cases'][0]['applicability']['target_date'] == '2026-09-12'
        return {'dataset_id': 'resolution-selection-probe', 'results': [
            {'case_id': 'q', 'selected_ids': ['c1']}]}

    result = run(PACK, assessor=lambda pack: deepcopy(DECISION), selector=selector)
    assert result['applicability_status'] == 'accepted'
    assert result['selection']['memories'] == [{'id': 'c1', 'text': '旧配置适用至2026-09-17。'}]
    assert PACK == original


def test_invalid_applicability_is_rejected_before_using_it_as_evidence():
    invalid = deepcopy(DECISION)
    invalid['target_date'] = '2026-02-30'

    def selector(pack):
        raise AssertionError('Invalid assessment must not reach selection')

    result = run(PACK, assessor=lambda pack: invalid, selector=selector)
    assert result['applicability_status'] == 'fallback'
    assert result['applicability'] is None
    assert result['selection']['fallback_reason'] == 'applicability_invalid'
    assert [item['id'] for item in result['selection']['memories']] == ['c1', 'c2']


@pytest.mark.parametrize('change', [
    {'dataset_id': 'other'}, {'case_id': 'other'}, {'scope_status': 'unknown'},
    {'target_date': 20260912}, {'target_date': '20260912'},
    {'assessments': []}, {'assessments': [{'id': 'c9', 'status': 'applicable'}]},
    {'assessments': [{'id': 'c1', 'status': 'applicable'}, {'id': 'c1', 'status': 'uncertain'}]},
    {'assessments': [{'id': 'c1', 'status': 'guess'}, {'id': 'c2', 'status': 'applicable'}]},
])
def test_invalid_assessment_fields_trigger_original_candidate_fallback(change):
    decision = dict(deepcopy(DECISION), **change)
    result = run(PACK, assessor=lambda pack: json.dumps(decision), selector=lambda pack: None)
    assert result['applicability_status'] == 'fallback'
    assert result['selection']['fallback_reason'] == 'applicability_invalid'
    assert [item['id'] for item in result['selection']['memories']] == ['c1', 'c2']


@pytest.mark.parametrize('response', ['{', [], RuntimeError('offline')])
def test_malformed_assessment_outputs_are_not_repaired(response):
    result = run(PACK, assessor=lambda pack: response, selector=lambda pack: None)
    assert result['applicability_status'] == 'fallback'


def test_assessor_exception_falls_back_without_mutating_original_input():
    original = deepcopy(PACK)

    def assessor(pack):
        pack['cases'][0]['candidates'].clear()
        raise RuntimeError('offline')

    result = run(PACK, assessor=assessor, selector=lambda pack: None)
    assert result['applicability_status'] == 'fallback' and PACK == original


def test_ambiguous_scope_and_unknown_date_remain_explicit():
    decision = dict(deepcopy(DECISION), target_date=None, scope_status='ambiguous')
    result = run(PACK, assessor=lambda pack: json.dumps(decision), selector=lambda pack: {
        'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': []}]})
    assert result['applicability']['target_date'] is None
    assert result['applicability']['scope_status'] == 'ambiguous'
    assert result['selection']['status'] == 'selected' and result['selection']['memories'] == []


@pytest.mark.parametrize('response,reason', [
    ('{', 'parse_error'),
    ({'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': ['c9']}]}, 'unknown_id'),
])
def test_invalid_second_stage_uses_existing_strict_fallback(response, reason):
    result = run(PACK, assessor=lambda pack: deepcopy(DECISION), selector=lambda pack: response)
    assert result['selection']['fallback_reason'] == reason
    assert [item['id'] for item in result['selection']['memories']] == ['c1', 'c2']


def test_second_stage_failure_still_preserves_original_evidence():
    def selector(pack):
        pack['cases'][0]['candidates'].clear()
        raise RuntimeError('offline')

    result = run(PACK, assessor=lambda pack: deepcopy(DECISION), selector=selector)
    assert result['selection']['fallback_reason'] == 'call_failure'
    assert [item['id'] for item in result['selection']['memories']] == ['c1', 'c2']
