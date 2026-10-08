import gc
import tracemalloc
from datetime import datetime, timedelta

import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import MemoryAtom


def test_text_index_rebuild_stays_within_fixture_retained_allocation_budget():
    memory = VibeMemory(agent_id='index-budget', embedding_backend='tfidf')
    try:
        for index in range(10000):
            text = ('quasar incident resolution' if index == 0 else
                    f'wallpaper maintenance record {index} desktop theme background color')
            memory.storage.insert_atom(MemoryAtom(
                id=f'atom-{index:05}', agent_id='index-budget', session_id='synthetic',
                content=text, summary=text,
                created_at=datetime(2026, 9, 1) + timedelta(seconds=index)))
        memory.recall('quasar incident resolution', mode='precision', top_k=5)
        memory.update('atom-00000', content='nebula incident resolution')

        tracemalloc.start()
        try:
            result = memory.recall('nebula incident resolution', mode='precision', top_k=5)
            assert result['failures'] == []
            assert [(atom.id, atom.content) for atom in result['atoms']] == [
                ('atom-00000', 'nebula incident resolution')]
            del result
            gc.collect()
            retained, _ = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        # New retained Python allocation on this fixture, not RSS or a global cap.
        assert retained < 16 * 1024 * 1024, retained
    finally:
        memory.storage.conn.close()


@pytest.mark.parametrize('mode', ['precision', 'recall'])
@pytest.mark.parametrize('external_writer', [False, True])
def test_recall_tracks_evidence_moving_between_record_boundaries(tmp_path, mode, external_writer):
    path = str(tmp_path / 'boundaries.db')
    reader = VibeMemory(agent_id='boundary-check', db_path=path, embedding_backend='tfidf')
    writer = (VibeMemory(agent_id='boundary-check', db_path=path, embedding_backend='tfidf')
              if external_writer else reader)
    try:
        for atom_id, content, date in [('a', '火星 "alpha" beta', 1), ('b', '\n gamma', 2)]:
            writer.storage.insert_atom(MemoryAtom(
                id=atom_id, agent_id='boundary-check', session_id='synthetic',
                content=content, summary=content, created_at=datetime(2026, 9, date)))
        first = reader.recall('beta', mode=mode, top_k=1)
        assert first['failures'] == []
        assert [atom.id for atom in first['atoms']] == ['a']
        # The corpus has identical concatenated bytes, but different per-record evidence.
        writer.update('a', content='火星 "alpha" ')
        writer.update('b', content='beta\n gamma')
        second = reader.recall('beta', mode=mode, top_k=1)
        assert second['failures'] == []
        assert [(atom.id, atom.content) for atom in second['atoms']] == [('b', 'beta\n gamma')]
    finally:
        if writer is not reader:
            writer.storage.conn.close()
        reader.storage.conn.close()
