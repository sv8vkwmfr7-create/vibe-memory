"""The same graph must not rank differently under Python hash randomization."""
import os
import subprocess
import sys


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
