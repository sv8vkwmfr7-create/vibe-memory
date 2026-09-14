"""Anonymous ID/hash and actual MCP stability checks for experimental bridge."""
import argparse
import json
import os
import random
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from experiments.precision_formula_probe import compare
from experiments.mcp_session_replay import replay
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.storage.sqlite_store import VibeStorage


def worker(data):
    store = VibeStorage(':memory:')
    try:
        for a in data['atoms']:
            store.insert_atom(MemoryAtom(id=a['id'], agent_id='probe', session_id=a['session_id'],
                content=a['content'], summary=a['summary'], created_at=datetime(2026, 9, 14)))
        for i, e in enumerate(data['edges']):
            store.insert_edge(Edge(id=f'edge-{i}', from_atom_id=e['from_atom_id'],
                to_atom_id=e['to_atom_id'], label=EdgeLabel(e['label'])))
        return compare(store, 'probe', data['queries'],
                       {a['id']: f'atom-{i}' for i,a in enumerate(data['atoms'])},
                       ('raw', 'primary_bridge'))
    finally:
        store.conn.close()


def run(data):
    conditions = []
    for seed in range(12):
        renamed = deepcopy(data)
        order = list(range(len(data['atoms'])))
        random.Random(seed).shuffle(order)
        mapping = {a['id']: f'{order[i]:08x}-0000-0000-0000-000000000000'
                   for i,a in enumerate(data['atoms'])}
        for a in renamed['atoms']:
            a['id'] = mapping[a['id']]
        for e in renamed['edges']:
            e['from_atom_id'], e['to_atom_id'] = mapping[e['from_atom_id']], mapping[e['to_atom_id']]
        for q in renamed['queries']:
            q['relevant_ids'] = [mapping[x] for x in q['relevant_ids']]
        for hash_seed in ('0', '37'):
            result = subprocess.run([sys.executable, '-m', 'experiments.primary_bridge_stability', '--worker'],
                input=json.dumps(renamed), capture_output=True, text=True, encoding='utf-8',
                env={**os.environ, 'PYTHONHASHSEED': hash_seed}, timeout=30, check=True)
            conditions.append({'permutation': seed, 'hash_seed': hash_seed,
                               'report': json.loads(result.stdout)})
    runs = []
    for repeat in range(2):
        for enabled in (False, True):
            for name, module in [('raw', 'vibe_memory.mcp_server'),
                                 ('primary_bridge', 'experiments.primary_bridge_server')]:
                runs.append({'repeat': repeat, 'variant': name,
                             **replay(data, enabled, server_module=module)})
    return {'conditions': ('24 fresh manual-graph core runs: 12 ID permutations x 2 hash seeds. '
        '8 actual sequential MCP subprocess replays: store (automatic edges), manual link, '
        'session_start, precision/budget recall and reinforcement, two repeats x maintenance off/on '
        'x raw/experimental server. MCP generates fresh IDs; paired variants do not share identical '
        'IDs/timestamps. Experimental server patches precision only; default production unchanged. '
        'Local assistant labels, no independent human/LLM/UI quality proof; private text omitted; '
        'temporary databases retained.'), 'core_runs': conditions, 'mcp_runs': runs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path, nargs='?')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(json.load(sys.stdin))))
    else:
        print(json.dumps(run(json.loads(args.corpus.read_text(encoding='utf-8-sig')))))
