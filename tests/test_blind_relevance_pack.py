"""Behavior of the reviewer-facing blind relevance-pack CLI."""

import csv
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / 'experiments' / 'blind_relevance_pack.py'


def test_cli_builds_repeatable_label_free_review_pack(tmp_path):
    corpus = tmp_path / 'corpus.json'
    corpus.write_text(json.dumps({
        'atoms': [
            {'id': 'secret-a', 'session_id': 'one', 'content': 'first candidate'},
            {'id': 'secret-b', 'session_id': 'two', 'content': 'second candidate'},
        ],
        'edges': [],
        'queries': [{
            'text': 'which candidate is relevant?',
            'relevant_ids': ['secret-a'],
            'negative_ids': ['secret-b'],
        }],
    }), encoding='utf-8')
    review = tmp_path / 'review.csv'
    manifest = tmp_path / 'manifest.json'
    review_again = tmp_path / 'review-again.csv'
    manifest_again = tmp_path / 'manifest-again.json'

    def run(review_path, manifest_path):
        return subprocess.run([
            sys.executable, str(SCRIPT), '--corpus', str(corpus),
            '--review-csv', str(review_path), '--manifest', str(manifest_path),
            '--seed', 'review-v1',
        ], capture_output=True, text=True, check=False)

    first = run(review, manifest)
    second = run(review_again, manifest_again)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert review.read_bytes() == review_again.read_bytes()
    assert manifest.read_bytes() == manifest_again.read_bytes()

    rows = list(csv.DictReader(review.open(encoding='utf-8-sig', newline='')))
    assert len(rows) == 2
    assert {row['candidate_text'] for row in rows} == {
        'first candidate', 'second candidate'}
    assert all(row['relevance'] == row['harmful'] == row['notes'] == ''
        for row in rows)
    assert 'secret-a' not in review.read_text(encoding='utf-8-sig')
    assert 'relevant_ids' not in review.read_text(encoding='utf-8-sig')

    private = json.loads(manifest.read_text(encoding='utf-8'))
    assert private['source_sha256']
    assert {item['atom_id'] for item in private['candidate_map']} == {
        'secret-a', 'secret-b'}
