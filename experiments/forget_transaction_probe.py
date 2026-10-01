"""Synthetic transaction/source-lineage probe. No production ingestion integration."""

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from vibe_memory import VibeMemory
from vibe_memory.maintenance import is_sqlite_lock_error
from vibe_memory.models.memory_atom import Edge, EdgeLabel, MemoryAtom


SCHEMA = """
CREATE TABLE experiment_sources (
    tenant_id TEXT, agent_id TEXT, source_id TEXT, blocked INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, agent_id, source_id)
);
CREATE TABLE experiment_atom_sources (
    atom_id TEXT, tenant_id TEXT, agent_id TEXT, source_id TEXT,
    PRIMARY KEY (atom_id, tenant_id, agent_id, source_id)
);
"""


def import_record(memory, atom_id, content, *, sources=(), parents=()):
    """Fixture-only importer: parents inherit root sources; missing lineage is rejected."""
    conn = memory.storage.conn
    scope = (memory.tenant_id, memory.agent_id)
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        roots = set(sources)
        for parent in parents:
            rows = conn.execute(
                "SELECT l.source_id FROM experiment_atom_sources l JOIN atoms a ON a.id=l.atom_id "
                "WHERE l.atom_id=? AND l.tenant_id=? AND l.agent_id=? "
                "AND a.tenant_id=l.tenant_id AND a.agent_id=l.agent_id", (parent, *scope)).fetchall()
            if not rows:
                raise ValueError("parent must exist with lineage in the current scope")
            roots.update(row[0] for row in rows)
        if not roots or any(not isinstance(root, str) or not root.strip() for root in roots):
            raise ValueError("every fixture record requires explicit source lineage")
        for root in sorted(roots):
            row = conn.execute("SELECT blocked FROM experiment_sources WHERE tenant_id=? AND agent_id=? "
                               "AND source_id=?", (*scope, root)).fetchone()
            if row and row[0]:
                return False
        conn.executemany("INSERT OR IGNORE INTO experiment_sources VALUES (?, ?, ?, 0)",
                         [(*scope, root) for root in sorted(roots)])
        # Existing storage CRUD commits internally. Minimal fixture SQL keeps this operation atomic.
        conn.execute("INSERT INTO atoms(id, tenant_id, agent_id, session_id, content, summary, created_at) "
                     "VALUES (?, ?, ?, 'synthetic', ?, ?, ?)",
                     (atom_id, *scope, content, content, "2026-09-30T00:00:00"))
        conn.executemany("INSERT INTO experiment_atom_sources VALUES (?, ?, ?, ?)",
                         [(atom_id, *scope, root) for root in sorted(roots)])
    memory.cold_start.invalidate_cache()
    return True


def forget_source(memory, source_id, *, fail_after_cleanup=False):
    """Delete all fixture descendants of one explicitly selected scoped source, atomically."""
    conn = memory.storage.conn
    scope = (memory.tenant_id, memory.agent_id)
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM experiment_sources WHERE tenant_id=? AND agent_id=? "
                            "AND source_id=?", (*scope, source_id)).fetchone():
            raise ValueError("unknown source")
        ids = [row[0] for row in conn.execute(
            "SELECT l.atom_id FROM experiment_atom_sources l JOIN atoms a ON a.id=l.atom_id "
            "WHERE l.tenant_id=? AND l.agent_id=? AND l.source_id=? "
            "AND a.tenant_id=l.tenant_id AND a.agent_id=l.agent_id ORDER BY l.atom_id", (*scope, source_id))]
        conn.execute("UPDATE experiment_sources SET blocked=1 WHERE tenant_id=? AND agent_id=? AND source_id=?",
                     (*scope, source_id))
        edge_ids = sorted({row[0] for atom_id in ids for row in conn.execute(
            "SELECT id FROM edges WHERE from_atom_id=? OR to_atom_id=?", (atom_id, atom_id))})
        conn.executemany("DELETE FROM edges WHERE id=?", [(edge_id,) for edge_id in edge_ids])
        conn.executemany("DELETE FROM atoms WHERE id=?", [(atom_id,) for atom_id in ids])
        conn.executemany("DELETE FROM experiment_atom_sources WHERE atom_id=?", [(atom_id,) for atom_id in ids])
        if fail_after_cleanup:
            raise RuntimeError("injected failure before commit")
    memory.cold_start.invalidate_cache()
    return ids, edge_ids


