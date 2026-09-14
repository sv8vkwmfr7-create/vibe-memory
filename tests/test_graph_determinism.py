"""The same graph must not rank differently under Python hash randomization."""
import os
import subprocess
import sys

from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.retrieval.strategies import GraphStrategy, TemporalStrategy
from vibe_memory.storage.sqlite_store import VibeStorage


def test_temporal_abstains_when_all_recency_scores_are_equal():
    from datetime import datetime, timedelta
    now = datetime.now()
    atoms = [MemoryAtom(id=str(i), agent_id="test", session_id="s", content="memory",
                        summary="memory", created_at=now - timedelta(days=i)) for i in range(6)]
    assert TemporalStrategy().search(atoms, top_k=2) == []


def test_temporal_still_ranks_memories_when_recency_distinguishes_them():
    from datetime import datetime, timedelta
    now = datetime.now()
    atoms = [MemoryAtom(id=str(i), agent_id="test", session_id="s", content="memory",
                        summary="memory", created_at=now - timedelta(days=age))
             for i, age in enumerate((30, 1))]
    ranked = TemporalStrategy().search(atoms, top_k=2)
    assert [i for i, score in ranked] == [1, 0]


def test_equal_graph_scores_follow_seed_priority_not_atom_id():
    ranks = []
    for ids in (("a", "b", "c", "d", "e", "f"), ("z", "y", "x", "c", "b", "a")):
        store = VibeStorage(":memory:")
        for index, atom_id in enumerate(ids):
            store.insert_atom(MemoryAtom(id=atom_id, agent_id="test", session_id="s",
                              content=f"node-{index}", summary=f"node-{index}"))
        for index in (0, 1, 3, 4):
            store.insert_edge(Edge(id=f"edge-{index}", from_atom_id=ids[index],
                                   to_atom_id=ids[index+1], label=EdgeLabel.CAUSAL))
        ranked = GraphStrategy(store, "budget").search([store.get_atom(ids[0]), store.get_atom(ids[3])], top_k=6)
        ranks.append([ids.index(atom_id) for atom_id, score in ranked])
        store.conn.close()
    assert ranks == [[0, 3, 1, 4, 2, 5], [0, 3, 1, 4, 2, 5]]


def test_graph_rank_is_stable_across_hash_seeds():
    code = '''
from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.retrieval.strategies import GraphStrategy
s=VibeStorage(":memory:")
for name in ("a","b","c","d","e","f"):
 s.insert_atom(MemoryAtom(id=name,agent_id="x",session_id="s",content=name,summary=name))
for source,target in (("a","b"),("b","c"),("d","e"),("e","f")):
 s.insert_edge(Edge(id=source,from_atom_id=source,to_atom_id=target,label=EdgeLabel.CAUSAL))
print([name for name,score in GraphStrategy(s,"budget").search([s.get_atom("a"),s.get_atom("d")],top_k=6)])
'''
    outputs = [subprocess.run([sys.executable, "-c", code],
               env=dict(os.environ, PYTHONHASHSEED=str(seed)), capture_output=True,
               text=True, check=True).stdout.strip() for seed in range(6)]
    assert len(set(outputs)) == 1, outputs
