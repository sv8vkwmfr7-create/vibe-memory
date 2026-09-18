"""
SQLite 存储层

L1 原型：SQLite 存储 MemoryAtom + Edge。
后续升级：pgvector（向量检索）+ Neo4j（图存储）。

表设计：
- atoms: MemoryAtom 持久化
- edges: Edge 持久化
- episodes: Episode 持久化
"""

import sqlite3
import json
import re
from typing import Optional
from datetime import datetime

from vibe_memory.models.memory_atom import (
    MemoryAtom, Edge, Episode,
    EdgeLabel, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle, DEFAULT_TENANT,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS atoms (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    content TEXT NOT NULL,
    summary TEXT DEFAULT '',
    type TEXT DEFAULT 'session',
    tags TEXT DEFAULT '[]',
    scope TEXT DEFAULT '{}',
    lifecycle TEXT DEFAULT 'active',
    weight REAL DEFAULT 1.0,
    decay_rate REAL DEFAULT 0.95,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    adopted_count INTEGER DEFAULT 0,
    ignored_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    source TEXT DEFAULT '',
    confidence REAL DEFAULT 1.0,
    context_before TEXT DEFAULT '',
    context_after TEXT DEFAULT '',
    episode_id TEXT,
    episode_position INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    previous_version_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_atoms_agent ON atoms(agent_id);
CREATE INDEX IF NOT EXISTS idx_atoms_session ON atoms(session_id);
CREATE INDEX IF NOT EXISTS idx_atoms_type ON atoms(type);
CREATE INDEX IF NOT EXISTS idx_atoms_lifecycle ON atoms(lifecycle);
CREATE INDEX IF NOT EXISTS idx_atoms_tenant ON atoms(tenant_id);
CREATE INDEX IF NOT EXISTS idx_atoms_recall_recent
    ON atoms(tenant_id, agent_id, created_at DESC, id, lifecycle);

CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    from_atom_id TEXT NOT NULL,
    to_atom_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    label TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    decay_rate REAL DEFAULT 0.95,
    confidence REAL DEFAULT 0.9,
    source TEXT DEFAULT 'rule',
    created_at TEXT NOT NULL,
    last_accessed TEXT,
    status TEXT DEFAULT 'active',
    cross_partition INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (from_atom_id) REFERENCES atoms(id),
    FOREIGN KEY (to_atom_id) REFERENCES atoms(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_pair ON edges(from_atom_id, to_atom_id);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_atom_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_atom_id);
CREATE INDEX IF NOT EXISTS idx_edges_status ON edges(status);
CREATE INDEX IF NOT EXISTS idx_edges_tenant ON edges(tenant_id);

CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    summary TEXT DEFAULT '',
    topic TEXT DEFAULT '',
    atom_ids TEXT DEFAULT '[]',
    started_at TEXT,
    ended_at TEXT,
    community_id TEXT,
    weight REAL DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT
);

CREATE INDEX IF NOT EXISTS idx_episodes_agent ON episodes(agent_id);
CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id);
CREATE INDEX IF NOT EXISTS idx_episodes_tenant ON episodes(tenant_id);
"""


FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS atoms_fts USING fts5(
    content,
    summary,
    content='atoms',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS atoms_fts_insert AFTER INSERT ON atoms BEGIN
    INSERT INTO atoms_fts(rowid, content, summary)
    VALUES (new.rowid, new.content, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS atoms_fts_delete AFTER DELETE ON atoms BEGIN
    INSERT INTO atoms_fts(atoms_fts, rowid, content, summary)
    VALUES ('delete', old.rowid, old.content, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS atoms_fts_update AFTER UPDATE OF content, summary ON atoms BEGIN
    INSERT INTO atoms_fts(atoms_fts, rowid, content, summary)
    VALUES ('delete', old.rowid, old.content, old.summary);
    INSERT INTO atoms_fts(rowid, content, summary)
    VALUES (new.rowid, new.content, new.summary);
END;
"""