def snapshot(memory):
    return {table: [tuple(row) for row in memory.storage.conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2, 3")]
            for table in ("atoms", "edges", "experiment_sources", "experiment_atom_sources")}


def observe(memory):
    conn = memory.storage.conn
    scope = (memory.tenant_id, memory.agent_id)
    return {"local_ids": [r[0] for r in conn.execute("SELECT id FROM atoms WHERE tenant_id=? AND agent_id=? ORDER BY id", scope)],
            "foreign_ids": [r[0] for r in conn.execute("SELECT id FROM atoms WHERE tenant_id='other' ORDER BY id")],
            "edge_ids": [r[0] for r in conn.execute("SELECT id FROM edges ORDER BY id")],
            "forgotten_fts_matches": conn.execute(
                "SELECT COUNT(*) FROM atoms_fts f JOIN atoms a ON a.rowid=f.rowid WHERE atoms_fts MATCH 'violet' "
                "AND a.tenant_id=? AND a.agent_id=?", scope).fetchone()[0],
            "retrieved_ids": [a.id for a in memory.recall("preferred display color violet", top_k=10)["atoms"]]}


def run():
    with TemporaryDirectory(prefix="vibe-forget-transaction-") as directory:
        db = str(Path(directory) / "synthetic.db")
        memory = VibeMemory(agent_id="forget-transaction", db_path=db, embedding_backend="tfidf")
        peer = VibeMemory(agent_id=memory.agent_id, db_path=db, embedding_backend="tfidf")
        foreign = VibeMemory(agent_id=memory.agent_id, tenant_id="other", db_path=db, embedding_backend="tfidf")
        try:
            memory.storage.conn.executescript(SCHEMA)
            content = "The user's preferred display color is violet."
            import_record(memory, "original", content, sources=("preference-v1",))
            import_record(memory, "copy", content, parents=("original",))
            import_record(memory, "chain-copy", content, parents=("copy",))
            import_record(memory, "keep", "Keep calendar reminders enabled.", sources=("calendar-v1",))
            import_record(memory, "keep-2", "Calendar reminders will stay enabled.", parents=("keep",))
            import_record(memory, "mixed-summary", content + " Keep calendar reminders enabled.", parents=("copy", "keep"))
            import_record(foreign, "foreign-original", content, sources=("preference-v1",))
            import_record(foreign, "foreign-keep", "Foreign calendar reminders.", sources=("calendar-v1",))
            for edge_id, source, target, tenant in (
                    ("incident-original", "original", "keep", "default"),
                    ("incident-chain", "chain-copy", "mixed-summary", "default"),
                    ("protected-edge", "keep", "keep-2", "default"),
                    ("foreign-edge", "foreign-original", "foreign-keep", "other")):
                memory.storage.insert_edge(Edge(id=edge_id, from_atom_id=source, to_atom_id=target,
                                               tenant_id=tenant, label=EdgeLabel.SIMILAR))
            before = observe(memory)
            if "original" not in before["retrieved_ids"] or before["forgotten_fts_matches"] != 4:
                raise RuntimeError("fixture must expose the original and four matching facts before deletion")
            initial = snapshot(memory)
            rejected = {}
            for key, action in (
                    ("missing_lineage_rejected", lambda: import_record(memory, "unlabeled", content)),
                    ("foreign_parent_rejected", lambda: import_record(memory, "foreign-child", content, parents=("foreign-original",))),
                    ("unknown_source_rejected", lambda: forget_source(memory, "unknown-source"))):
                try:
                    action()
                except ValueError:
                    rejected[key] = snapshot(memory) == initial
                else:
                    rejected[key] = False
            try:
                forget_source(memory, "preference-v1", fail_after_cleanup=True)
            except RuntimeError as error:
                rollback_restored = (str(error) == "injected failure before commit"
                                     and snapshot(memory) == initial and observe(memory) == before)
            else:
                rollback_restored = False
            peer.storage.conn.execute("PRAGMA busy_timeout=0")
            memory.storage.conn.execute("BEGIN IMMEDIATE")
            try:
                import_record(peer, "racing-import", content, sources=("preference-v1",))
            except sqlite3.OperationalError as error:
                writer_blocked = is_sqlite_lock_error(error)
            else:
                writer_blocked = False
            finally:
                memory.storage.conn.rollback()
            deleted_ids, deleted_edges = forget_source(memory, "preference-v1")
            after = observe(memory)
            peer_blocked = not import_record(peer, "peer-new-id", content, sources=("preference-v1",))
        finally:
            for client in (memory, peer, foreign):
                client.storage.conn.close()
        memory = VibeMemory(agent_id="forget-transaction", db_path=db, embedding_backend="tfidf")
        foreign = VibeMemory(agent_id=memory.agent_id, tenant_id="other", db_path=db, embedding_backend="tfidf")
        try:
            after_restart = observe(memory)
            restart_blocked = not import_record(memory, "restart-new-id", content, sources=("preference-v1",))
            protected_allowed = import_record(memory, "calendar-new-id", "Keep calendar reminders enabled.", sources=("calendar-v1",))
            foreign_allowed = import_record(foreign, "foreign-new-id", content, sources=("preference-v1",))
            relabeled_restores = (import_record(memory, "relabeled-bypass", content, sources=("renamed-source",))
                                  and "relabeled-bypass" in observe(memory)["retrieved_ids"])
            # Deliberately bypass the experimental guard through unchanged production storage.
            memory.storage.insert_atom(MemoryAtom(id="direct-bypass", agent_id=memory.agent_id, session_id="synthetic",
                                                   content=content, summary=content, created_at=datetime(2026, 9, 30)))
            bypass_restores = "direct-bypass" in observe(memory)["retrieved_ids"]
        finally:
            memory.storage.conn.close()
            foreign.storage.conn.close()
    return {"scenario": "synthetic_atomic_source_forgetting",
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "before": before,
            **rejected, "rollback_restored_all_rows": rollback_restored,
            "second_writer_blocked_during_transaction": writer_blocked, "deleted_ids": deleted_ids,
            "deleted_edges": deleted_edges, "after": after, "after_restart": after_restart,
            "peer_import_blocked_after_commit": peer_blocked, "new_id_same_source_blocked_after_restart": restart_blocked,
            "protected_source_import_allowed": protected_allowed, "foreign_same_source_import_allowed": foreign_allowed,
            "relabeled_source_bypass_restores_fact": relabeled_restores,
            "direct_storage_bypass_restores_fact": bypass_restores,
            "complete_forgetting_demonstrated": False, "production_changed": False,
            "evaluation_is_independent": False, "paid_api_calls": 0,
            "limits": "Temporary synthetic TF-IDF database, six local and two foreign-tenant fixture atoms, four fixed edges. "
                      "Caller-declared scoped root-source keys propagate through this experiment-only importer. "
                      "Mixed-source derivatives are wholly deleted, not redacted; unrelated base records remain. "
                      "SQLite atomic deletion/edge cleanup/lineage cleanup/tombstone verified with injected failure, reopen, "
                      "FTS query and a two-connection lock schedule, not a concurrent stress benchmark. "
                      "Source keys are not authenticated or discovered from real data. A relabeled root or direct storage "
                      "can bypass suppression. Production store/batch/seed/merge/update/episode paths, "
                      "physical/WAL/backups, other agent isolation, final answers and user time/price remain unverified. "
                      "No real user data deleted; temporary database removed after closed connections."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("rollback_restored_all_rows", "deleted_ids",
                                                  "new_id_same_source_blocked_after_restart", "direct_storage_bypass_restores_fact")}))
