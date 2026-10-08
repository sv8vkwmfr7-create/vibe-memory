import json
import pytest

from experiments.resolution_selection_probe import run
from vibe_memory import VibeMemory


def test_short_candidate_selection_returns_original_uuid_without_mutating_evidence(tmp_path):
    memory = VibeMemory(agent_id='probe', db_path=str(tmp_path / 'short.db'), embedding_backend='tfidf')
    try:
        memory.store('订单生产超时为60秒。', session_id='fixture', auto_build_edges=False, auto_episode=False)

        def selector(pack):
            assert pack['cases'][0]['candidates'][0]['id'] == 'c1'
            return json.dumps({'dataset_id': 'resolution-selection-probe', 'results': [
                {'case_id': 'q', 'selected_ids': ['c1']}]})

        result = run(memory, '订单生产超时？', selector=selector, short_candidate_ids=True)
        original_id = result['candidates'][0]['id']
        assert original_id != 'c1'
        assert result['selection'] == {'case_id': 'q', 'status': 'selected', 'fallback_reason': None,
                                       'memories': [{'id': original_id, 'text': '订单生产超时为60秒。'}]}
        assert result['selected_evidence'][0]['id'] == original_id
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('response,reason', [
    ('{', 'parse_error'),
    ({'dataset_id': 'wrong', 'results': [{'case_id': 'q', 'selected_ids': ['c1']}]}, 'dataset_mismatch'),
    ({'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': ['c9']}]}, 'unknown_id'),
    ({'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': [1]}]}, 'invalid_ids'),
    ({'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': ['c1', 'c1']}]}, 'duplicate_id'),
    ({'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': ['c1', 'c2', 'c3']}]}, 'over_budget'),
    (RuntimeError(), 'call_failure'),
])
def test_invalid_short_selection_falls_back_without_guessing_ids(tmp_path, response, reason):
    memory = VibeMemory(agent_id='probe', db_path=str(tmp_path / 'invalid.db'), embedding_backend='tfidf')
    try:
        atoms = [memory.store(text, session_id='fixture', auto_build_edges=False, auto_episode=False)
                 for text in ['订单生产超时30秒。', '订单生产超时60秒。']]
        result = run(memory, '订单生产超时？', selector=lambda pack: response, short_candidate_ids=True)
        assert result['selection']['status'] == 'fallback'
        assert result['selection']['fallback_reason'] == reason
        assert {item['id'] for item in result['selection']['memories']} == {atom.id for atom in atoms}
    finally:
        memory.storage.conn.close()


def test_short_selection_can_abstain_without_inserting_fallback_evidence(tmp_path):
    memory = VibeMemory(agent_id='probe', db_path=str(tmp_path / 'empty.db'), embedding_backend='tfidf')
    try:
        memory.store('订单生产超时60秒。', session_id='fixture', auto_build_edges=False, auto_episode=False)
        result = run(memory, '订单生产超时？', short_candidate_ids=True, selector=lambda pack: {
            'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': []}]})
        assert result['selection']['status'] == 'selected'
        assert result['selection']['memories'] == [] and result['selected_evidence'] == []
    finally:
        memory.storage.conn.close()


def test_default_selector_still_receives_and_returns_original_uuid(tmp_path):
    memory = VibeMemory(agent_id='probe', db_path=str(tmp_path / 'default.db'), embedding_backend='tfidf')
    try:
        atom = memory.store('订单生产超时60秒。', session_id='fixture', auto_build_edges=False, auto_episode=False)

        def selector(pack):
            assert pack['cases'][0]['candidates'][0]['id'] == atom.id
            return {'dataset_id': 'resolution-selection-probe', 'results': [{'case_id': 'q', 'selected_ids': [atom.id]}]}

        result = run(memory, '订单生产超时？', selector=selector)
        assert result['selection']['memories'][0]['id'] == atom.id
    finally:
        memory.storage.conn.close()
