from types import SimpleNamespace

import numpy as np

from vibe_memory import langchain, openai_agents
from vibe_memory.retrieval import fusion


def test_reranker_docs_distinguish_placeholder_and_production_function():
    assert "pass-through" in fusion.Reranker.__doc__
    assert "rerank_by_similarity" in fusion.__doc__
    for name in ("DefaultReranker", "CrossEncoderReranker", "LLMReranker"):
        assert name not in fusion.__doc__


def test_reranker_placeholder_preserves_scores_and_order():
    candidates = [("first", 0.1), ("second", 0.9)]
    provider = SimpleNamespace(encode_query=lambda query: np.ones(2))
    assert fusion.Reranker(provider).rerank("test", candidates, top_k=1) == candidates[:1]
    assert fusion.Reranker().rerank("test", candidates) == candidates


def test_production_similarity_reranker_does_score_candidates():
    result = fusion.rerank_by_similarity(np.array([1., 0.]),
        [("away", 0.1), ("match", 0.1)], np.array([[0., 1.], [1., 0.]]),
        {"away": 0, "match": 1}, top_k=2)
    assert [item[0] for item in result] == ["match", "away"]
    assert result[0][1] > result[1][1]


def test_openai_example_wraps_plain_functions_and_imports_existing_module():
    assert "from vibe_memory.openai_agents import create_vibe_tools" in openai_agents.__doc__
    assert "function_tool(fn)" in openai_agents.__doc__
    assert "plain Python functions" in openai_agents.create_vibe_tools.__doc__


def test_langchain_contract_does_not_claim_base_memory_inheritance():
    assert "not a BaseMemory subclass" in langchain.__doc__
    assert "RunnableLambda" in langchain.__doc__
    assert "Drop-in BaseMemory" not in langchain.__doc__
