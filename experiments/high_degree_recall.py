"""Measure actual SDK budget recall on a synthetic causal star in memory."""
import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from experiments.mcp_maintenance_smoke import summary


def run(degree):
    memory=VibeMemory('test', ':memory:')
    store=memory.storage
    store.insert_atom(MemoryAtom(id='hub',agent_id='test',session_id='s',content='deployment incident',summary='incident'))
    store.insert_atom(MemoryAtom(id='answer',agent_id='test',session_id='s',content='install runtime dependency',summary='answer'))
    store.insert_edge(Edge(id='answer-edge',from_atom_id='hub',to_atom_id='answer',label=EdgeLabel.CAUSAL))
    columns=[r[1] for r in store.conn.execute('PRAGMA table_info(atoms)')]
    template=list(store.conn.execute("SELECT * FROM atoms WHERE id='answer'").fetchone())
    rows=[]
    for i in range(degree-1):
        row=list(template)
        row[columns.index('id')]=f'noise-{i:06d}'
        row[columns.index('content')]='unrelated background record'
        row[columns.index('summary')]='background'
        rows.append(row)
    store.conn.executemany(f"INSERT INTO atoms VALUES ({','.join('?' for _ in columns)})",rows)
    columns=[r[1] for r in store.conn.execute('PRAGMA table_info(edges)')]
    template=list(store.conn.execute("SELECT * FROM edges WHERE id='answer-edge'").fetchone())
    rows=[]
    for i in range(degree-1):
        row=list(template)
        row[columns.index('id')]=f'edge-{i:06d}'
        row[columns.index('to_atom_id')]=f'noise-{i:06d}'
        rows.append(row)
    store.conn.executemany(f"INSERT INTO edges VALUES ({','.join('?' for _ in columns)})",rows)
    store.conn.commit()
    latencies=[]
    hits=0
    for i in range(6):
        start=perf_counter()
        result=memory.recall('deployment incident',mode='budget',top_k=5)
        elapsed=(perf_counter()-start)*1000
        if i:
            latencies.append(elapsed)
            hits+=any(a.id=='answer' for a in result['atoms'])
    store.conn.close()
    return {'hub_degree':degree,'samples':5,'answer_hits':hits,'latency_ms':summary(latencies)}


if __name__=='__main__':
    print(json.dumps({'conditions':'Single process in-memory SDK budget recall including reinforcement/trace; causal star, uniform edge weights, synthetic lexical hub and graph-only answer; one warmup, five sequential samples; setup excluded. Not production, disk/concurrency, stable timings or independent quality proof.',
                      'runs':[run(n) for n in (1000,10000)]}))
