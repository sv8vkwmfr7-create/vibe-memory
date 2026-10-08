from experiments.resolution_selection_probe import run
from vibe_memory import VibeMemory
import pytest


@pytest.mark.parametrize('stage', ['export', 'final', 'answer'])
def test_invalid_original_date_is_rejected_at_each_pack_boundary(stage):
    from experiments.resolution_selection_probe import export_cases, freeze_final_pack, freeze_answer_pack

    case = {'case_id': 'q', 'question': '超时？', 'scope': {}, 'as_of': '2026-02-30',
            'atoms': [{'id': 'a', 'text': '超时60秒。'}],
            'anchor_evidence': [{'id': 'a', 'text': '超时60秒。'}],
            'candidates': [{'id': 'a', 'text': '超时60秒。'}]}
    with pytest.raises(ValueError, match='as_of'):
        if stage == 'export':
            export_cases([case])
        else:
            pack = {'dataset_id': 'resolution-reference-review-v4' if stage == 'final'
                    else 'resolution-final-selection-v5', 'cases': [case]}
            response = {'dataset_id': pack['dataset_id'], 'results': [
                {'case_id': 'q', 'selected_ids': ['a']}]}
            (freeze_final_pack if stage == 'final' else freeze_answer_pack)(pack, response)


def test_legacy_undated_packs_remain_undated_across_pipeline():
    from experiments.resolution_selection_probe import export_cases, freeze_final_pack, freeze_answer_pack

    exported = export_cases([{'case_id': 'q', 'question': '超时？',
                             'atoms': [{'id': 'a', 'text': '超时60秒。'}]}],
                            include_references=True, review_references=True)
    review = exported['pack']
    final = freeze_final_pack(review, {'dataset_id': review['dataset_id'], 'results': [
        {'case_id': 'q', 'selected_ids': []}]})['pack']
    answer = freeze_answer_pack(final, {'dataset_id': final['dataset_id'], 'results': [
        {'case_id': 'q', 'selected_ids': []}]})
    assert all('as_of' not in pack['cases'][0] for pack in (review, final, answer))


def test_cli_preserves_source_date_through_export_final_and_answer_packs(tmp_path):
    import hashlib
    import json
    import subprocess
    import sys

    source = tmp_path / 'cases.json'
    source.write_text(json.dumps({'as_of': '2026-10-01', 'cases': [{
        'case_id': 'q', 'question': '现在订单超时多少？',
        'atoms': [{'id': 'a', 'text': '订单超时60秒。'}],
        'relevant_ids': ['a'], 'negative_ids': [],
    }]}), encoding='utf-8')
    review, baseline, response, final, final_baseline, answer = [
        tmp_path / name for name in ('review.json', 'baseline.json', 'response.json',
                                    'final.json', 'final-baseline.json', 'answer.json')]
    command = [sys.executable, '-m', 'experiments.resolution_selection_probe']
    subprocess.run(command + ['export', '--cases', str(source), '--pack', str(review),
                             '--baseline', str(baseline), '--include-references',
                             '--review-references'], capture_output=True, check=True, timeout=30)
    pack = json.loads(review.read_text(encoding='utf-8'))
    assert pack['cases'][0]['as_of'] == '2026-10-01'
    response.write_text(json.dumps({'dataset_id': pack['dataset_id'],
        'pack_sha256': hashlib.sha256(review.read_bytes()).hexdigest(),
        'results': [{'case_id': 'q', 'selected_ids': []}]}), encoding='utf-8')
    subprocess.run(command + ['finalize', '--cases', str(source), '--pack', str(final),
        '--baseline', str(final_baseline), '--response', str(response),
        '--review-pack', str(review), '--review-baseline', str(baseline)],
        capture_output=True, check=True, timeout=30)
    pack = json.loads(final.read_text(encoding='utf-8'))
    assert pack['cases'][0]['as_of'] == '2026-10-01'
    response.write_text(json.dumps({'dataset_id': pack['dataset_id'],
        'pack_sha256': hashlib.sha256(final.read_bytes()).hexdigest(),
        'results': [{'case_id': 'q', 'selected_ids': [pack['cases'][0]['candidates'][0]['id']]}]}),
        encoding='utf-8')
    subprocess.run(command + ['answers', '--cases', str(source), '--pack', str(final),
        '--baseline', str(final_baseline), '--response', str(response), '--report', str(answer)],
        capture_output=True, check=True, timeout=30)
    assert json.loads(answer.read_text(encoding='utf-8'))['cases'][0]['as_of'] == '2026-10-01'


def test_answer_input_preserves_original_evaluation_date_and_explicit_historical_question():
    from experiments.resolution_selection_probe import freeze_answer_pack

    pack = {'dataset_id': 'resolution-final-selection-v5', 'cases': [{
        'case_id': 'q', 'question': '2026-09-15订单超时是多少？', 'scope': {},
        'as_of': '2026-10-01', 'candidates': [{'id': 'a', 'text': '9月15日超时30秒。'}]}]}
    response = {'dataset_id': pack['dataset_id'], 'results': [
        {'case_id': 'q', 'selected_ids': ['a'], 'as_of': '2099-01-01'}]}
    answer = freeze_answer_pack(pack, response)['cases'][0]
    assert answer['as_of'] == '2026-10-01'
    assert answer['question'] == '2026-09-15订单超时是多少？'
    assert answer['evidence'] == [{'id': 'a', 'text': '9月15日超时30秒。'}]


def test_final_selection_preserves_evaluation_date_from_original_pack():
    from experiments.resolution_selection_probe import freeze_final_pack

    pack = {'dataset_id': 'resolution-reference-review-v4', 'cases': [{
        'case_id': 'q', 'question': '现在超时多少？', 'scope': {}, 'as_of': '2026-10-01',
        'anchor_evidence': [{'id': 'a', 'text': '超时60秒。'}], 'candidates': []}]}
    response = {'dataset_id': pack['dataset_id'], 'results': [
        {'case_id': 'q', 'selected_ids': [], 'as_of': '2099-01-01'}]}
    final = freeze_final_pack(pack, response)['pack']['cases'][0]
    assert final['as_of'] == '2026-10-01'
    assert final['candidates'] == [{'id': 'a', 'text': '超时60秒。'}]


def test_export_preserves_per_case_date_and_batch_default_without_changing_evidence():
    from experiments.resolution_selection_probe import export_cases

    cases = [
        {'case_id': 'historical', 'as_of': '2026-09-15', 'question': '订单超时？',
         'atoms': [{'id': 'a', 'text': '订单超时为30秒。'}]},
        {'case_id': 'current', 'question': '订单超时？',
         'atoms': [{'id': 'a', 'text': '订单超时为60秒。'}]},
    ]
    exported = export_cases(cases, as_of='2026-10-01')
    assert [case['as_of'] for case in exported['pack']['cases']] == ['2026-09-15', '2026-10-01']
    assert [case['candidates'][0]['text'] for case in exported['pack']['cases']] == [
        '订单超时为30秒。', '订单超时为60秒。']


