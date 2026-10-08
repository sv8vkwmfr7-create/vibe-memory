"""Private, whole-file administrator preview; never initialize or repair a database."""

from pathlib import Path
from datetime import datetime
import sqlite3
import argparse
import json
import sys


def preview_history(path: str | Path) -> dict:
    """Report historical orphan edge IDs from an existing read-only snapshot."""
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('BEGIN')
        orphan_edges = {'missing_source': [], 'missing_target': [], 'both_missing': []}
        rows = connection.execute('''
            SELECT e.id, source.id, target.id
            FROM edges AS e
            LEFT JOIN atoms AS source ON source.id = e.from_atom_id
            LEFT JOIN atoms AS target ON target.id = e.to_atom_id
            WHERE source.id IS NULL OR target.id IS NULL
            ORDER BY e.id
        ''')
        for edge_id, source, target in rows:
            category = ('both_missing' if source is None and target is None
                        else 'missing_source' if source is None else 'missing_target')
            orphan_edges[category].append(edge_id)
        stale_ids = [row[0] for row in connection.execute(
            "SELECT id FROM edges WHERE status = 'stale' ORDER BY id")]
        unknown_timezone = {}
        invalid_timestamps = {}
        for table in ('atoms', 'edges'):
            unknown_timezone[table] = {'created_at': [], 'last_accessed': []}
            invalid_timestamps[table] = {'created_at': [], 'last_accessed': []}
            for record_id, created, accessed in connection.execute(
                f'SELECT id, created_at, last_accessed FROM {table} ORDER BY id'
            ):
                for field, value in (('created_at', created), ('last_accessed', accessed)):
                    if value is None:
                        continue
                    try:
                        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except (ValueError, TypeError, AttributeError):
                        invalid_timestamps[table][field].append(record_id)
                    else:
                        if timestamp.utcoffset() is None:
                            unknown_timezone[table][field].append(record_id)
        return {'scope': 'whole_database_admin', 'orphan_edges': orphan_edges,
                'stale_edges': {'ids': stale_ids, 'transition_time': 'unknown'},
                'unknown_timezone': unknown_timezone,
                'invalid_timestamps': invalid_timestamps}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only private history audit (whole database).')
    parser.add_argument('database', type=Path)
    args = parser.parse_args()
    try:
        report = preview_history(args.database)
    except sqlite3.Error:
        print('Cannot audit: database unavailable or schema unsupported. No repair performed.',
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
