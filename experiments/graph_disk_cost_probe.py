"""Synthetic TF-IDF disk precision/recall graph cost; no real-data access."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel


def run(scale=1000, graph_shape='chain'):
    if type(scale) is not int or scale < 2:
        raise ValueError('scale must be an integer >= 2')
    if graph_shape not in ('chain', 'star'):
        raise ValueError('graph_shape must be chain or star')
    rows = []
    for mode in ('precision', 'recall'):
        for with_graph in (False, True):
            with TemporaryDirectory(prefix='vibe-graph-cost-') as directory:
                memory = VibeMemory(agent_id='graph-cost', embedding_backend='tfidf',
                                    db_path=str(Path(directory) / 'memory.db'))
                try:
                    for i in range(scale):
                        text = '连接池超时修复' + (' 日常维护配置背景记录' * 5 if i else '')
                        memory.storage.insert_atom(MemoryAtom(
                            id=f'atom-{i:04}', agent_id=memory.agent_id, session_id='fixture',
                            content=text, summary=text,
                            created_at=datetime(2026, 10, 4) + timedelta(microseconds=i)))
                    if with_graph:
                        for i in range(scale - 1):
                            memory.storage.insert_edge(Edge(id=f'edge-{i}',
                                from_atom_id=f'atom-{i if graph_shape == "chain" else 0:04}',
                                to_atom_id=f'atom-{i+1:04}',
                                label=EdgeLabel.SIMILAR))
                        edges = memory.storage.get_retrieval_edges(memory.agent_id)
                        assert len(edges) == scale - 1
                        if graph_shape == 'star':
                            assert {edge.from_atom_id for edge in edges} == {'atom-0000'}
                        del edges
                    times, hits, outputs = [], [], []
                    for sample in range(6):
                        start = perf_counter()
                        result = memory.recall('连接池超时修复', mode=mode, top_k=5)
                        times.append((perf_counter() - start) * 1000)
                        ids = [atom.id for atom in result['atoms']]
                        assert not result['failures']
                        assert all(atom.agent_id == memory.agent_id for atom in result['atoms'])
                        outputs.append(ids)
                        hits.append('atom-0000' in ids)
                    rows.append({'mode': mode, 'atoms': scale, 'edges': scale - 1 if with_graph else 0,
                                 'graph_shape': graph_shape if with_graph else 'none',
                                 'cold_ms': times[0], 'warm_samples_ms': times[1:],
                                 'warm_median_ms': median(times[1:]),
                                 'anchor_hits': sum(hits), 'calls': 6, 'result_ids': outputs})
                finally:
                    memory.storage.conn.close()
    return {'rows': rows, 'model_calls': 0, 'production_changed': False,
            'limits': 'Single synthetic high-match TF-IDF fixture; chain/star graph, not arbitrary dense graph. '
                      'Cold means fresh SDK index, not OS-cold. Recall reinforcement mutates '
                      'temporary records across warm calls. No memory profiling, independent '
                      'quality, dense embeddings, old/new performance or SLA evidence.'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--scale', type=int, default=1000)
    parser.add_argument('--graph-shape', choices=('chain', 'star'), default='chain')
    args = parser.parse_args()
    report = run(args.scale, args.graph_shape)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