@pytest.mark.parametrize('as_of', ['2026-09-15', '2026-10-01', '2026-10-11'])
def test_explicit_evaluation_date_reaches_selector_without_removing_temporal_evidence(tmp_path, as_of):
    memory = VibeMemory(agent_id='date-control', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'date.db'))
    seen = []
    try:
        texts = [
            '2026-09-01至09-19，订单生产超时为30秒。',
            '2026-09-20起，订单生产超时为60秒。',
            '计划2026-10-10起，订单生产超时改为90秒，尚未生效。',
        ]
        for text in texts:
            memory.store(text, session_id='fixture', auto_build_edges=False, auto_episode=False)

        def selector(pack):
            seen.append(pack)
            return {'dataset_id': pack['dataset_id'],
                    'results': [{'case_id': 'q', 'selected_ids': []}]}

        result = run(memory, '现在订单生产超时是多少？', selector=selector, as_of=as_of)

        assert seen[0]['cases'][0]['as_of'] == as_of
        assert {item['text'] for item in seen[0]['cases'][0]['candidates']} == set(texts)
        assert result['selection']['status'] == 'selected'
        assert result['recall_failures'] == []
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('as_of', ['2026-02-30', '2026-10-01T12:00:00', '20261001', '', 20261001])
def test_invalid_evaluation_date_is_rejected_without_sending_selector_input(tmp_path, as_of):
    memory = VibeMemory(agent_id='invalid-date', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'date.db'))
    seen = []
    try:
        with pytest.raises(ValueError, match='as_of'):
            run(memory, '现在的配置？', selector=seen.append, as_of=as_of)
        assert seen == []
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('action', ['export', 'finalize', 'answers'])
def test_cli_budget_rejects_oversized_batch_without_overwriting_evidence(tmp_path, action):
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    pack, baseline, report = [tmp_path / name for name in ('pack.json', 'baseline.json', 'report.json')]
    for path in (pack, baseline, report):
        path.write_text('preserved', encoding='utf-8')
    command = [sys.executable, '-m', 'experiments.resolution_selection_probe', action,
               '--cases', str(root / 'experiments/resolution_reference_competition_cases.json'),
               '--pack', str(pack), '--baseline', str(baseline), '--report', str(report),
               '--max-pack-chars', '1']
    if action == 'export':
        command += ['--include-references', '--review-references']
    elif action == 'finalize':
        command += ['--review-pack', str(root / 'results/resolution_reference_content_pack.json'),
                    '--review-baseline', str(root / 'results/resolution_reference_content_baseline.json'),
                    '--response', str(root / 'results/resolution_reference_content_response.json')]
    else:
        command[command.index('--pack') + 1] = str(root / 'results/resolution_final_selection_pack.json')
        command[command.index('--baseline') + 1] = str(root / 'results/resolution_final_selection_baseline.json')
        command += ['--response', str(root / 'results/resolution_final_selection_response.json')]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'input_over_budget' in result.stderr
    assert all(path.read_text(encoding='utf-8') == 'preserved' for path in (pack, baseline, report))
    budget_index = command.index('--max-pack-chars')
    unlimited = command[:budget_index] + command[budget_index + 2:]
    subprocess.run(unlimited, cwd=root, capture_output=True, check=True)
    output = report if action == 'answers' else pack
    original = output.read_bytes()
    size = len(original.decode('utf-8'))
    command[budget_index + 1] = str(size)
    subprocess.run(command, cwd=root, capture_output=True, check=True)
    assert output.read_bytes() == original
    before = [path.read_bytes() for path in (pack, baseline, report)]
    command[budget_index + 1] = str(size - 1)
    rejected = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert 'input_over_budget' in rejected.stderr
    assert [path.read_bytes() for path in (pack, baseline, report)] == before


@pytest.mark.parametrize('budget', ['0', '-1', '1.5', 'true', 'abc'])
def test_cli_invalid_budget_is_rejected_before_reading_or_writing(tmp_path, budget):
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    pack = tmp_path / 'pack.json'
    pack.write_text('preserved', encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe',
        'export', '--cases', str(tmp_path / 'missing.json'), '--pack', str(pack),
        '--baseline', str(tmp_path / 'baseline.json'), '--max-pack-chars', budget],
        cwd=root, capture_output=True, text=True)
    assert result.returncode == 2
    assert '--max-pack-chars' in result.stderr
    assert 'FileNotFoundError' not in result.stderr
    assert pack.read_text(encoding='utf-8') == 'preserved'
    assert not (tmp_path / 'baseline.json').exists()


def test_long_context_budget_skips_selector_without_truncating_negation(tmp_path):
    memory = VibeMemory(agent_id='budget', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'budget.db'))
    try:
        context = '待核实。' * 1000 + '最终结论：不是连接池故障，根因未确认。'
        atom = memory.store('连接池排查记录', session_id='fixture', context_after=context,
                            auto_build_edges=False, auto_episode=False)
        def selector(pack):
            pytest.fail('Over-budget evidence must not be sent to the selector')
        result = run(memory, '连接池根因', selector=selector, max_selector_chars=2000)
        assert result['selection']['fallback_reason'] == 'input_over_budget'
        assert result['selected_evidence'] == []
        assert result['candidates'][0]['id'] == atom.id
        assert result['candidates'][0]['context_after'] == context
        assert result['retrieval_diagnostics']['selector_input_over_budget'] is True
    finally:
        memory.storage.conn.close()


def test_selector_budget_accepts_exact_boundary_and_preserves_complete_context(tmp_path):
    memory = VibeMemory(agent_id='boundary', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'boundary.db'))
    try:
        atom = memory.store('连接池排查', session_id='fixture', context_after='根因未确认。',
                            auto_build_edges=False, auto_episode=False)
        def selector(pack):
            assert pack['cases'][0]['candidates'][0]['context_after'] == '根因未确认。'
            return {'dataset_id': pack['dataset_id'], 'results': [
                {'case_id': 'q', 'selected_ids': [atom.id]}]}
        unlimited = run(memory, '连接池', selector=selector)
        size = unlimited['retrieval_diagnostics']['selector_input_chars']
        bounded = run(memory, '连接池', selector=selector, max_selector_chars=size)
        assert bounded['selection']['status'] == 'selected'
        assert bounded['retrieval_diagnostics']['selector_input_over_budget'] is False
        assert bounded['selected_evidence'] == unlimited['selected_evidence']
    finally:
        memory.storage.conn.close()


def test_cli_chain_preserves_retrieval_snapshot_even_when_final_evidence_is_empty(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'cases.json'
    source.write_text(json.dumps({'cases': [
        {'case_id': 'window', 'question': '连接池', 'scope': {'service': 'orders'},
         'noise_count': 101, 'atoms': [
             {'id': 'wrong', 'text': '连接池', 'scope': {'service': 'billing'}}]},
        {'case_id': 'empty', 'question': '连接池', 'scope': {'service': 'orders'},
         'atoms': [{'id': 'wrong', 'text': '连接池', 'scope': {'service': 'billing'}}]}]}),
        encoding='utf-8')
    review, audit = tmp_path / 'review.json', tmp_path / 'audit.json'
    final, baseline = tmp_path / 'final.json', tmp_path / 'baseline.json'
    response, answer = tmp_path / 'response.json', tmp_path / 'answer.json'

    def cli(action, *args):
        subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe',
                        action, '--cases', str(source), *map(str, args)],
                       cwd=root, check=True, capture_output=True)

    cli('export', '--pack', review, '--baseline', audit,
        '--include-references', '--review-references')
    exported = json.loads(audit.read_bytes())
    diagnostic = exported['retrieval_diagnostics']
    assert diagnostic['window']['eligible_session_rows'] == 101
    assert diagnostic['window']['eligible_window_truncated'] is True
    assert diagnostic['window']['scope_excluded_session_rows'] == 1
    assert diagnostic['empty']['candidate_status'] == 'empty'

    for pack in (review, final):
        if pack == final:
            cli('finalize', '--pack', final, '--baseline', baseline,
                '--review-pack', review, '--review-baseline', audit, '--response', response)
            assert json.loads(baseline.read_bytes())['retrieval_diagnostics'] == diagnostic
        frozen = json.loads(pack.read_bytes())
        response.write_text(json.dumps({
            'dataset_id': frozen['dataset_id'],
            'pack_sha256': hashlib.sha256(pack.read_bytes()).hexdigest(),
            'results': [{'case_id': case['case_id'], 'selected_ids': []}
                        for case in frozen['cases']]}), encoding='utf-8')
    cli('answers', '--pack', final, '--baseline', baseline,
        '--response', response, '--report', answer)
    cases = json.loads(answer.read_bytes())['cases']
    assert [case['retrieval_diagnostics'] for case in cases] == [
        diagnostic['window'], diagnostic['empty']]
    assert all(case['evidence'] == [] for case in cases)
    assert cases[0]['retrieval_diagnostics']['candidate_status'] == 'nonempty'
    assert all(case['retrieval_diagnostics']['evidence_sufficiency'] == 'not_assessed'
               for case in cases)


