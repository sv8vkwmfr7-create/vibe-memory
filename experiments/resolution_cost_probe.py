"""Opt-in synthetic warm timing; no production changes or model calls."""

import json
import platform
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from experiments.resolution_selection_probe import run
from vibe_memory import VibeMemory


def measure():
    rows = []
    for count, context_chars in [(100, 0), (500, 0), (1000, 0), (1000, 1000)]:
        with TemporaryDirectory(prefix='vibe-cost-') as directory:
            memory = VibeMemory(agent_id='cost-probe', embedding_backend='tfidf',
                                db_path=str(Path(directory) / 'memory.db'))
            try:
                for index in range(count):
                    memory.store(f'连接池维护记录编号{index}，资源配置未确认根因',
                                 session_id='fixture',
                                 scope={'service': 'orders' if index < 100 else 'billing'},
                                 context_after='待' * context_chars,
                                 auto_build_edges=False, auto_episode=False)
                captured = []

                def selector(pack):
                    captured.append(json.dumps(pack, ensure_ascii=False, separators=(',', ':')))
                    return {'dataset_id': pack['dataset_id'], 'results': [
                        {'case_id': 'q', 'selected_ids': []}]}

                read_ms, run_ms = [], []
                for sample in range(4):
                    start = perf_counter()
                    loaded = memory.storage.get_atoms_by_session(
                        'fixture', agent_id=memory.agent_id, tenant_id=memory.tenant_id)
                    elapsed_read = (perf_counter() - start) * 1000
                    assert len(loaded) == count
                    del loaded
                    start = perf_counter()
                    result = run(memory, '连接池根因与修复', scope={'service': 'orders'},
                                 selector=selector)
                    elapsed_run = (perf_counter() - start) * 1000
                    if sample:
                        read_ms.append(elapsed_read)
                        run_ms.append(elapsed_run)
                diagnostic = result['retrieval_diagnostics']
                assert diagnostic['session_rows_loaded'] == count
                assert diagnostic['eligible_pool_rows'] == 100
                assert diagnostic['scope_excluded_session_rows'] == count - 100
                assert not diagnostic['session_read_bounded']
                assert result['selected_evidence'] == []
                payload = captured[-1]
                rows.append({'session_rows': count, 'context_after_chars_per_row': context_chars,
                             'read_samples_ms': read_ms, 'run_samples_ms': run_ms,
                             'read_median_ms': median(read_ms), 'run_median_ms': median(run_ms),
                             'selector_json_chars': len(payload),
                             'selector_json_utf8_bytes': len(payload.encode('utf-8')),
                             'retrieval_diagnostics': diagnostic})
            finally:
                memory.storage.conn.close()
    return {'rows': rows, 'python': platform.python_version(), 'platform': platform.platform(),
            'samples': 3, 'warmups': 1, 'embedding_backend': 'tfidf',
            'model_calls': 0, 'token_count': None, 'model_fee': None,
            'limits': ['Warm same-instance synthetic timings, not cold startup or concurrency.',
                       'Separate session reads are not a breakdown of the full run timing.',
                       'Full run includes SDK recall and selection with a scripted empty response.',
                       'Payload excludes host prompts, wrappers, output and tokenizer overhead.',
                       'Character and UTF-8 byte counts are not model tokens or billing.',
                       'No memory-peak measurement or independent retrieval quality assessment.']}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    report = measure()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['rows'], ensure_ascii=False, indent=2))
