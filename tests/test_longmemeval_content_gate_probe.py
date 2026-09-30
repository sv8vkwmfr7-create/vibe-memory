"""Content support is a fixed lexical gate, not factual validation."""

from experiments.longmemeval_content_gate_probe import content_support
from experiments.longmemeval_lexical_slot_probe import lexical_slot


def test_content_gate_blocks_generic_overlap_accepts_half_and_is_not_truth():
    assert not content_support("What degree did I graduate with?", "What factors did shape national identity?")["allowed"]
    assert not content_support("the and with", "the and with")["allowed"]
    assert content_support("battery phone", "phone charger")["allowed"]
    ids = ["a", "b", "c", "d", "gold"]
    # Same-topic wrong facts still pass, and the replacement really executes.
    support = content_support("battery phone", "phone battery advice for someone else")
    assert support["allowed"]
    assert lexical_slot(ids, [("wrong-fact", 1.0)]) == ["a", "b", "c", "d", "wrong-fact"]