def test_export_keeps_retrieval_diagnostics_outside_selector_input():
    from experiments.resolution_selection_probe import export_cases
    exported = export_cases([{'case_id': 'empty', 'question': '连接池',
                             'scope': {'service': 'orders'}, 'atoms': [
                                 {'id': 'wrong', 'text': '连接池恢复',
                                  'scope': {'service': 'billing'}}]}])
    assert exported['retrieval_diagnostics']['empty']['candidate_status'] == 'empty'
    assert 'retrieval_diagnostics' not in exported['pack']['cases'][0]


def test_empty_scoped_candidates_report_exclusions_without_claiming_sufficient_evidence(tmp_path):
    memory = VibeMemory(agent_id='diagnostic', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'empty.db'))
    try:
        memory.store('接口超时连接池恢复记录', session_id='fixture', scope={'service': 'billing'},
                     auto_build_edges=False, auto_episode=False)
        result = run(memory, '接口超时连接池', scope={'service': 'orders'})
        diagnostic = result['retrieval_diagnostics']
        assert diagnostic['session_rows_loaded'] == 1
        assert diagnostic['scope_excluded_session_rows'] == 1
        assert diagnostic['scope_excluded_baseline_rows'] == 1
        assert diagnostic['eligible_window_truncated'] is False
        assert diagnostic['candidate_status'] == 'empty'
        assert diagnostic['evidence_sufficiency'] == 'not_assessed'
        assert diagnostic['session_read_bounded'] is False
    finally:
        memory.storage.conn.close()


def test_matching_memory_older_than_100_other_scope_rows_can_fill_lexical_slot(tmp_path):
    memory = VibeMemory(agent_id='scope-window', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'window.db'))
    try:
        good = memory.store('连接池耗尽导致接口超时，释放连接后恢复正常', session_id='fixture',
                            scope={'service': 'orders'}, auto_build_edges=False, auto_episode=False)
        for index in range(100):
            memory.store(f'接口超时连接池维护记录编号{index}，连接资源配置记录',
                         session_id='fixture', scope={'service': 'billing'},
                         auto_build_edges=False, auto_episode=False)
        assert good.id not in [item.id for item in memory.history('fixture', limit=100)]
        result = run(memory, '接口超时的根因以及如何修复连接池', scope={'service': 'orders'})
        assert good.id not in [item['id'] for item in result['baseline']]
        assert [item['id'] for item in result['candidates']] == [good.id]
    finally:
        memory.storage.conn.close()


def test_100_matching_rows_still_bound_reference_preview_and_keep_owner_isolation(tmp_path):
    from vibe_memory.models.memory_atom import EdgeLabel
    memory = VibeMemory(agent_id='scope-window', tenant_id='tenant-a', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'bounded.db'))
    other = VibeMemory(agent_id='other', tenant_id='tenant-a', embedding_backend='tfidf',
                       db_path=str(tmp_path / 'bounded.db'))
    try:
        old = memory.store('资源持有者没有结束动作', session_id='fixture', scope={'service': 'orders'},
                           auto_build_edges=False, auto_episode=False)
        for index in range(99):
            memory.store(f'接口超时连接池维护记录编号{index}，连接资源配置记录', session_id='fixture',
                         scope={'service': 'orders'}, auto_build_edges=False, auto_episode=False)
        repair = memory.store('连接池耗尽导致接口超时，释放连接后恢复正常', session_id='fixture',
                              scope={'service': 'orders'}, auto_build_edges=False, auto_episode=False)
        foreign = other.store('接口超时连接池修复连接池', session_id='fixture',
                              scope={'service': 'orders'}, auto_build_edges=False, auto_episode=False)
        memory.link(repair.id, old.id, label=EdgeLabel.REFERENCE)
        result = run(memory, '接口超时的根因以及如何修复连接池', scope={'service': 'orders'},
                     include_references=True, review_references=True)
        assert old.id not in [item['id'] for item in result['reference_review']]
        assert foreign.id not in [item['id'] for item in result['candidates']]
        assert repair.id in [item['id'] for item in result['candidates']]
        assert len(result['anchor_evidence']) <= 6
        assert result['retrieval_diagnostics']['eligible_window_truncated'] is True
        assert result['retrieval_diagnostics']['eligible_session_rows'] == 101
        assert result['retrieval_diagnostics']['eligible_pool_rows'] == 100
    finally:
        other.storage.conn.close()
        memory.storage.conn.close()


def test_lexical_supplement_does_not_add_out_of_scope_evidence(tmp_path):
    memory = VibeMemory(agent_id='scope-probe', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'scope.db'))
    try:
        wrong = memory.store('连接池耗尽导致接口超时，释放连接后恢复正常',
                             session_id='fixture', scope={'service': 'billing'},
                             auto_build_edges=False, auto_episode=False)
        for index in range(5):
            memory.store(f'接口超时连接池维护记录编号{index}，连接资源配置记录',
                         session_id='fixture', scope={'service': 'orders'},
                         auto_build_edges=False, auto_episode=False)
        result = run(memory, '接口超时的根因以及如何修复连接池', scope={'service': 'orders'})
        assert wrong.id not in [item['id'] for item in result['baseline']]
        assert len(result['baseline']) == 5
        assert wrong.id not in [item['id'] for item in result['candidates']]
    finally:
        memory.storage.conn.close()


def test_experiment_filters_sdk_scope_boost_results_without_changing_raw_baseline(tmp_path):
    memory = VibeMemory(agent_id='scope-probe', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'boost.db'))
    try:
        wrong = memory.store('接口超时连接池恢复记录', session_id='fixture',
                             scope={'service': 'billing'},
                             auto_build_edges=False, auto_episode=False)
        result = run(memory, '接口超时连接池', scope={'service': 'orders'},
                     include_references=True, review_references=True)
        assert [item['id'] for item in result['baseline']] == [wrong.id]
        assert result['candidates'] == []
        assert result['anchor_evidence'] == []
        assert result['reference_review'] == []
        assert result['selected_evidence'] == []
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('stored_scope', [
    {}, {'service': 'orders'}, {'service': 'orders', 'environment': 'test'},
    {'service': 'billing', 'environment': 'production'}])
