"""Minimal LongMemEval adapter guard."""

import json
import os

import pytest

from experiments import longmemeval_tfidf_baseline as baseline
from experiments.longmemeval_tfidf_baseline import prepare


def test_prepare_keeps_turn_labels_out_of_memory_text():
    case = {"question_id": "q", "haystack_session_ids": ["s1"],
            "haystack_dates": ["2023/05/20 (Sat) 02:21"],
            "haystack_sessions": [[{"role": "user", "content": "A fact", "has_answer": True},
                                   {"role": "assistant", "content": "Okay"}]]}
    atoms, evidence = prepare(case)
    assert evidence == {"q:0:0"}
    assert [(atom.id, atom.session_id, atom.content) for atom in atoms] == [
        ("q:0:0", "s1", "user: A fact"), ("q:0:1", "s1", "assistant: Okay")]
    assert atoms[0].created_at < atoms[1].created_at


def test_prepare_rejects_unlabeled_non_abstention():
    case = {"question_id": "q", "haystack_session_ids": ["s1"],
            "haystack_dates": ["2023/05/20 (Sat) 02:21"],
            "haystack_sessions": [[{"role": "user", "content": "A fact"}]]}
    with pytest.raises(ValueError, match="no turn-level evidence"):
        prepare(case)


def test_checkpoint_retries_transient_windows_replace_lock(tmp_path, monkeypatch):
    target = tmp_path / "progress.json"
    target.write_text("old", encoding="utf-8")
    original = os.replace
    attempts = []

    def briefly_locked(source, destination):
        attempts.append((source, destination))
        if len(attempts) == 1:
            raise PermissionError(5, "target briefly locked")
        original(source, destination)

    monkeypatch.setattr(baseline.os, "replace", briefly_locked)
    baseline.save_checkpoint(target, {"rows": [{"id": "q"}]})
    assert len(attempts) == 2
    assert json.loads(target.read_text(encoding="utf-8")) == {"rows": [{"id": "q"}]}
