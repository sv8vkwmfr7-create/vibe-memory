"""Explicit-ID forgetting on disposable synthetic storage; no production fix."""

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom


def observe(memory: VibeMemory) -> dict:
    ids = [atom.id for atom in memory.recall("preferred display color violet", mode="precision", top_k=5)["atoms"]]
    return {"ids": ids, "original_present": "original" in ids,
            "derived_copy_present": "derived-copy" in ids,
            "original_in_storage": memory.storage.get_atom("original") is not None,
            "original_in_semantic_cache": any(item[0] == "original" for item in memory._semantic_cache.get("key", ())),
            "original_in_bm25_cache": any(item[0] == "original" for item in memory._bm25_cache.get("key", ())),
            "incident_edge_rows": memory.storage.conn.execute(
                "SELECT COUNT(*) FROM edges WHERE from_atom_id = ? OR to_atom_id = ?", ("original", "original")).fetchone()[0]}


def run() -> dict:
    with TemporaryDirectory(prefix="vibe-forget-action-") as directory:
        db_path = str(Path(directory) / "synthetic.db")
        memory = VibeMemory(agent_id="forget-probe", db_path=db_path, embedding_backend="tfidf")
        try:
            atoms = [MemoryAtom(id=atom_id, agent_id="forget-probe", session_id="synthetic",
                                content=text, summary=text, created_at=datetime(2026, 9, 29) + timedelta(seconds=i))
                     for i, (atom_id, text) in enumerate((
                         ("original", "user: My preferred display color is violet."),
                         ("derived-copy", "assistant summary: The user's preferred display color is violet."),
                         ("unrelated", "user: Keep calendar reminders enabled.")))]
            for atom in atoms:
                memory.storage.insert_atom(atom)
            memory.storage.insert_edge(Edge(id="synthetic-edge", from_atom_id="original", to_atom_id="unrelated", label=EdgeLabel.SIMILAR))
            before = observe(memory)
            # Warm the real SDK caches before the explicit action.
            if not before["original_present"] or not before["original_in_semantic_cache"] or not before["original_in_bm25_cache"]:
                raise RuntimeError("forget probe must begin with a retrieved original and warmed indexes")
            forgotten = memory.forget("original")
            cache_retained_before_next_recall = {
                "semantic": any(item[0] == "original" for item in memory._semantic_cache.get("key", ())),
                "bm25": any(item[0] == "original" for item in memory._bm25_cache.get("key", ()))}
            after = observe(memory)
        finally:
            memory.storage.conn.close()
        memory = VibeMemory(agent_id="forget-probe", db_path=db_path, embedding_backend="tfidf")
        try:
            after_restart = observe(memory)
            # Controlled importer bypass: restore the exact synthetic source atom.
            memory.storage.insert_atom(atoms[0])
            after_reimport = observe(memory)
        finally:
            memory.storage.conn.close()
    return {"scenario": "synthetic_explicit_id_forgetting", "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "fixture": "three fixed assistant-authored atoms; one manually duplicated summary; one fixed similarity edge",
            "before": before, "forget_returned": forgotten, "cache_retained_before_next_recall": cache_retained_before_next_recall,
            "after": after, "after_restart": after_restart, "after_reimport": after_reimport,
            "complete_forgetting_demonstrated": False, "production_changed": False,
            "evaluation_is_independent": False, "paid_api_calls": 0,
            "limits": "Actual existing SDK forget/recall on a disposable file database, explicitly known target ID and TF-IDF. Fixture inserted via storage, not store/chunk/automatic summaries. Derived copy is manually planted, not evidence of real summary generation. Index-cache metadata observed before/after warmed recall; not proof of wiping process memory. Incident edge rows do not imply reachable graph leakage. Direct storage reimport deliberately bypasses SDK ingest; not a claim about all importers. No natural-language resolution, full derivative deletion, tombstones, backup/WAL physical erasure, MCP/HTTP, concurrency, answer quality, performance or cost measurement. No real user data deleted; temporary synthetic database is cleaned after the run."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"forget_returned": result["forget_returned"], "after": result["after"], "after_reimport": result["after_reimport"]}))