def test_scoped_experiment_requires_every_requested_key(tmp_path, stored_scope):
    memory = VibeMemory(agent_id='scope-probe', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'keys.db'))
    try:
        wrong = memory.store('接口超时连接池恢复记录', session_id='fixture', scope=stored_scope,
                             auto_build_edges=False, auto_episode=False)
        good = memory.store('接口超时连接池恢复记录', session_id='fixture',
                            scope={'service': 'orders', 'environment': 'production', 'operation': 'timeout'},
                            auto_build_edges=False, auto_episode=False)
        result = run(memory, '接口超时连接池', scope={'service': 'orders', 'environment': 'production'})
        assert [item['id'] for item in result['candidates']] == [good.id]
        assert wrong.id not in [item['id'] for item in result['selected_evidence']]
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('query_scope', [None, {}, {'service': 'orders'}])
def test_scope_filter_keeps_unscoped_queries_and_matching_extra_metadata(tmp_path, query_scope):
    memory = VibeMemory(agent_id='scope-probe', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'matching.db'))
    try:
        atom = memory.store('接口超时连接池恢复记录', session_id='fixture',
                            scope={'service': 'orders', 'environment': 'production'},
                            auto_build_edges=False, auto_episode=False)
        result = run(memory, '接口超时连接池', scope=query_scope)
        assert [item['id'] for item in result['candidates']] == [atom.id]
    finally:
        memory.storage.conn.close()


def test_answer_citation_check_rejects_unknown_and_cross_case_ids_without_rewriting_first_answer():
    from experiments.resolution_selection_probe import check_answer_citations

    pack = {'dataset_id': 'answer-test', 'cases': [
        {'case_id': 'a', 'evidence': [{'id': 'a1', 'text': 'repair'}]},
        {'case_id': 'b', 'evidence': [{'id': 'b1', 'text': 'different case'}]}]}
    response = {'dataset_id': 'answer-test', 'results': [
        {'case_id': 'a', 'answer': '原因已经确定[b1][ghost]'},
        {'case_id': 'b', 'answer': '只是恢复操作[b1]'}]}
    rows = check_answer_citations(pack, response)
    assert rows[0]['invalid_citation_ids'] == ['b1', 'ghost']
    assert rows[0]['citation_status'] == 'invalid'
    assert rows[0]['answer'] == '原因已经确定[b1][ghost]'
    assert rows[1]['citation_status'] == 'valid_ids'
    assert rows[1]['semantic_support'] == 'not_checked'


def test_answer_citation_ids_neither_verify_false_claims_nor_mark_uncited_answers_correct():
    from experiments.resolution_selection_probe import check_answer_citations

    pack = {'dataset_id': 'answer-test', 'cases': [
        {'case_id': 'a', 'evidence': [{'id': 'a1', 'text': '重启后恢复，原因未查明。'}]},
        {'case_id': 'b', 'evidence': []}]}
    rows = check_answer_citations(pack, {'dataset_id': 'answer-test', 'results': [
        {'case_id': 'a', 'answer': '根因已经确定为磁盘损坏[a1]'},
        {'case_id': 'b', 'answer': '根因未知'}]})
    assert rows[0]['citation_status'] == 'valid_ids'
    assert rows[1]['citation_status'] == 'none'
    assert all(row['semantic_support'] == 'not_checked' and 'correct' not in row for row in rows)


@pytest.mark.parametrize('results', [[], [{'case_id': 'a', 'answer': ''}],
    [{'case_id': 'a', 'answer': 'x'}, {'case_id': 'a', 'answer': 'y'}],
    [{'case_id': 'other', 'answer': 'x'}]])
def test_answer_citation_check_rejects_missing_duplicate_or_invalid_answer_rows(results):
    from experiments.resolution_selection_probe import check_answer_citations
    with pytest.raises(ValueError, match='Invalid answer batch'):
        check_answer_citations({'dataset_id': 'answer-test', 'cases': [
            {'case_id': 'a', 'evidence': []}]}, {'dataset_id': 'answer-test', 'results': results})


