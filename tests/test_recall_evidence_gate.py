"""Public SDK evidence boundaries for the TF-IDF baseline."""
import pytest
from datetime import datetime

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel, MemoryAtom


@pytest.mark.parametrize("mode", ["precision", "budget", "recall"])
def test_zero_overlap_query_returns_no_arbitrary_memories(mode):
    memory = VibeMemory(agent_id="evidence-gate", embedding_backend="tfidf")
    memory.store("陶艺学习大约五周了。", session_id="pottery")
    memory.store("周末吃了苹果。", session_id="dinner")

    result = memory.recall("火星轨道卫星", mode=mode, top_k=5)

    assert result["atoms"] == []
    assert result["failures"] == []


@pytest.mark.parametrize("mode", ["precision", "budget", "recall"])
def test_recency_does_not_make_unmatched_content_relevant(mode):
    memory = VibeMemory(agent_id="evidence-gate", embedding_backend="tfidf")
    pottery = MemoryAtom(id="old-pottery", agent_id=memory.agent_id,
                         session_id="pottery", content="陶艺学习大约五周了。",
                         summary="陶艺学习大约五周了。", created_at=datetime(2000, 1, 1))
    memory.storage.insert_atom(pottery)
    memory.store("周末吃了苹果。", session_id="dinner")

    assert memory.recall("火星轨道卫星", mode=mode)["atoms"] == []
    assert [a.id for a in memory.recall("陶艺学习", mode=mode)["atoms"]] == [pottery.id]


@pytest.mark.parametrize("mode", ["precision", "budget", "recall"])
def test_query_anchor_keeps_nonlexical_cause_without_unrelated_padding(mode):
    memory = VibeMemory(agent_id="evidence-gate", embedding_backend="tfidf")
    incident = memory.store("支付服务连接超时。", session_id="incident")
    cause = memory.store("凭据过期。", session_id="cause")
    noise = memory.store("周末吃了苹果。", session_id="dinner")
    memory.link(cause.id, incident.id, label=EdgeLabel.CAUSAL, confidence=1.0)

    result = memory.recall("支付服务连接超时", mode=mode, top_k=5)

    assert {atom.id for atom in result["atoms"]} == {incident.id, cause.id}
    assert noise.id not in {atom.id for atom in result["atoms"]}
