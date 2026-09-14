"""Private-corpus frozen database probe; reports only ordinal IDs and scores."""
import argparse
import json
import sys
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.mcp_session_replay import replay
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.storage.sqlite_store import VibeStorage


def probe(data):
    data = deepcopy(data)
    mapping = {a['id']: f'{i:08x}-0000-0000-0000-000000000000' for i,a in enumerate(data['atoms'])}
    root = Path(tempfile.mkdtemp(prefix='vibe-frozen-probe-'))
    store = VibeStorage(str(root/'seed.db'), journal_mode='wal')
    for atom in data['atoms']:
        atom['id'] = mapping[atom['id']]
        store.insert_atom(MemoryAtom(id=atom['id'], agent_id='local-replay', session_id=atom['session_id'],
                         content=atom['content'], summary=atom['summary'], created_at=datetime(2026,9,14)))
    for i,edge in enumerate(data['edges']):
        edge['from_atom_id']=mapping[edge['from_atom_id']]
        edge['to_atom_id']=mapping[edge['to_atom_id']]
        store.insert_edge(Edge(id=f'edge-{i}',from_atom_id=edge['from_atom_id'], to_atom_id=edge['to_atom_id'],
                         label=EdgeLabel(edge['label']), created_at=datetime(2026,9,14)))
    store.conn.close()
    for q in data['queries']:
        q['relevant_ids']=[mapping[x] for x in q['relevant_ids']]
    runs=[]
    for i in range(12):
        r=replay(data, bool(i%2), seed_path=root/'seed.db')
        runs.append({'maintenance':bool(i%2),'rows':[{'query_id':x['query_id'],'mode':x['mode'],
                     'recall':x['recall'],'returned_ids':x['returned_ids']} for x in r['rows']]})
    return {'conditions':'Fixed IDs, creation timestamps, insertion order and manual edges; read-only seed cloned into fresh WAL DB for each real MCP subprocess; twelve off/on alternating runs; no automatic edges. Current time and reinforcement last-access timestamps not frozen. Not equivalent to original store-built graph or independent labels. Private text never reported; test DBs retained.', 'runs':runs}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus',type=Path)
    args=parser.parse_args()
    print(json.dumps(probe(json.loads(args.corpus.read_text(encoding='utf-8-sig')))))