def test_answer_citation_cli_binds_first_response_to_exact_pack(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    pack, response, report = [tmp_path / name for name in ('pack.json', 'response.json', 'report.json')]
    pack.write_bytes(b'{"dataset_id":"answer-test","cases":[{"case_id":"a","evidence":[]}]}')
    body = {'dataset_id': 'answer-test', 'pack_sha256': hashlib.sha256(pack.read_bytes()).hexdigest(),
            'results': [{'case_id': 'a', 'answer': 'unsupported[ghost]'}]}
    response.write_text(json.dumps(body), encoding='utf-8')
    command = [sys.executable, '-m', 'experiments.resolution_selection_probe', 'check-answers',
               '--pack', str(pack), '--response', str(response), '--report', str(report)]
    subprocess.run(command, cwd=root, capture_output=True, check=True)
    scored = json.loads(report.read_bytes())
    assert scored['rows'][0]['citation_status'] == 'invalid'
    assert scored['response_sha256'] == hashlib.sha256(response.read_bytes()).hexdigest()
    assert scored['eligible_for_default'] is False
    body['pack_sha256'] = 'wrong'
    response.write_text(json.dumps(body), encoding='utf-8')
    failed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert failed.returncode != 0
    assert 'Response pack identity mismatch' in failed.stderr


def test_answer_pack_preserves_unknown_cause_context_and_upstream_failure_without_labels():
    from experiments.resolution_selection_probe import freeze_answer_pack

    pack = {'dataset_id': 'resolution-final-selection-v5', 'cases': [{
        'case_id': 'r', 'question': 'why and how?', 'scope': {}, 'candidates': [
            {'id': 'a', 'text': '释放连接后恢复', 'context_after': '尚无确认根因。'}]}]}
    response = {'dataset_id': pack['dataset_id'], 'results': [
        {'case_id': 'r', 'selected_ids': ['a'], 'text': 'fake confirmed cause'}]}
    answer = freeze_answer_pack(pack, response, review_selections=[
        {'case_id': 'r', 'status': 'fallback', 'fallback_reason': 'call_failure'}])
    assert answer['cases'][0]['evidence'] == [
        {'id': 'a', 'text': '释放连接后恢复', 'context_after': '尚无确认根因。'}]
    assert answer['cases'][0]['review_status'] == 'fallback'
    assert answer['cases'][0]['review_failure'] == 'call_failure'
    assert 'quality' not in str(answer)
    assert 'fake confirmed cause' not in str(answer)


@pytest.mark.parametrize('response,reason', [
    (RuntimeError(), 'call_failure'),
    ({'dataset_id': 'resolution-final-selection-v5', 'results': [
        {'case_id': 'r', 'selected_ids': ['missing']}]}, 'unknown_id'),
    ({'dataset_id': 'resolution-final-selection-v5', 'results': [
        {'case_id': 'r', 'selected_ids': []}]}, None)])
def test_answer_pack_exposes_failure_or_empty_selection_without_repairing_choices(response, reason):
    from experiments.resolution_selection_probe import freeze_answer_pack

    pack = {'dataset_id': 'resolution-final-selection-v5', 'cases': [{
        'case_id': 'r', 'question': 'why?', 'scope': {},
        'candidates': [{'id': 'a', 'text': 'maintenance noise'},
                       {'id': 'b', 'text': 'unverified guess'}]}]}
    case = freeze_answer_pack(pack, response)['cases'][0]
    assert case['selection_failure'] == reason
    assert case['evidence'] == (pack['cases'][0]['candidates'] if reason else [])
    assert case['selection_status'] == ('fallback' if reason else 'selected')


def test_answer_cli_exports_bound_original_evidence_not_scored_labels(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    report = tmp_path / 'answers.json'
    command = [sys.executable, '-m', 'experiments.resolution_selection_probe', 'answers',
        '--cases', str(root / 'experiments/resolution_reference_competition_cases.json'),
        '--pack', str(root / 'results/resolution_final_selection_pack.json'),
        '--baseline', str(root / 'results/resolution_final_selection_baseline.json'),
        '--response', str(root / 'results/resolution_final_selection_response.json'),
        '--report', str(report)]
    subprocess.run(command, cwd=root, check=True, capture_output=True)
    pack = json.loads(report.read_bytes())
    assert [len(case['evidence']) for case in pack['cases']] == [2, 2, 2, 1]
    assert pack['cases'][3]['evidence'][0]['context_after'] == '已观察恢复；排查记录仍未核实，无确认根因。'
    assert 'label_aliases' not in str(pack)
    assert 'relevant_ids' not in str(pack)
    assert pack['final_pack_sha256'] == '041d93fff70d54235747cbd29da456bc605ad94510ab23bd3e885429ff270183'
    assert all('retrieval_diagnostics' not in case for case in pack['cases'])
    baseline = json.loads((root / 'results/resolution_final_selection_baseline.json').read_bytes())
    baseline['retrieval_diagnostics'] = {'r01': {
        'eligible_window_truncated': True, 'candidate_status': 'nonempty',
        'evidence_sufficiency': 'not_assessed', 'session_read_bounded': False}}
    diagnostic_baseline = tmp_path / 'diagnostic-baseline.json'
    diagnostic_baseline.write_text(json.dumps(baseline), encoding='utf-8')
    command[command.index('--baseline') + 1] = str(diagnostic_baseline)
    subprocess.run(command, cwd=root, check=True, capture_output=True)
    diagnosed = json.loads(report.read_bytes())
    assert diagnosed['cases'][0]['retrieval_diagnostics'] == {
        'eligible_window_truncated': True, 'candidate_status': 'nonempty',
        'evidence_sufficiency': 'not_assessed', 'session_read_bounded': False}
    assert diagnosed['cases'][0]['evidence'] == pack['cases'][0]['evidence']
    assert all('retrieval_diagnostics' not in case for case in diagnosed['cases'][1:])
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({'dataset_id': 'resolution-final-selection-v5',
                              'pack_sha256': 'wrong', 'results': []}), encoding='utf-8')
    command[command.index('--response') + 1] = str(bad)
    failed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert failed.returncode != 0
    assert 'Response pack identity mismatch' in failed.stderr


def test_final_pack_preserves_frozen_context_and_separates_selection_stage():
    from experiments.resolution_selection_probe import freeze_final_pack

    review = {'dataset_id': 'resolution-reference-review-v4', 'cases': [{
        'case_id': 'r', 'question': 'why?', 'scope': {},
        'anchor_evidence': [{'id': 'a', 'text': 'repair', 'context_after': 'observed'}],
        'candidates': [{'id': 'b', 'text': 'cause', 'context_after': 'confirmed'}]}]}
    response = {'dataset_id': review['dataset_id'], 'results': [
        {'case_id': 'r', 'selected_ids': ['b'], 'context_after': 'tampered'}]}
    frozen = freeze_final_pack(review, response)
    assert frozen['pack']['dataset_id'] == 'resolution-final-selection-v5'
    assert frozen['pack']['cases'][0]['candidates'] == [
        {'id': 'a', 'text': 'repair', 'context_after': 'observed'},
        {'id': 'b', 'text': 'cause', 'context_after': 'confirmed'}]
    frozen['pack']['cases'][0]['candidates'][0]['text'] = 'changed'
    assert review['cases'][0]['anchor_evidence'][0]['text'] == 'repair'


@pytest.mark.parametrize('response', [RuntimeError(), {'dataset_id': 'resolution-reference-review-v4',
    'results': [{'case_id': 'r', 'selected_ids': ['unknown']}]}])
def test_final_pack_keeps_anchors_but_does_not_forward_failed_review_fallback(response):
    from experiments.resolution_selection_probe import freeze_final_pack

    review = {'dataset_id': 'resolution-reference-review-v4', 'cases': [{
        'case_id': 'r', 'question': 'why?', 'scope': {},
        'anchor_evidence': [{'id': 'a', 'text': 'repair'}],
        'candidates': [{'id': 'b', 'text': 'excluded cause'}]}]}
    frozen = freeze_final_pack(review, response)
    assert frozen['review_selections'][0]['status'] == 'fallback'
    assert frozen['pack']['cases'][0]['candidates'] == [{'id': 'a', 'text': 'repair'}]


def test_final_pack_empty_review_and_legal_wrong_choices_are_not_semantically_rewritten():
    from experiments.resolution_selection_probe import freeze_final_pack, score_result
    from experiments.selection_response_probe import process_selection

    review = {'dataset_id': 'resolution-reference-review-v4', 'cases': [{
        'case_id': 'r', 'question': 'why?', 'scope': {},
        'anchor_evidence': [{'id': 'a', 'text': 'repair'}],
        'candidates': [{'id': 'b', 'text': 'excluded cause'}]}]}
    for ids, expected in [([], ['a']), (['b'], ['a', 'b'])]:
        frozen = freeze_final_pack(review, {'dataset_id': review['dataset_id'],
            'results': [{'case_id': 'r', 'selected_ids': ids}]})
        assert [item['id'] for item in frozen['pack']['cases'][0]['candidates']] == expected
        assert frozen['review_selections'][0]['status'] != 'fallback'
    pack = frozen['pack']
    selection = process_selection(pack, {'dataset_id': pack['dataset_id'],
        'results': [{'case_id': 'r', 'selected_ids': ['b']}]})['results'][0]
    assert score_result({'baseline': [{'id': 'a'}], 'selection': selection}, {'a'}, {'b'}) == {
        'baseline_relevant_ids': ['a'], 'selected_relevant_ids': [],
        'selected_negative_ids': ['b'], 'lost_relevant_ids': ['a']}


def test_finalize_cli_freezes_bound_review_and_scores_missing_evidence(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    inputs = root / 'results'
    pack, baseline = tmp_path / 'final.json', tmp_path / 'baseline.json'
    command = [sys.executable, '-m', 'experiments.resolution_selection_probe', 'finalize',
        '--cases', str(root / 'experiments/resolution_reference_competition_cases.json'),
        '--pack', str(pack), '--baseline', str(baseline),
        '--review-pack', str(inputs / 'resolution_reference_content_pack.json'),
        '--review-baseline', str(inputs / 'resolution_reference_content_baseline.json'),
        '--response', str(inputs / 'resolution_reference_content_response.json')]
    subprocess.run(command, cwd=root, check=True, capture_output=True)
    frozen = json.loads(pack.read_bytes())
    assert [len(case['candidates']) for case in frozen['cases']] == [7, 7, 7, 6]
    response, report = tmp_path / 'response.json', tmp_path / 'report.json'
    response.write_text(json.dumps({'dataset_id': frozen['dataset_id'],
        'pack_sha256': json.loads(baseline.read_bytes())['pack_sha256'],
        'results': [{'case_id': case['case_id'], 'selected_ids': []} for case in frozen['cases']]}),
        encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'score',
        '--cases', command[command.index('--cases') + 1], '--pack', str(pack),
        '--baseline', str(baseline), '--response', str(response), '--report', str(report)],
        cwd=root, check=True, capture_output=True)
    scored = json.loads(report.read_bytes())
    assert scored['rows'][2]['quality']['missing_selected_relevant_ids'] == ['c1', 'c4']
    assert scored['rows'][2]['quality']['missing_candidate_relevant_ids'] == []
    assert len(scored['review_selections']) == 4
    response.write_text(json.dumps({'dataset_id': 'resolution-reference-review-v4',
        'pack_sha256': 'wrong', 'results': []}), encoding='utf-8')
    command[command.index('--response') + 1] = str(response)
    failed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert failed.returncode != 0
    assert 'Response pack identity mismatch' in failed.stderr


def test_content_review_exposes_third_reference_with_context_without_changing_final_pool():
    import json
    from pathlib import Path
    from experiments.resolution_selection_probe import export_cases

    case = json.loads((Path(__file__).resolve().parents[1] /
                       'experiments/resolution_reference_competition_cases.json').read_bytes())['cases'][2]
    ordinary = export_cases([case], include_references=True, reference_limit=2)
    reviewed = export_cases([case], include_references=True, reference_limit=2,
                            review_references=True)
    before, after = ordinary['pack']['cases'][0], reviewed['pack']['cases'][0]
    assert reviewed['pack']['dataset_id'] == 'resolution-reference-review-v4'
    assert len(after['candidates']) == 3
    assert len(after['anchor_evidence']) == 6
    assert '资源持有者未执行结束动作，回收流程一直等待' not in [item['text'] for item in before['candidates']]
    root = next(item for item in after['candidates'] if item['text'].startswith('资源持有者'))
    assert root['context_after'] == '同次事故复盘确认的原因：持有者遗漏结束动作；释放后恢复。'
    assert 'relevant_ids' not in str(reviewed['pack'])


def test_reference_review_cli_proposes_bounded_pool_from_original_evidence(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    pack, baseline = tmp_path / 'pack.json', tmp_path / 'baseline.json'
    common = ['--cases', str(root / 'experiments/resolution_reference_competition_cases.json'),
              '--pack', str(pack), '--baseline', str(baseline)]
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'export',
                    *common, '--include-references', '--review-references'],
                   cwd=root, check=True, capture_output=True)
    frozen = json.loads(pack.read_bytes())
    assert frozen['dataset_id'] == 'resolution-reference-review-v4'
    case = frozen['cases'][2]
    cause = next(item for item in case['candidates'] if item['text'].startswith('资源持有者'))
    response = tmp_path / 'response.json'
    response.write_text(json.dumps({'dataset_id': frozen['dataset_id'],
        'pack_sha256': json.loads(baseline.read_bytes())['pack_sha256'],
        'results': [{'case_id': 'r03', 'selected_ids': [cause['id']],
                     'anchor_evidence': [{'id': 'invented', 'text': 'tampered'}]}]}), encoding='utf-8')
    report = tmp_path / 'report.json'
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'score',
                    *common, '--response', str(response), '--report', str(report)],
                   cwd=root, check=True, capture_output=True)
    scored = json.loads(report.read_bytes())
    assert scored['evaluation_stage'] == 'reference_review'
    row = next(item for item in scored['rows'] if item['case_id'] == 'r03')
    assert len(row['proposed_candidate_pool']) == 7
    assert row['proposed_candidate_pool'][-1]['context_after'] == '同次事故复盘确认的原因：持有者遗漏结束动作；释放后恢复。'
    assert 'tampered' not in str(row['proposed_candidate_pool'])
    assert set(row['quality']['proposed_pool_relevant_ids']) == {'c1', 'c4'}
    assert row['quality']['missing_proposed_relevant_ids'] == []


