"""Isolated seed-filter cost with unrelated in-scope edges; not full recall."""
import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom
from vibe_memory.retrieval.seed_filter import SeedFilter
from vibe_memory.storage.sqlite_store import VibeStorage
from experiments.mcp_maintenance_smoke import summary


def run(count):
    store = VibeStorage(":memory:")
    for name in ("a", "bridge", "b", "c", "d", "background-a", "background-b"):
        store.insert_atom(MemoryAtom(id=name, agent_id="test", session_id="s",
                                     content=name, summary=name))
    for source, target in (("a", "bridge"), ("bridge", "b"), ("c", "d")):
        store.insert_edge(Edge(id=source, from_atom_id=source, to_atom_id=target,
                               label=EdgeLabel.CAUSAL))
    # Fixed 1,000 background nodes; unique directed edges unrelated to seeds.
    atom_columns = [row[1] for row in store.conn.execute("PRAGMA table_info(atoms)")]
    atom_template = list(store.conn.execute("SELECT * FROM atoms WHERE id='background-a'").fetchone())
    atom_rows = []
    for index in range(1000):
        row = list(atom_template)
        row[atom_columns.index("id")] = f"node-{index}"
        atom_rows.append(row)
    store.conn.executemany(f"INSERT INTO atoms VALUES ({','.join('?' for _ in atom_columns)})", atom_rows)
    store.insert_edge(Edge(id="template", from_atom_id="background-a",
                           to_atom_id="background-b", label=EdgeLabel.CAUSAL))
    columns = [row[1] for row in store.conn.execute("PRAGMA table_info(edges)")]
    template = list(store.conn.execute("SELECT * FROM edges WHERE id='template'").fetchone())
    def rows():
        for index in range(count - 1):
            row = list(template)
            row[columns.index("id")] = f"background-{index}"
            row[columns.index("from_atom_id")] = f"node-{index // 1000}"
            row[columns.index("to_atom_id")] = f"node-{index % 1000}"
            yield row
    store.conn.executemany(f"INSERT INTO edges VALUES ({','.join('?' for _ in columns)})", rows())
    store.conn.commit()
    seeds = [store.get_atom(name) for name in ("a", "b", "c", "d")]
    elapsed = []
    for index in range(11):
        start = perf_counter()
        kept = SeedFilter().filter(seeds, store)
        duration = (perf_counter() - start) * 1000
        assert {atom.id for atom in kept} == {"a", "b", "c", "d"}
        if index:
            elapsed.append(duration)
    store.conn.close()
    return {"background_edges": count, "samples": len(elapsed), "latency_ms": summary(elapsed)}


if __name__ == "__main__":
    print(json.dumps({"conditions": "single-process in-memory; 1007 nodes, four seeds; unique unrelated directed edges including self loops; isolated filter only; setup and warmup excluded",
                      "runs": [run(count) for count in (1000, 10000, 100000)]}))