class VibeStorage:
    """VibeMemory SQLite 存储（多租户，M3）"""

    def __init__(self, db_path: str = ":memory:", tenant_id: str = DEFAULT_TENANT,
                 journal_mode: Optional[str] = None):
        if journal_mode not in (None, "delete", "wal"):
            raise ValueError("journal_mode must be None, 'delete', or 'wal'")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        if journal_mode is not None:
            try:
                actual = self.conn.execute(f"PRAGMA journal_mode={journal_mode}").fetchone()[0]
                if actual != journal_mode:
                    raise ValueError(f"Cannot enable journal_mode={journal_mode}: SQLite returned {actual}")
            except Exception:
                self.conn.close()
                raise
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(atoms)")}
        if "scope" not in columns:
            self.conn.execute("ALTER TABLE atoms ADD COLUMN scope TEXT DEFAULT '{}'")
        self.conn.commit()
        self._fts_enabled = self._initialize_fts()
        self._trigram_enabled = self._initialize_trigram()
        self.tenant_id = tenant_id

    def _initialize_fts(self) -> bool:
        existed = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'atoms_fts'"
        ).fetchone()
        try:
            self.conn.executescript(FTS_SCHEMA)
            if not existed:
                self.conn.execute("INSERT INTO atoms_fts(atoms_fts) VALUES ('rebuild')")
            self.conn.commit()
            return True
        except sqlite3.OperationalError:
            return False

    def _initialize_trigram(self) -> bool:
        """Native trigram index; older SQLite builds keep the LIKE fallback."""
        existed = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'atoms_trigram'"
        ).fetchone()
        # Same external-content schema and native SQL triggers as unicode61.
        schema = FTS_SCHEMA.replace('atoms_fts', 'atoms_trigram').replace(
            "tokenize='unicode61'", "tokenize='trigram'"
        )
        try:
            self.conn.executescript(schema)
            if not existed:
                self.conn.execute("INSERT INTO atoms_trigram(atoms_trigram) VALUES ('rebuild')")
            self.conn.commit()
            return True
        except sqlite3.OperationalError:
            return False

    # ── Atom CRUD ──

    def insert_atom(self, atom: MemoryAtom) -> None:
        self.conn.execute(
            """INSERT INTO atoms (
                id, agent_id, session_id, tenant_id, content, summary, type, tags, scope,
                lifecycle, weight, decay_rate, access_count, last_accessed,
                adopted_count, ignored_count, created_at, source, confidence,
                context_before, context_after, episode_id, episode_position,
                version, previous_version_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                atom.id, atom.agent_id, atom.session_id, atom.tenant_id,
                atom.content, atom.summary,
                atom.type.value, json.dumps(atom.tags), json.dumps(atom.scope), atom.lifecycle.value,
                atom.weight, atom.decay_rate, atom.access_count,
                atom.last_accessed.isoformat() if atom.last_accessed else None,
                atom.adopted_count, atom.ignored_count,
                atom.created_at.isoformat(), atom.source, atom.confidence,
                atom.context_before, atom.context_after,
                atom.episode_id, atom.episode_position,
                atom.version, atom.previous_version_id,
            ),
        )
        self.conn.commit()

    def get_atom(self, atom_id: str) -> Optional[MemoryAtom]:
        row = self.conn.execute(
            "SELECT * FROM atoms WHERE id = ?", (atom_id,)
        ).fetchone()
        return self._row_to_atom(row) if row else None

    def get_atoms_by_session(self, session_id: str) -> list[MemoryAtom]:
        rows = self.conn.execute(
            "SELECT * FROM atoms WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_atom(r) for r in rows]

    def get_atoms_by_agent(self, agent_id: str, tenant_id: Optional[str] = None) -> list[MemoryAtom]:
        tid = tenant_id or self.tenant_id
        rows = self.conn.execute(
            "SELECT * FROM atoms WHERE agent_id = ? AND tenant_id = ? ORDER BY created_at",
            (agent_id, tid),
        ).fetchall()
        return [self._row_to_atom(r) for r in rows]

    def get_recall_candidates(
        self,
        agent_id: str,
        query: str,
        limit: int,
        tenant_id: Optional[str] = None,
        graph_seed_limit: int = 0,
        graph_neighbor_limit: Optional[int] = None,
        graph_hops: int = 1,
    ) -> list[MemoryAtom]:
        """Return bounded candidates; expand at most two causal hops.

        Each hop materializes at most 2 * limit edges and retains limit
        frontier nodes. SQL scanning/sorting time is not bounded by this cap.
        """
        if limit <= 0:
            return []

        tid = tenant_id or self.tenant_id
        default_neighbor_limit = min(limit // 5, graph_seed_limit * 4)
        neighbor_limit = (
            default_neighbor_limit
            if graph_neighbor_limit is None
            else min(limit, max(0, graph_neighbor_limit))
        ) if graph_seed_limit > 0 else 0
        terms = list(dict.fromkeys(
            term.lower() for term in re.findall(r"\w+", query) if len(term) > 1
        ))[:32]
        from vibe_memory.retrieval.text_tokens import cjk_bigrams
        chinese_terms = cjk_bigrams(query)
        if chinese_terms:
            terms = list(dict.fromkeys(chinese_terms + terms))[:32]
        chinese_trigrams = list(dict.fromkeys(
            run[i:i + 3]
            for run in re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]+', query)
            for i in range(len(run) - 2)
        ))[:32]
        use_trigram = bool(chinese_trigrams and self._trigram_enabled)
        fts_table = 'atoms_trigram' if use_trigram else 'atoms_fts'
        match_order = (
            f'bm25({fts_table}), {fts_table}.rowid DESC'
            if use_trigram else f'{fts_table}.rowid DESC'
        )
        if use_trigram:
            terms = chinese_trigrams
        if use_trigram or (self._fts_enabled and terms and not chinese_terms):
            quoted_terms = [f'"{term}"' for term in terms]
            match_queries = [" AND ".join(quoted_terms)]
            any_term_query = " OR ".join(quoted_terms)
            if any_term_query != match_queries[0]:
                match_queries.append(any_term_query)

            rows = []
            for match_query in match_queries:
                selected_ids = [row["id"] for row in rows]
                exclude_sql = ""
                exclude_params = []
                if selected_ids:
                    placeholders = ", ".join("?" for _ in selected_ids)
                    exclude_sql = f"AND atoms.id NOT IN ({placeholders})"
                    exclude_params = selected_ids
                rows.extend(self.conn.execute(
                    f"""SELECT atoms.*
                        FROM {fts_table}
                        JOIN atoms ON atoms.rowid = {fts_table}.rowid
                        WHERE {fts_table} MATCH ?
                          AND atoms.tenant_id = ? AND atoms.agent_id = ?
                          AND atoms.lifecycle IN ('active', 'warm')
                          {exclude_sql}
                        ORDER BY {match_order}
                        LIMIT ?""",
                    (
                        match_query,
                        tid,
                        agent_id,
                        *exclude_params,
                        limit - len(rows),
                    ),
                ).fetchall())
                if len(rows) == limit:
                    break

            if len(rows) < limit:
                selected_ids = [row["id"] for row in rows]
                exclude_sql = ""
                exclude_params = []
                if selected_ids:
                    placeholders = ", ".join("?" for _ in selected_ids)
                    exclude_sql = f"AND id NOT IN ({placeholders})"
                    exclude_params = selected_ids
                rows.extend(self.conn.execute(
                    f"""SELECT * FROM atoms
                        WHERE tenant_id = ? AND agent_id = ?
                          AND lifecycle IN ('active', 'warm')
                          {exclude_sql}
                        ORDER BY created_at DESC, id
                        LIMIT ?""",
                    (tid, agent_id, *exclude_params, limit - len(rows)),
                ).fetchall())
        else:
            if terms:
                score_parts = [
                    "CASE WHEN LOWER(content) LIKE ? OR LOWER(summary) LIKE ? THEN 1 ELSE 0 END"
                    for _ in terms
                ]
                score_sql = " + ".join(score_parts)
                match_params = [value for term in terms for value in (f"%{term}%", f"%{term}%")]
            else:
                score_sql = "0"
                match_params = []

            rows = self.conn.execute(
                f"""SELECT *, ({score_sql}) AS match_count
                    FROM atoms
                    WHERE tenant_id = ? AND agent_id = ?
                      AND lifecycle IN ('active', 'warm')
                    ORDER BY match_count DESC, created_at DESC, id
                    LIMIT ?""",
                (*match_params, tid, agent_id, limit),
            ).fetchall()

        if neighbor_limit and graph_hops > 0 and rows:
            seed_ids = [row["id"] for row in rows[:min(graph_seed_limit, limit)]]
            frontier_scores = {atom_id: 1.0 for atom_id in seed_ids}
            visited_ids = set(seed_ids)
            neighbor_scores: dict[str, tuple[float, int]] = {}

            for hop in range(1, min(graph_hops, 2) + 1):
                frontier_ids = list(frontier_scores)
                if not frontier_ids:
                    break
                placeholders = ", ".join("?" for _ in frontier_ids)
                edge_rows = self.conn.execute(
                    f"""SELECT edges.from_atom_id AS source_id,
                                edges.to_atom_id AS atom_id,
                                edges.weight * edges.confidence AS edge_score
                        FROM edges
                        JOIN atoms ON atoms.id = edges.to_atom_id
                        WHERE edges.from_atom_id IN ({placeholders})
                          AND edges.tenant_id = ? AND edges.status = 'active'
                          AND edges.label = ?
                          AND edges.weight * edges.confidence >= 0.05
                          AND atoms.tenant_id = ? AND atoms.agent_id = ?
                          AND atoms.lifecycle IN ('active', 'warm')
                        UNION ALL
                        SELECT edges.to_atom_id AS source_id,
                               edges.from_atom_id AS atom_id,
                               edges.weight * edges.confidence AS edge_score
                        FROM edges
                        JOIN atoms ON atoms.id = edges.from_atom_id
                        WHERE edges.to_atom_id IN ({placeholders})
                          AND edges.tenant_id = ? AND edges.status = 'active'
                          AND edges.label = ?
                          AND edges.weight * edges.confidence >= 0.05
                          AND atoms.tenant_id = ? AND atoms.agent_id = ?
                          AND atoms.lifecycle IN ('active', 'warm')
                        ORDER BY edge_score DESC, atom_id, source_id
                        LIMIT ?""",
                    (
                        *frontier_ids,
                        tid,
                        EdgeLabel.CAUSAL.value,
                        tid,
                        agent_id,
                        *frontier_ids,
                        tid,
                        EdgeLabel.CAUSAL.value,
                        tid,
                        agent_id,
                        2 * limit,
                    ),
                ).fetchall()

                next_scores: dict[str, float] = {}
                for edge_row in edge_rows:
                    atom_id = edge_row["atom_id"]
                    if atom_id in visited_ids:
                        continue
                    score = frontier_scores[edge_row["source_id"]] * edge_row["edge_score"]
                    next_scores[atom_id] = max(next_scores.get(atom_id, 0.0), score)
                next_scores = dict(sorted(
                    next_scores.items(), key=lambda item: (-item[1], item[0])
                )[:limit])
                visited_ids.update(next_scores)
                frontier_scores = next_scores

                for atom_id, score in next_scores.items():
                    previous = neighbor_scores.get(atom_id)
                    if previous is None or score > previous[0]:
                        neighbor_scores[atom_id] = (score, hop)

            if neighbor_scores:
                neighbor_ids = [
                    atom_id
                    for atom_id, _ in sorted(
                        neighbor_scores.items(),
                        key=lambda item: (-item[1][0], item[1][1], item[0]),
                    )[:neighbor_limit]
                ]
                neighbor_placeholders = ", ".join("?" for _ in neighbor_ids)
                fetched_rows = self.conn.execute(
                    f"""SELECT * FROM atoms
                        WHERE id IN ({neighbor_placeholders})
                          AND tenant_id = ? AND agent_id = ?
                          AND lifecycle IN ('active', 'warm')""",
                    (*neighbor_ids, tid, agent_id),
                ).fetchall()
                fetched_by_id = {row["id"]: row for row in fetched_rows}
                graph_rows = [
                    fetched_by_id[atom_id]
                    for atom_id in neighbor_ids
                    if atom_id in fetched_by_id
                ]
                graph_ids = {row["id"] for row in graph_rows}
                lexical_rows = [row for row in rows if row["id"] not in graph_ids]
                rows = lexical_rows[:limit - len(graph_rows)] + graph_rows

        return [self._row_to_atom(row) for row in rows]

    def count_atoms_by_agent(self, agent_id: str, tenant_id: Optional[str] = None) -> int:
        """Count tenant-scoped atoms without hydrating MemoryAtom objects."""
        tid = tenant_id or self.tenant_id
        row = self.conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE tenant_id = ? AND agent_id = ?",
            (tid, agent_id),
        ).fetchone()
        return int(row[0])

    def reinforce_atoms(self, atom_ids: list[str], agent_id: str,
                        tenant_id: Optional[str] = None) -> list[MemoryAtom]:
        """One atomic metadata-only batch; no stale text or counter overwrites."""
        if not atom_ids:
            return []
        placeholders = ','.join('?' for _ in atom_ids)
        scope = (agent_id, self.tenant_id if tenant_id is None else tenant_id, *atom_ids)
        self.conn.execute(
            f"""UPDATE atoms SET weight=MIN(1.0, weight + 0.1),
                access_count=access_count + 1, last_accessed=?
            WHERE agent_id=? AND tenant_id=? AND id IN ({placeholders})
                AND lifecycle IN ('active', 'warm')""",
            (datetime.now().isoformat(), *scope),
        )
        updated = self.conn.execute(
            f"""SELECT * FROM atoms WHERE agent_id=? AND tenant_id=? AND id IN ({placeholders})
                AND lifecycle IN ('active', 'warm')""", scope).fetchall()
        self.conn.commit()
        return [self._row_to_atom(row) for row in updated]

    def update_atom(self, atom: MemoryAtom) -> None:
        self.conn.execute(
            """UPDATE atoms SET
                content=?, summary=?, type=?, tags=?, scope=?, weight=?, decay_rate=?,
                lifecycle=?, access_count=?, last_accessed=?, adopted_count=?,
                ignored_count=?, confidence=?, episode_id=?, episode_position=?,
                version=?
            WHERE id=?""",
            (
                atom.content, atom.summary, atom.type.value,
                json.dumps(atom.tags), json.dumps(atom.scope), atom.weight, atom.decay_rate,
                atom.lifecycle.value, atom.access_count,
                atom.last_accessed.isoformat() if atom.last_accessed else None,
                atom.adopted_count, atom.ignored_count,
                atom.confidence, atom.episode_id, atom.episode_position,
                atom.version, atom.id,
            ),
        )
        self.conn.commit()

    def delete_atom(self, atom_id: str) -> None:
        self.conn.execute("DELETE FROM atoms WHERE id = ?", (atom_id,))
        self.conn.commit()

    # ── Edge CRUD ──

    def insert_edge(self, edge: Edge) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO edges (
                id, from_atom_id, to_atom_id, tenant_id, label, weight, decay_rate,
                confidence, source, created_at, last_accessed, status,
                cross_partition, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                edge.id, edge.from_atom_id, edge.to_atom_id, edge.tenant_id,
                edge.label.value, edge.weight, edge.decay_rate,
                edge.confidence, edge.source.value,
                edge.created_at.isoformat(),
                edge.last_accessed.isoformat() if edge.last_accessed else None,
                edge.status.value, int(edge.cross_partition), edge.version,
            ),
        )
        self.conn.commit()

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        row = self.conn.execute(
            "SELECT * FROM edges WHERE id = ?", (edge_id,)
        ).fetchone()
        return self._row_to_edge(row) if row else None

    def get_outgoing_edges(self, atom_id: str) -> list[Edge]:
        rows = self.conn.execute(
            "SELECT * FROM edges INDEXED BY idx_edges_from WHERE from_atom_id = ? AND status = 'active'",
            (atom_id,),
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_incoming_edges(self, atom_id: str) -> list[Edge]:
        rows = self.conn.execute(
            "SELECT * FROM edges INDEXED BY idx_edges_to WHERE to_atom_id = ? AND status = 'active'",
            (atom_id,),
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_retrieval_edges(self, agent_id: str, tenant_id: Optional[str] = None,
                            atom_ids: Optional[list[str]] = None) -> list[Edge]:
        """Read live scoped edges, optionally only those incident to supplied atoms."""
        tid = tenant_id or self.tenant_id
        if atom_ids is not None and not atom_ids:
            return []
        edge_source = "edges e"
        endpoint_join = "JOIN"
        params = (tid, tid, tid, agent_id, agent_id)
        if atom_ids is not None:
            # Start with indexed incident edges, not a cross product of live atoms.
            endpoint_join = "CROSS JOIN"
            placeholders = ",".join("?" for _ in atom_ids)
            edge_source = f"""(
                SELECT * FROM edges INDEXED BY idx_edges_from WHERE from_atom_id IN ({placeholders})
                UNION SELECT * FROM edges INDEXED BY idx_edges_to WHERE to_atom_id IN ({placeholders})) e"""
            params = tuple(atom_ids) + tuple(atom_ids) + params
        rows = self.conn.execute(
            f"""SELECT e.* FROM {edge_source}
               {endpoint_join} atoms src ON src.id = e.from_atom_id
               {endpoint_join} atoms dst ON dst.id = e.to_atom_id
               WHERE e.status = 'active' AND e.tenant_id = ?
                 AND src.tenant_id = ? AND dst.tenant_id = ?
                 AND src.agent_id = ? AND dst.agent_id = ?
                 AND src.lifecycle IN ('active', 'warm')
                 AND dst.lifecycle IN ('active', 'warm')""",
            params,
        ).fetchall()
        return [self._row_to_edge(row) for row in rows]

    def get_all_edges(self) -> list[Edge]:
        rows = self.conn.execute(
            "SELECT * FROM edges WHERE status = 'active'"
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_all_edges_raw(self) -> list[Edge]:
        """获取所有边（含 stale/pending），用于 GC 稀疏化"""
        rows = self.conn.execute("SELECT * FROM edges").fetchall()
        return [self._row_to_edge(r) for r in rows]

    def update_edge(self, edge: Edge) -> None:
        self.conn.execute(
            """UPDATE edges SET
                weight=?, decay_rate=?, confidence=?, status=?,
                last_accessed=?, version=?
            WHERE id=?""",
            (
                edge.weight, edge.decay_rate, edge.confidence,
                edge.status.value,
                edge.last_accessed.isoformat() if edge.last_accessed else None,
                edge.version, edge.id,
            ),
        )
        self.conn.commit()

    def get_pending_edges(self) -> list[Edge]:
        """获取待复核的降级边（Bug 5 异步队列）"""
        rows = self.conn.execute(
            "SELECT * FROM edges WHERE status = 'pending_review'"
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_edges_between(self, atom_a_id: str, atom_b_id: str) -> list[Edge]:
        rows = self.conn.execute(
            """SELECT * FROM edges WHERE
                (from_atom_id = ? AND to_atom_id = ?)
                OR (from_atom_id = ? AND to_atom_id = ?)""",
            (atom_a_id, atom_b_id, atom_b_id, atom_a_id),
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    # ── Episode CRUD ──

    def insert_episode(self, episode: Episode) -> None:
        self.conn.execute(
            """INSERT INTO episodes (
                id, agent_id, session_id, tenant_id, summary, topic, atom_ids,
                started_at, ended_at, community_id, weight, access_count, last_accessed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                episode.id, episode.agent_id, episode.session_id, episode.tenant_id,
                episode.summary, episode.topic, json.dumps(episode.atom_ids),
                episode.started_at.isoformat() if episode.started_at else None,
                episode.ended_at.isoformat() if episode.ended_at else None,
                episode.community_id, episode.weight, episode.access_count,
                episode.last_accessed.isoformat() if episode.last_accessed else None,
            ),
        )
        self.conn.commit()

    def get_episodes_by_session(self, session_id: str) -> list[Episode]:
        rows = self.conn.execute(
            "SELECT * FROM episodes WHERE session_id = ? ORDER BY started_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_episode(r) for r in rows]

    # ── Row → Object ──

    def _row_to_atom(self, row: sqlite3.Row) -> MemoryAtom:
        return MemoryAtom(
            id=row["id"],
            agent_id=row["agent_id"],
            session_id=row["session_id"],
            tenant_id=row["tenant_id"] if "tenant_id" in row.keys() else DEFAULT_TENANT,
            content=row["content"],
            summary=row["summary"],
            type=GraphPartition(row["type"]),
            tags=json.loads(row["tags"]),
            scope=json.loads(row["scope"]) if "scope" in row.keys() else {},
            lifecycle=Lifecycle(row["lifecycle"]),
            weight=row["weight"],
            decay_rate=row["decay_rate"],
            access_count=row["access_count"],
            last_accessed=datetime.fromisoformat(row["last_accessed"]) if row["last_accessed"] else None,
            adopted_count=row["adopted_count"],
            ignored_count=row["ignored_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            source=row["source"],
            confidence=row["confidence"],
            context_before=row["context_before"],
            context_after=row["context_after"],
            episode_id=row["episode_id"],
            episode_position=row["episode_position"],
            version=row["version"],
            previous_version_id=row["previous_version_id"],
        )

    def _row_to_edge(self, row: sqlite3.Row) -> Edge:
        return Edge(
            id=row["id"],
            from_atom_id=row["from_atom_id"],
            to_atom_id=row["to_atom_id"],
            tenant_id=row["tenant_id"] if "tenant_id" in row.keys() else DEFAULT_TENANT,
            label=EdgeLabel(row["label"]),
            weight=row["weight"],
            decay_rate=row["decay_rate"],
            confidence=row["confidence"],
            source=EdgeSource(row["source"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed=datetime.fromisoformat(row["last_accessed"]) if row["last_accessed"] else None,
            status=EdgeStatus(row["status"]),
            cross_partition=bool(row["cross_partition"]),
            version=row["version"],
        )

    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        return Episode(
            id=row["id"],
            agent_id=row["agent_id"],
            session_id=row["session_id"],
            tenant_id=row["tenant_id"] if "tenant_id" in row.keys() else DEFAULT_TENANT,
            summary=row["summary"],
            topic=row["topic"],
            atom_ids=json.loads(row["atom_ids"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            community_id=row["community_id"],
            weight=row["weight"],
            access_count=row["access_count"],
            last_accessed=datetime.fromisoformat(row["last_accessed"]) if row["last_accessed"] else None,
        )