def test_reference_review_requires_explicit_reference_opt_in():
    from experiments.resolution_selection_probe import export_cases

    with pytest.raises(ValueError, match='review_references requires include_references'):
        export_cases([], review_references=True)


def test_two_reference_slots_show_both_competitors_without_changing_single_slot():
    import json
    from pathlib import Path
    from experiments.resolution_selection_probe import export_cases

    cases = json.loads((Path(__file__).resolve().parents[1] /
                        'experiments/resolution_reference_competition_cases.json').read_bytes())['cases'][:2]
    single = export_cases(cases, include_references=True)
    double = export_cases(cases, include_references=True, reference_limit=2)
    assert single['pack']['dataset_id'] == 'resolution-reference-v2'
    assert double['pack']['dataset_id'] == 'resolution-reference-v3'
    assert [len(case['candidates']) for case in single['pack']['cases']] == [7, 7]
    for case in double['pack']['cases']:
        assert len(case['candidates']) == 8
        assert len(case['references']) == 2
        assert {'资源持有者未执行结束动作，回收流程一直等待',
                '长事务没有结束，持有的资源无法归还'} <= {item['text'] for item in case['candidates']}


@pytest.mark.parametrize('limit', [0, 3, True, 1.5])
def test_reference_budget_rejects_unsupported_limits(limit):
    from experiments.resolution_selection_probe import export_cases

    with pytest.raises(ValueError, match='reference_limit must be 1 or 2'):
        export_cases([], include_references=True, reference_limit=limit)


def test_repeated_reference_target_does_not_consume_second_slot():
    import json
    from pathlib import Path
    from experiments.resolution_selection_probe import export_cases

    case = json.loads((Path(__file__).resolve().parents[1] /
                       'experiments/resolution_reference_competition_cases.json').read_bytes())['cases'][0]
    case['references'] = [{'from_id': 'repair', 'to_id': 'suspect'},
                          {'from_id': 'n0', 'to_id': 'suspect'},
                          {'from_id': 'n0', 'to_id': 'cause'}]
    exported = export_cases([case], include_references=True, reference_limit=2)
    evidence = exported['pack']['cases'][0]
    assert len(evidence['candidates']) == 8
    assert len({item['id'] for item in evidence['candidates']}) == 8
    assert '资源持有者未执行结束动作，回收流程一直等待' in [item['text'] for item in evidence['candidates']]


def test_competition_cli_exports_two_slot_version(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    pack = tmp_path / 'pack.json'
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'export',
                    '--cases', str(root / 'experiments/resolution_reference_competition_cases.json'),
                    '--pack', str(pack), '--baseline', str(tmp_path / 'baseline.json'),
                    '--include-references', '--reference-limit', '2'],
                   cwd=root, check=True, capture_output=True)
    exported = json.loads(pack.read_bytes())
    assert exported['dataset_id'] == 'resolution-reference-v3'
    assert [len(case['candidates']) for case in exported['cases']] == [8, 8, 8, 8]


