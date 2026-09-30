"""Same-session predecessor context must not leak across sessions or ahead in time."""

from experiments.locomo_adjacent_context_probe import write_texts


def test_previous_turn_stays_in_session_and_follows_current_text():
    atoms = [
        {"id": "a", "session_id": "s1", "content": "A: first"},
        {"id": "b", "session_id": "s1", "content": "B: second"},
        {"id": "c", "session_id": "s2", "content": "A: third"},
    ]
    assert write_texts(atoms, False) == [("A: first", None), ("B: second", None),
                                         ("A: third", None)]
    assert write_texts(atoms, True) == [("A: first", None),
                                        ("B: second\nPrevious turn: A: first", "a"),
                                        ("A: third", None)]
