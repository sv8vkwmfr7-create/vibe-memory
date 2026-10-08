from datetime import datetime, timezone
import json
import sqlite3
import subprocess
import sys

import pytest

from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel, EdgeStatus
from vibe_memory.storage.sqlite_store import VibeStorage


def test_preview_reports_orphans_without_changing_database(tmp_path):
    from vibe_memory.history_audit import preview_history

    path = tmp_path / 'history.db'
    storage = VibeStorage(str(path))
    try:
        storage.insert_atom(MemoryAtom(id='present', agent_id='owner',
                                      session_id='fixture', content='private text',
                                      summary='private summary'))
        for edge_id, source, target in (
            ('missing-source', 'absent1', 'present'),
            ('missing-target', 'present', 'absent2'),
            ('both-missing', 'absent3', 'absent4'),
            ('valid-self-loop', 'present', 'present'),
        ):
            storage.insert_edge(Edge(id=edge_id, from_atom_id=source,
                                     to_atom_id=target, label=EdgeLabel.CAUSAL))
    finally:
        storage.conn.close()
    before = path.read_bytes()

    report = preview_history(path)

    assert report['scope'] == 'whole_database_admin'
    assert report['orphan_edges'] == {
        'missing_source': ['missing-source'],
        'missing_target': ['missing-target'],
        'both_missing': ['both-missing'],
    }
    assert 'private text' not in str(report)
    assert 'private summary' not in str(report)
    assert path.read_bytes() == before


def test_preview_does_not_create_missing_database(tmp_path):
    from vibe_memory.history_audit import preview_history

    path = tmp_path / 'missing.db'
    with pytest.raises(sqlite3.OperationalError):
        preview_history(path)
    assert not path.exists()


def test_preview_does_not_initialize_unsupported_database(tmp_path):
    from vibe_memory.history_audit import preview_history

    path = tmp_path / 'empty.db'
    sqlite3.connect(path).close()
    before = path.read_bytes()
    with pytest.raises(sqlite3.OperationalError):
        preview_history(path)
    assert path.read_bytes() == before


def test_admin_command_returns_private_preview(tmp_path):
    path = tmp_path / 'history.db'
    storage = VibeStorage(str(path))
    storage.insert_edge(Edge(id='orphan', from_atom_id='missing1',
                             to_atom_id='missing2', label=EdgeLabel.CAUSAL))
    storage.conn.close()
    before = path.read_bytes()

    process = subprocess.run([sys.executable, '-m', 'vibe_memory.history_audit', str(path)],
                             capture_output=True, text=True, timeout=15)

    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report['orphan_edges']['both_missing'] == ['orphan']
    assert path.read_bytes() == before


def test_preview_reads_committed_wal_history_with_writer_open(tmp_path):
    from vibe_memory.history_audit import preview_history

    path = tmp_path / 'history.db'
    storage = VibeStorage(str(path), journal_mode='wal')
    try:
        storage.insert_edge(Edge(id='wal-orphan', from_atom_id='missing1',
                                 to_atom_id='missing2', label=EdgeLabel.CAUSAL))
        assert preview_history(path)['orphan_edges']['both_missing'] == ['wal-orphan']
        assert [edge.id for edge in storage.get_all_edges_raw()] == ['wal-orphan']
    finally:
        storage.conn.close()


def test_admin_command_rejects_missing_database_without_creating_it(tmp_path):
    path = tmp_path / 'missing.db'
    process = subprocess.run([sys.executable, '-m', 'vibe_memory.history_audit', str(path)],
                             capture_output=True, text=True, timeout=15)
    assert process.returncode == 1
    assert process.stdout == ''
    assert 'No repair performed' in process.stderr
    assert not path.exists()


def test_preview_preserves_valid_stale_cross_owner_history_and_unknown_times(tmp_path):
    from vibe_memory.history_audit import preview_history

    path = tmp_path / 'history.db'
    storage = VibeStorage(str(path))
    aware = datetime(2020, 1, 1, tzinfo=timezone.utc)
    try:
        for atom_id, owner, timestamp in (
            ('naive', 'alice', datetime(2020, 1, 1)), ('aware', 'bob', aware),
        ):
            storage.insert_atom(MemoryAtom(id=atom_id, agent_id=owner,
                                          session_id='fixture', content='private',
                                          summary='private', created_at=timestamp))
        storage.insert_edge(Edge(id='stale-cross-owner', from_atom_id='naive',
                                 to_atom_id='aware', label=EdgeLabel.CAUSAL,
                                 status=EdgeStatus.STALE, created_at=aware))
    finally:
        storage.conn.close()
    before = path.read_bytes()

    report = preview_history(path)

    assert all(not ids for ids in report['orphan_edges'].values())
    assert report['stale_edges'] == {
        'ids': ['stale-cross-owner'], 'transition_time': 'unknown',
    }
    assert report['unknown_timezone'] == {
        'atoms': {'created_at': ['naive'], 'last_accessed': []},
        'edges': {'created_at': [], 'last_accessed': []},
    }
    assert path.read_bytes() == before