def test_opt_in_reference_recovers_joint_evidence_without_rewriting_context(tmp_path):
    from vibe_memory.models.memory_atom import EdgeLabel

    memory = VibeMemory(agent_id='resolution-test', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'joint.db'))
    try:
        repair = memory.store('连接池耗尽导致接口超时，释放连接后恢复正常',
                              session_id='fixture', context_after='仅记录恢复动作。',
                              auto_build_edges=False, auto_episode=False)
        cause = memory.store('长事务没有结束，持有的资源无法归还',
                             session_id='fixture', context_before='同次事故的根因记录。',
                             auto_build_edges=False, auto_episode=False)
        for index in range(5):
            memory.store(f'接口超时连接池维护记录编号{index}，连接资源配置记录',
                         session_id='fixture', auto_build_edges=False, auto_episode=False)
        memory.link(repair.id, cause.id, label=EdgeLabel.REFERENCE)
        question = '接口超时的根因以及如何修复连接池'
        original = run(memory, question)
        assert cause.id not in [item['id'] for item in original['candidates']]

        def selector(pack):
            return {'dataset_id': pack['dataset_id'], 'results': [
                {'case_id': 'q', 'selected_ids': [repair.id, cause.id]}]}

        result = run(memory, question, selector=selector, include_references=True)
        assert len(result['candidates']) == 7
        assert [item['id'] for item in result['selected_evidence']] == [repair.id, cause.id]
        assert result['selected_evidence'][1]['context_before'] == '同次事故的根因记录。'
        assert result['selected_evidence'][0]['context_after'] == '仅记录恢复动作。'
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('boundary', ['scope', 'cold', 'archived', 'reverse', 'adjacent', 'deleted', 'owner'])
@pytest.mark.parametrize('reference_limit', [1, 2])
def test_reference_expansion_does_not_bypass_evidence_boundaries(tmp_path, boundary, reference_limit):
    from vibe_memory.models.memory_atom import EdgeLabel, Lifecycle

    memory = VibeMemory(agent_id='resolution-test', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'boundaries.db'))
    other = VibeMemory(agent_id='other', embedding_backend='tfidf',
                       db_path=str(tmp_path / 'boundaries.db'))
    try:
        repair = memory.store('连接池耗尽导致接口超时，释放连接后恢复正常',
                              session_id='fixture', scope={'service': 'orders'},
                              auto_build_edges=False, auto_episode=False)
        writer = other if boundary == 'owner' else memory
        cause = writer.store('长事务没有结束，持有的资源无法归还', session_id='fixture',
                             scope={'service': 'billing' if boundary == 'scope' else 'orders'},
                             auto_build_edges=False, auto_episode=False)
        for index in range(5):
            memory.store(f'接口超时连接池维护记录编号{index}，连接资源配置记录',
                         session_id='fixture', scope={'service': 'orders'},
                         auto_build_edges=False, auto_episode=False)
        if boundary == 'reverse':
            memory.link(cause.id, repair.id, label=EdgeLabel.REFERENCE)
        else:
            memory.link(repair.id, cause.id, label=(EdgeLabel.ADJACENT if boundary == 'adjacent'
                                                   else EdgeLabel.REFERENCE))
        if boundary in ('cold', 'archived'):
            cause.lifecycle = Lifecycle(boundary)
            memory.storage.update_atom(cause)
        elif boundary == 'deleted':
            memory.forget(cause.id)
        result = run(memory, '接口超时的根因以及如何修复连接池', include_references=True,
                     reference_limit=reference_limit, review_references=True)
        assert cause.id not in [item['id'] for item in result['candidates']]
        assert result['references'] == []
        assert result['reference_review'] == []
    finally:
        other.storage.conn.close()
        memory.storage.conn.close()


@pytest.mark.parametrize('context', ['未核实的猜测，不能确认为根因。',
                                   '这是旧版事故，当前版本不适用。',
                                   '排查确认不是该原因，释放后仍失败。'])
def test_reference_is_candidate_not_truth_and_selected_context_cannot_be_rewritten(tmp_path, context):
    from experiments.resolution_selection_probe import score_result
    from vibe_memory.models.memory_atom import EdgeLabel

    memory = VibeMemory(agent_id='resolution-test', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'uncertain.db'))
    try:
        repair = memory.store('连接池耗尽导致接口超时，释放连接后恢复正常',
                              session_id='fixture', auto_build_edges=False, auto_episode=False)
        cause = memory.store('长事务没有结束，持有的资源无法归还', session_id='fixture',
                             context_after=context, auto_build_edges=False, auto_episode=False)
        for index in range(5):
            memory.store(f'接口超时连接池维护记录编号{index}，连接资源配置记录',
                         session_id='fixture', auto_build_edges=False, auto_episode=False)
        memory.link(repair.id, cause.id, label=EdgeLabel.REFERENCE)

        def wrong_selector(pack):
            candidate = next(item for item in pack['cases'][0]['candidates'] if item['id'] == cause.id)
            candidate['context_after'] = '被篡改为已验证。'
            return {'dataset_id': pack['dataset_id'], 'results': [
                {'case_id': 'q', 'selected_ids': [cause.id]}]}

        result = run(memory, '接口超时的根因以及如何修复连接池',
                     include_references=True, selector=wrong_selector)
        assert result['selected_evidence'][0]['context_after'] == context
        assert score_result(result, set(), {cause.id})['selected_negative_ids'] == [cause.id]
    finally:
        memory.storage.conn.close()


def test_selector_can_read_omitted_resolution_and_original_context(tmp_path):
    memory = VibeMemory(agent_id='resolution-test', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'memory.db'))
    text = '连接池耗尽导致接口超时，释放连接后恢复正常'
    try:
        memory.store(text, session_id='fixture', context_after='当前记录：修复已完成。',
                     auto_build_edges=False, auto_episode=False)
        for index in range(5):
            memory.store(f'接口超时连接池维护记录编号{index}，连接资源配置记录',
                         session_id='fixture', auto_build_edges=False, auto_episode=False)

        def selector(pack):
            candidates = pack['cases'][0]['candidates']
            assert len(candidates) == 6
            evidence = next(item for item in candidates if item['text'] == text)
            assert evidence['context_after'] == '当前记录：修复已完成。'
            evidence['text'] = 'selector must not rewrite evidence'
            return {'dataset_id': pack['dataset_id'], 'results': [
                {'case_id': 'q', 'selected_ids': [evidence['id']]}]}

        result = run(memory, '接口超时如何修复连接池', selector=selector)
        assert text not in [item['text'] for item in result['baseline']]
        assert result['selection']['status'] == 'selected'
        assert [item['text'] for item in result['selection']['memories']] == [text]
    finally:
        memory.storage.conn.close()


def test_legal_wrong_selection_is_scored_not_silently_repaired(tmp_path):
    from experiments.resolution_selection_probe import score_result

    memory = VibeMemory(agent_id='resolution-test', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'wrong.db'))
    try:
        negative = memory.store('释放连接未恢复接口超时，不能作为成功方案',
                                session_id='fixture', auto_build_edges=False, auto_episode=False)

        def selector(pack):
            return {'dataset_id': pack['dataset_id'], 'results': [
                {'case_id': 'q', 'selected_ids': [pack['cases'][0]['candidates'][0]['id']]}]}

        result = run(memory, '接口超时如何修复', selector=selector)
        quality = score_result(result, set(), {negative.id})
        assert result['selection']['status'] == 'selected'
        assert quality['selected_negative_ids'] == [negative.id]
        assert result['selection']['memories'][0]['text'] == negative.content
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('selector,reason', [
    (None, 'selector_disabled'),
    (lambda pack: (_ for _ in ()).throw(RuntimeError('private detail')), 'call_failure'),
    (lambda pack: {'dataset_id': pack['dataset_id'], 'results': []}, 'missing_case'),
    (lambda pack: {'dataset_id': pack['dataset_id'], 'results': [
        {'case_id': 'q', 'selected_ids': ['invented']} ]}, 'unknown_id'),
])
def test_failed_selection_keeps_original_fallback_evidence(tmp_path, selector, reason):
    memory = VibeMemory(agent_id='resolution-test', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'fallback.db'))
    try:
        for text in ('接口超时日志记录甲', '接口超时日志记录乙', '接口超时日志记录丙'):
            memory.store(text, session_id='fixture', auto_build_edges=False, auto_episode=False)
        result = run(memory, '接口超时', selector=selector)
        assert result['selection']['fallback_reason'] == reason
        assert result['selection']['memories'] == [
            {'id': item['id'], 'text': item['text']} for item in result['baseline'][:2]]
        assert 'private detail' not in str(result)
    finally:
        memory.storage.conn.close()


