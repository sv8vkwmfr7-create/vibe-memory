"""Generic snippet openings must not create false evidence indices."""

import pytest

from experiments.personamem_evidence import evidence_indices


def test_full_unique_role_content_mapping_preserves_original_indices():
    opening = {"role": "user", "content": "Please help"}
    old = {"role": "assistant", "content": "old topic"}
    current = {"role": "assistant", "content": "current topic"}
    system = {"role": "system", "content": "hidden persona"}
    history = [system, opening, old, opening, current]
    assert evidence_indices(history, [opening, current]) == [3, 4]
    for snippet in ([], [opening], [system], [{"role": "assistant", "content": "Please help"}],
                    [{"role": "user", "content": "Please"}], [{"role": "user", "content": []}]):
        with pytest.raises(ValueError):
            evidence_indices(history, snippet)
