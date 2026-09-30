"""Disposable known-ID forgetting plan; intentionally not a production importer."""

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom


def observe(memory: VibeMemory) -> dict:
    conn = memory.storage.conn
    return {"retrieved_ids": [atom.id for atom in memory.recall("preferred display color violet", mode="precision", top_k=5)["atoms"]],
            "target_rows": conn.execute("SELECT COUNT(*) FROM atoms WHERE id IN (?, ?)", ("original", "derived-copy")).fetchone()[0],
            "unrelated_rows": conn.execute("SELECT COUNT(*) FROM atoms WHERE id IN (?, ?)", ("unrelated", "unrelated-2")).fetchone()[0],
            "incident_edges": conn.execute("SELECT COUNT(*) FROM edges WHERE from_atom_id IN (?, ?) OR to_atom_id IN (?, ?)",
                                           ("original", "derived-copy", "original", "derived-copy")).fetchone()[0],
            "unrelated_edges": conn.execute("SELECT COUNT(*) FROM edges WHERE id = ?", ("protected-edge",)).fetchone()[0]}


def apply_known_plan(memory: VibeMemory, source_id: str, derived_id: str) -> tuple[list[str], list[str]]:
    targets = [source_id, derived_id]
    if len(set(targets)) != 2 or any((atom := memory.storage.get_atom(atom_id)) is None
                                     or atom.agent_id != memory.agent_id or atom.tenant_id != memory.tenant_id
                                     for atom_id in targets):
        raise ValueError("both distinct explicitly selected atoms must belong to this agent and tenant")
    conn = memory.storage.conn
    edge_ids = [row[0] for row in conn.execute(
        "SELECT id FROM edges WHERE from_atom_id IN (?, ?) OR to_atom_id IN (?, ?) ORDER BY id", (*targets, *targets))]
    conn.execute("CREATE TABLE IF NOT EXISTS experiment_blocked_ids (id TEXT PRIMARY KEY)")
    conn.executemany("INSERT OR IGNORE INTO experiment_blocked_ids(id) VALUES (?)", [(atom_id,) for atom_id in targets])
    conn.commit()
    # Existing SDK forget commits per atom. This experiment-side sequence is not atomic.
    for edge_id in edge_ids:
        conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
    conn.commit()
    for atom_id in targets:
        if not memory.forget(atom_id):
            raise RuntimeError("explicit SDK forget failed")
    return targets, edge_ids


def guarded_import(memory: VibeMemory, atom: MemoryAtom, origin_id: str | None = None) -> bool:
    if memory.storage.conn.execute(
            "SELECT 1 FROM experiment_blocked_ids WHERE id = ? OR id = ?", (atom.id, origin_id or atom.id)).fetchone():
        return False
    memory.storage.insert_atom(atom)
    return True


def run() -> dict:
    with TemporaryDirectory(prefix="vibe-forget-plan-") as directory:
        db_path = str(Path(directory) / "synthetic.db")
        memory = VibeMemory(agent_id="forget-plan", db_path=db_path, embedding_backend="tfidf")
        try:
            fixture = (("original", "user: My preferred display color is violet."),
                       ("derived-copy", "assistant summary: The user's preferred display color is violet."),
                       ("unrelated", "user: Keep calendar reminders enabled."),
                       ("unrelated-2", "assistant: Calendar reminders will stay enabled."))
            atoms = [MemoryAtom(id=atom_id, agent_id="forget-plan", session_id="synthetic", content=content,
                                summary=content, created_at=datetime(2026, 9, 30) + timedelta(seconds=i))
                     for i, (atom_id, content) in enumerate(fixture)]
            for atom in atoms:
                memory.storage.insert_atom(atom)
            for edge_id, source, target in (("incident-edge", "original", "unrelated"),
                                            ("protected-edge", "unrelated", "unrelated-2")):
                memory.storage.insert_edge(Edge(id=edge_id, from_atom_id=source, to_atom_id=target, label=EdgeLabel.SIMILAR))
            before = observe(memory)
            if not {"original", "derived-copy"}.issubset(before["retrieved_ids"]):
                raise RuntimeError("known fact and copy must be recallable before deletion")
            try:
                apply_known_plan(memory, "original", "missing-id")
            except ValueError:
                unknown_rejected = observe(memory) == before
            else:
                unknown_rejected = False
            if not unknown_rejected:
                raise RuntimeError("unknown target caused mutation")
            deleted_ids, deleted_edge_ids = apply_known_plan(memory, "original", "derived-copy")
            after = observe(memory)
        finally:
            memory.storage.conn.close()
        memory = VibeMemory(agent_id="forget-plan", db_path=db_path, embedding_backend="tfidf")
        try:
            after_restart = observe(memory)
            blocked_same_id = not guarded_import(memory, atoms[0])
            blocked_known_source = not guarded_import(memory, replace(atoms[0], id="new-id-with-source"), origin_id="original")
            after_guarded_import = observe(memory)
            imported_unlabeled = guarded_import(memory, replace(atoms[0], id="new-id"))
            after_unlabeled_reimport = observe(memory)
        finally:
            memory.storage.conn.close()
    return {"scenario": "synthetic_known_id_forget_plan", "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "before": before, "unknown_id_rejected_before_mutation": unknown_rejected,
            "deleted_ids": deleted_ids, "deleted_edge_ids": deleted_edge_ids, "after": after,
            "after_restart": after_restart, "known_id_reimport_blocked": blocked_same_id,
            "known_source_reimport_blocked": blocked_known_source, "after_guarded_import": after_guarded_import,
            "unlabeled_new_id_reimported": imported_unlabeled, "after_unlabeled_reimport": after_unlabeled_reimport,
            "complete_forgetting_demonstrated": False, "production_changed": False,
            "evaluation_is_independent": False, "paid_api_calls": 0,
            "limits": "Disposable synthetic TF-IDF experiment with manually known provenance and IDs. Uses existing SDK single-atom forget but experiment-only SQL edge cleanup and tombstone/import guard; multi-step plan is not atomic or production integration. Unknown-ID validation is pre-mutation; no keyword/fuzzy/natural-language target selection. Same-ID and declared-origin reimport are blocked only through this local guard; unlabeled new-ID import restores the fact. Direct storage, backup, physical/WAL, real derivative discovery, concurrent importers, cross-scope access, MCP/HTTP, answer quality and user cost are unverified. No real user data deleted; temporary database cleaned."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("deleted_ids", "deleted_edge_ids", "known_id_reimport_blocked",
                                                     "known_source_reimport_blocked", "unlabeled_new_id_reimported")}))