def test_quality_report_exposes_discarded_relevant_evidence(tmp_path):
    from experiments.resolution_selection_probe import score_result

    memory = VibeMemory(agent_id='resolution-test', embedding_backend='tfidf',
                        db_path=str(tmp_path / 'loss.db'))
    try:
        first = memory.store('接口超时根因：连接池耗尽', session_id='fixture',
                             auto_build_edges=False, auto_episode=False)
        second = memory.store('接口超时修复：释放连接恢复正常', session_id='fixture',
                              auto_build_edges=False, auto_episode=False)

        def selector(pack):
            return {'dataset_id': pack['dataset_id'], 'results': [
                {'case_id': 'q', 'selected_ids': [first.id]}]}

        result = run(memory, '接口超时', selector=selector)
        quality = score_result(result, {first.id, second.id}, set())
        assert quality['selected_relevant_ids'] == [first.id]
        assert quality['lost_relevant_ids'] == [second.id]
        assert result['selection']['memories'] == [{'id': first.id, 'text': first.content}]
    finally:
        memory.storage.conn.close()


def test_export_contains_evidence_but_not_scoring_labels():
    from experiments.resolution_selection_probe import export_cases

    case = {'case_id': 'q1', 'question': '接口超时如何修复',
            'atoms': [{'id': 'm0', 'text': '接口超时，释放连接恢复正常',
                       'context_after': '后来确认修复成功。'}],
            'relevant_ids': ['m0'], 'negative_ids': [], 'expected_answer': 'secret test label'}
    exported = export_cases([case])
    assert set(exported['pack']) == {'dataset_id', 'cases'}
    candidate = exported['pack']['cases'][0]['candidates'][0]
    assert candidate['id'] == 'c0'
    assert candidate['context_after'] == '后来确认修复成功。'
    assert 'relevant_ids' not in str(exported['pack'])
    assert 'expected_answer' not in str(exported['pack'])
    assert 'secret test label' not in str(exported['pack'])
    assert 'label_aliases' not in exported['pack']


def test_reference_export_is_versioned_and_uses_only_public_candidate_ids():
    from experiments.resolution_selection_probe import export_cases

    case = {'case_id': 'joint', 'question': '接口超时的根因以及如何修复连接池',
            'noise_count': 5, 'atoms': [
                {'id': 'repair', 'text': '连接池耗尽导致接口超时，释放连接后恢复正常'},
                {'id': 'cause', 'text': '长事务没有结束，持有的资源无法归还',
                 'context_before': '同次事故已核实的根因。'}],
            'references': [{'from_id': 'repair', 'to_id': 'cause'}],
            'relevant_ids': ['repair', 'cause'], 'negative_ids': []}
    off = export_cases([case])
    on = export_cases([case], include_references=True)
    before, after = off['pack']['cases'][0], on['pack']['cases'][0]
    assert off['pack']['dataset_id'] == 'resolution-context-v1'
    assert on['pack']['dataset_id'] == 'resolution-reference-v2'
    assert len(before['candidates']) == 6
    assert len(after['candidates']) == 7
    repair = next(item for item in after['candidates'] if item['text'].startswith('连接池耗尽'))
    cause = next(item for item in after['candidates'] if item['text'].startswith('长事务'))
    assert after['references'] == [{'from_id': repair['id'], 'to_id': cause['id'],
                                    'label': '引用', 'source': 'rule'}]
    assert cause['context_before'] == '同次事故已核实的根因。'
    assert 'relevant_ids' not in str(on['pack'])
    assert 'label_aliases' not in on['pack']


def test_export_cli_records_hash_of_saved_pack_bytes(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    pack = tmp_path / 'pack.json'
    baseline = tmp_path / 'baseline.json'
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'export',
                    '--cases', str(root / 'experiments/resolution_context_cases.json'),
                    '--pack', str(pack), '--baseline', str(baseline)],
                   cwd=root, check=True, capture_output=True)
    record = json.loads(baseline.read_bytes())
    assert record['pack_sha256'] == hashlib.sha256(pack.read_bytes()).hexdigest()


def test_reference_cli_flag_exports_new_dataset_without_changing_default(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    pack = tmp_path / 'pack.json'
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'export',
                    '--cases', str(root / 'experiments/resolution_context_cases.json'),
                    '--pack', str(pack), '--baseline', str(tmp_path / 'baseline.json'),
                    '--include-references'], cwd=root, check=True, capture_output=True)
    exported = json.loads(pack.read_bytes())
    assert exported['dataset_id'] == 'resolution-reference-v2'
    assert all('references' in case for case in exported['cases'])


@pytest.mark.parametrize('choice', ['selected', 'empty', 'unknown'])
def test_score_cli_binds_original_context_for_selection_empty_and_fallback(tmp_path, choice):
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    cases = tmp_path / 'cases.json'
    cases.write_text(json.dumps({'cases': [
        {'case_id': 'q', 'question': '接口超时', 'atoms': [
            {'id': 'a', 'text': '接口超时修复记录', 'scope': {'service': 'orders'},
             'context_before': '仅旧版适用。', 'context_after': '2026年9月20日恢复。'}],
         'relevant_ids': ['a'], 'negative_ids': []}]}), encoding='utf-8')
    pack, baseline = tmp_path / 'pack.json', tmp_path / 'baseline.json'
    common = ['--cases', str(cases), '--pack', str(pack), '--baseline', str(baseline)]
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'export',
                    *common, '--include-references'], cwd=root, check=True, capture_output=True)
    response = tmp_path / 'response.json'
    ids = ['c0'] if choice == 'selected' else ([] if choice == 'empty' else ['invented'])
    response.write_text(json.dumps({'dataset_id': 'resolution-reference-v2',
        'pack_sha256': json.loads(baseline.read_bytes())['pack_sha256'],
        'results': [{'case_id': 'q', 'selected_ids': ids,
                     'selected_evidence': [{'id': 'c0', 'context_before': 'tampered'}]}]}), encoding='utf-8')
    report = tmp_path / 'report.json'
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'score',
                    *common, '--response', str(response), '--report', str(report)],
                   cwd=root, check=True, capture_output=True)
    row = json.loads(report.read_bytes())['rows'][0]
    expected = [] if choice == 'empty' else [
        {'id': 'c0', 'text': '接口超时修复记录', 'scope': {'service': 'orders'},
         'context_before': '仅旧版适用。', 'context_after': '2026年9月20日恢复。',
         'source_session': 'fixture'}]
    assert row['selected_evidence'] == expected
    assert row['selection']['status'] == ('fallback' if choice == 'unknown' else 'selected')


def test_score_cli_rejects_response_for_a_different_frozen_pack(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    pack, baseline = tmp_path / 'pack.json', tmp_path / 'baseline.json'
    common = ['--cases', str(root / 'experiments/resolution_context_cases.json'),
              '--pack', str(pack), '--baseline', str(baseline)]
    subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'export', *common],
                   cwd=root, check=True, capture_output=True)
    response = tmp_path / 'response.json'
    response.write_text(json.dumps({'dataset_id': 'resolution-context-v1',
                                   'pack_sha256': 'different', 'results': []}), encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'experiments.resolution_selection_probe', 'score',
                             *common, '--response', str(response), '--report', str(tmp_path / 'report.json')],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Response pack identity mismatch' in result.stderr
