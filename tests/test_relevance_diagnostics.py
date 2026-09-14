"""Frozen synthetic diagnostics: characterize gaps, not semantic success."""
import json
from pathlib import Path

import pytest

from experiments.precision_guard_probe import evaluate
from experiments.relevance_diagnostic_probe import run


CASES_PATH = Path(__file__).resolve().parents[1] / 'experiments' / 'relevance_diagnostic_cases.json'
CASES = json.loads(CASES_PATH.read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case', CASES[:4], ids=[c['case_id'] for c in CASES[:4]])
def test_preserving_direct_matches_does_not_delete_existing_answer(case):
    result = evaluate(case)['aggregates']
    assert result['baseline']['macro_recall'] == 1
    assert result['guarded_causal_2hop']['macro_recall'] == 0
    assert result['evidence_preserving_causal_2hop']['macro_recall'] == 1


def test_synonym_candidate_omission_still_requires_real_semantics():
    result = evaluate(CASES[4])['aggregates']
    assert result['baseline']['macro_recall'] == 0
    assert result['evidence_preserving_causal_2hop']['macro_recall'] == 0


def test_positive_control_keeps_causal_answers():
    assert evaluate(CASES[5])['aggregates']['evidence_preserving_causal_2hop']['macro_recall'] == 1


def test_public_diagnostic_report_is_repeatable():
    assert run(CASES_PATH) == run(CASES_PATH)


def test_zero_overlap_answer_is_still_unsafe_even_when_already_a_candidate():
    case = {'atoms': [
        {'id': 'n0', 'session_id': 'other', 'content': 'request hangs request hangs unrelated application'},
        {'id': 'n1', 'session_id': 'other', 'content': 'request hangs request hangs restart unrelated application'},
        {'id': 'a0', 'session_id': 'target', 'content': 'Connections saturated; enlarge pool capacity'},
    ], 'edges': [('n0', 'n1')], 'queries': [
        {'text': 'request hangs', 'relevant_ids': ['a0'], 'negative_ids': ['n0', 'n1']},
    ]}
    result = evaluate(case)['aggregates']
    assert result['baseline']['macro_recall'] == 1
    assert result['evidence_preserving_causal_2hop']['macro_recall'] == 0
