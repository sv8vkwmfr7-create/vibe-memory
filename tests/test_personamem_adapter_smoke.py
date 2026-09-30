"""Query parsing must not execute dataset text or accept answer metadata."""

import pytest

from experiments.personamem_adapter_smoke import parse_query, stage_diagnosis, rank_positions, preceding_texts
from vibe_memory.models.memory_atom import MemoryAtom


def test_personamem_query_literal_parsing_rejects_code_and_wrong_roles():
    assert parse_query("{'role': 'user', 'content': 'Which theme?'}") == "Which theme?"
    for value in ("__import__('os').getcwd()", "{'role': 'assistant', 'content': 'answer'}", "{}", "{'role': 'user', 'content': ''}"):
        with pytest.raises((ValueError, SyntaxError)):
            parse_query(value)


def test_personamem_stage_diagnosis_distinguishes_cutoffs_and_temporal_route():
    stages = {name: [] for name in ("semantic", "bm25", "graph", "temporal", "fused", "final")}
    evidence = {"target"}
    assert stage_diagnosis(evidence, stages)["loss_stage"] == "before_fusion"
    stages["temporal"] = ["target"]
    assert stage_diagnosis(evidence, stages)["loss_stage"] == "fusion_top10"
    stages["fused"] = [f"noise-{i}" for i in range(5)] + ["target"]
    result = stage_diagnosis(evidence, stages)
    assert result["loss_stage"] == "final_rerank"
    assert result["evidence_ranks"]["target"]["fused"] == 6
    assert result["fused_top5_snippet_hit"] is False
    stages["final"] = ["target"]
    assert stage_diagnosis(evidence, stages)["loss_stage"] == "retained"


def test_personamem_full_rank_positions_distinguish_missing_and_zero_score():
    result = rank_positions(["noise", "zero", "target", "absent"], [(0, 0.9), (2, 0.2), (1, 0.0)], {"zero", "target", "absent"})
    assert result["ranked_count"] == 3
    assert result["nearest_positive_snippet_rank"] == 2
    assert result["evidence"]["target"] == {"rank": 2, "score": 0.2, "positive_score": True}
    assert result["evidence"]["zero"] == {"rank": 3, "score": 0.0, "positive_score": False}
    assert result["evidence"]["absent"] == {"rank": None, "score": None, "positive_score": False}


def test_preceding_texts_preserve_original_and_session_boundary():
    atoms = [MemoryAtom(id=str(i), agent_id="test", content=text, summary=text, session_id=session)
             for i, (text, session) in enumerate((("user: first", "a"), ("assistant: second", "a"), ("user: third", "b")))]
    assert preceding_texts(atoms) == ["user: first", "assistant: second\nPrevious turn: user: first", "user: third"]
    assert [atom.content for atom in atoms] == ["user: first", "assistant: second", "user: third"]
