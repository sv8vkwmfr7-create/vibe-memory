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


def probe(data, id_order=None, repeats=12):
    data = deepcopy(data)
    id_order = list(range(len(data['atoms']))) if id_order is None else id_order
    mapping = {a['id']: f'{id_order[i]:08x}-0000-0000-0000-000000000000' for i,a in enumerate(data['atoms'])}
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
    anonymous = {a['id']: f'atom-{i}' for i,a in enumerate(data['atoms'])}
    candidates = [{ 'query_id': f'query-{i}', 'ids': [anonymous[a.id] for a in store.get_recall_candidates(
                    'local-replay',q['text'],limit=100,graph_seed_limit=5,graph_neighbor_limit=20)]}
                  for i,q in enumerate(data['queries'])]
    from vibe_memory.retrieval.ppr import recall
    q = data['queries'][1]
    ablation = {name: [anonymous[a.id] for a in recall(q['text'], 'local-replay', store,
                        mode='budget', top_k=5, strategies=strategies)['atoms']]
                for name,strategies in [('default',['semantic','bm25','graph','temporal']),
                                        ('no_temporal',['semantic','bm25','graph'])]}
    store.conn.close()
    for q in data['queries']:
        q['relevant_ids']=[mapping[x] for x in q['relevant_ids']]
    runs=[]
    for i in range(repeats):
        r=replay(data, bool(i%2), seed_path=root/'seed.db')
        runs.append({'maintenance':bool(i%2),'rows':[{'query_id':x['query_id'],'mode':x['mode'],
                     'recall':x['recall'],'returned_ids':x['returned_ids']} for x in r['rows']]})
    return {'conditions':'Fixed creation timestamps, insertion order and manual edges; read-only seed cloned into fresh WAL DB for each real MCP subprocess; off/on alternating runs; no automatic edges. Current time and reinforcement last-access timestamps not frozen. Not equivalent to original store-built graph or independent labels. Private text never reported; test DBs retained.', 'candidates':candidates, 'query_1_initial_ablation':ablation, 'runs':runs}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus',type=Path)
    args=parser.parse_args()
    print(json.dumps(probe(json.loads(args.corpus.read_text(encoding='utf-8-sig')))))
