"""Automatic merging must not confuse shared categories with duplicate facts."""
import pytest

from vibe_memory import VibeMemory


def test_unrelated_chinese_records_remain_independent_across_sessions():
    memory = VibeMemory(agent_id="merge-evidence", embedding_backend="tfidf")
    pottery = memory.store("陶艺学习大约五周了。", session_id="pottery")
    dinner = memory.store("周末吃了苹果。", session_id="dinner")

    assert memory.storage.get_atom(pottery.id).content == "陶艺学习大约五周了。"
    assert memory.storage.get_atom(dinner.id).content == "周末吃了苹果。"


@pytest.mark.parametrize("first, second", [
    ("已确认，生产重试次数为4次。", "已确认，生产重试次数为7次。"),
    ("2026/08/05 学习陶艺五周了。", "2026/08/20 学习陶艺五周了。"),
])
def test_changed_facts_and_dates_keep_separate_session_history(first, second):
    memory = VibeMemory(agent_id="merge-evidence", embedding_backend="tfidf")
    memory.store(first, session_id="earlier")
    memory.store(second, session_id="later")

    assert [atom.content for atom in memory.history("earlier")] == [first]
    assert [atom.content for atom in memory.history("later")] == [second]


def test_identical_text_can_still_merge_and_keep_existing_relation():
    memory = VibeMemory(agent_id="merge-evidence", embedding_backend="tfidf")
    original = memory.store("陶艺学习大约五周了。", session_id="earlier")
    neighbor = memory.store("完成了一个杯子。", session_id="neighbor",
                            auto_build_edges=False)
    relation = memory.link(original.id, neighbor.id)
    merged = memory.store("陶艺学习大约五周了。", session_id="later")

    assert memory.storage.get_atom(original.id) is None
    assert "陶艺学习大约五周了。" in memory.storage.get_atom(merged.id).content
    assert memory.storage.get_edge(relation.id).from_atom_id == merged.id
    assert memory.storage.get_edge(relation.id).to_atom_id == neighbor.id


def test_identical_text_with_different_scope_is_not_merged():
    memory = VibeMemory(agent_id="merge-evidence", embedding_backend="tfidf")
    production = memory.store("重试次数为4次。", session_id="production",
                              scope={"environment": "production"})
    test = memory.store("重试次数为4次。", session_id="test",
                        scope={"environment": "test"})

    assert memory.storage.get_atom(production.id).scope == {"environment": "production"}
    assert memory.storage.get_atom(test.id).scope == {"environment": "test"}
