import pytest

from vibe_memory import VibeMemory
from vibe_memory.chunking.chunker import should_ingest


@pytest.mark.parametrize("text", [
    "token预算设置为2048", "webhook地址使用内部服务", "book索引按标题排序",
    "已将数据库迁移到新节点", "收到告警后请检查连接池", "继续使用本地模型处理文档",
    "好的方案需要保留版本记录", "OK，部署端口为8080", "OK, got it; use port 8080",
])
def test_meaningful_text_is_not_filtered_by_acknowledgment_substrings(text):
    assert should_ingest(text, None)


@pytest.mark.parametrize("text", ["好的", "收到！", "继续。", "ok", " OK! \n", "OK, got it", "已"])
def test_complete_acknowledgments_remain_filtered(text):
    assert not should_ingest(text, None)


@pytest.mark.parametrize("text", ["OK，但请求失败", "已修正连接参数", "收到error告警"])
def test_error_and_correction_precedence_is_preserved(text):
    assert should_ingest(text, None)


def test_batch_persists_meaningful_text_but_not_acknowledgments():
    memory = VibeMemory(agent_id="filter-test", embedding_backend="tfidf")
    texts = ["token预算设置为2048", "已将数据库迁移到新节点", "收到！", "OK, got it"]
    try:
        stored = memory.store_batch(
            [{"role": "assistant", "content": text} for text in texts], session_id="s")
        assert [atom.content for atom in stored] == texts[:2]
        persisted = memory.storage.get_atoms_by_session("s", agent_id="filter-test")
        assert sorted(atom.content for atom in persisted) == sorted(texts[:2])
        assert memory._store_count == 2
    finally:
        memory.storage.conn.close()
