"""Caller-asserted relation review, through public SDK/storage only."""
from dataclasses import replace
import json
import uuid

import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import Edge, EdgeLabel, EdgeSource, EdgeStatus, GraphPartition, Lifecycle


@pytest.fixture
def memory(tmp_path):
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as memory:
        yield memory


def pair(memory):
    first = memory.store("Order timeout was investigated.", session_id="first",
                         auto_build_edges=False)
    second = memory.store("Order timeout needs another investigation.", session_id="second",
                          auto_build_edges=False)
    return first, second


@pytest.mark.parametrize("decision", ["reject", "uncertain"])
def test_nonaccepting_review_is_read_only(memory, decision):
    first, second = pair(memory)
    before = memory.history("first") + memory.history("second")
    review = memory.prepare_relation_review(first.id, second.id)
    assert review["from"]["content"] == first.content
    assert review["to"]["content"] == second.content
    result = memory.apply_relation_review(review["review_id"], decision=decision)
    assert result["applied"] is False
    assert result["semantic_verified"] is False
    assert result["decision_origin"] == "caller_assertion"
    assert memory.storage.get_all_edges_raw() == []
    assert memory.history("first") + memory.history("second") == before


def test_accept_creates_only_similar_and_replay_never_writes(memory):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    result = memory.apply_relation_review(review["review_id"], decision="accept",
                                          from_quote="Order timeout", to_quote="Order timeout")
    assert result["applied"] is True
    assert result["semantic_verified"] is False
    assert result["decision_origin"] == "caller_assertion"
    edges = memory.storage.get_all_edges_raw()
    assert len(edges) == 1
    edge = edges[0]
    assert (edge.from_atom_id, edge.to_atom_id) == (first.id, second.id)
    assert (edge.label, edge.source, edge.status) == (EdgeLabel.SIMILAR, EdgeSource.RULE, EdgeStatus.ACTIVE)
    assert result["edge_id"] == edge.id
    assert memory.apply_relation_review(review["review_id"], decision="accept",
                                        from_quote="Order timeout", to_quote="Order timeout")["applied"] is False
    assert memory.storage.get_all_edges_raw() == edges


@pytest.mark.parametrize("quote", [None, "", "   ", "not in either record", 1])
@pytest.mark.parametrize("side", ["from_quote", "to_quote"])
def test_invalid_quotes_leave_review_pending(memory, quote, side):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    quotes = {"from_quote": "Order timeout", "to_quote": "Order timeout", side: quote}
    with pytest.raises(ValueError, match="quote"):
        memory.apply_relation_review(review["review_id"], decision="accept", **quotes)
    assert memory.storage.get_all_edges_raw() == []
    assert memory.apply_relation_review(review["review_id"], decision="accept",
                                        from_quote="Order timeout", to_quote="Order timeout")["applied"] is True


@pytest.mark.parametrize("status", list(EdgeStatus))
def test_review_preserves_existing_directed_relation(memory, tmp_path, status):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as other:
        edge = other.link(first.id, second.id, label=EdgeLabel.CAUSAL,
                          confidence=0.93, source=EdgeSource.LEARNER)
        edge.status = status
        edge.weight = 0.41
        other.storage.insert_edge(edge)
    assert memory.apply_relation_review(review["review_id"], decision="accept",
                                        from_quote="Order timeout", to_quote="Order timeout")["applied"] is False
    assert memory.storage.get_all_edges_raw() == [edge]


@pytest.mark.parametrize("field,value", [
    ("content", "Order timeout has a different conclusion."),
    ("summary", "Different conclusion"), ("tags", ["changed"]),
    ("scope", {"environment": "test"}), ("type", GraphPartition.DOCUMENT),
    ("context_before", "Earlier evidence"), ("context_after", "Later evidence"),
    ("version", 2), ("session_id", "replacement-session"),
    ("agent_id", "another-agent"), ("tenant_id", "another-tenant"),
    ("lifecycle", Lifecycle.ARCHIVED),
])
@pytest.mark.parametrize("endpoint", [0, 1])
def test_second_connection_semantic_changes_reject_stale_review(memory, tmp_path, field, value, endpoint):
    atoms = pair(memory)
    review = memory.prepare_relation_review(*(atom.id for atom in atoms))
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as other:
        atom = other.storage.get_atom(atoms[endpoint].id)
        # Public update_atom does not persist context/ownership/session metadata.
        # Replacing via public delete/insert exercises those changes without SQL.
        other.storage.delete_atom(atom.id)
        other.storage.insert_atom(replace(atom, **{field: value}))
        assert getattr(other.storage.get_atom(atom.id), field) == value
        assert memory.apply_relation_review(review["review_id"], decision="accept",
                                            from_quote="Order timeout", to_quote="Order timeout")["applied"] is False
        assert other.storage.get_all_edges_raw() == []


@pytest.mark.parametrize("endpoint", [0, 1])
def test_second_connection_delete_rejects_review(memory, tmp_path, endpoint):
    atoms = pair(memory)
    review = memory.prepare_relation_review(*(atom.id for atom in atoms))
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as other:
        other.forget(atoms[endpoint].id)
        assert memory.apply_relation_review(review["review_id"], decision="accept",
                                            from_quote="Order timeout", to_quote="Order timeout")["applied"] is False
        assert other.storage.get_all_edges_raw() == []


def test_returned_export_cannot_rewrite_retained_evidence(memory):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    review["from"]["content"] = "Forged body"
    review["from"]["tags"].append("Forged tag")
    review["to"]["scope"]["environment"] = "Forged scope"
    with pytest.raises(ValueError, match="quote"):
        memory.apply_relation_review(review["review_id"], decision="accept",
                                     from_quote="Forged body", to_quote="Order timeout")
    assert memory.apply_relation_review(review["review_id"], decision="accept",
                                        from_quote="Order timeout", to_quote="Order timeout")["applied"] is True


def test_current_nonsemantic_counters_are_not_overwritten(memory):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    atom = memory.storage.get_atom(first.id)
    atom.reinforce()
    atom.learn_from_feedback(True)
    memory.storage.update_atom(atom)
    assert memory.apply_relation_review(review["review_id"], decision="accept",
                                        from_quote="Order timeout", to_quote="Order timeout")["applied"] is True
    assert memory.storage.get_atom(first.id) == atom


@pytest.mark.parametrize("decision", ["merge", "causal", "", None, []])
def test_invalid_decision_does_not_consume_review(memory, decision):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    with pytest.raises(ValueError, match="decision"):
        memory.apply_relation_review(review["review_id"], decision=decision)
    assert memory.storage.get_all_edges_raw() == []
    assert memory.apply_relation_review(review["review_id"], decision="reject")["status"] == "reject"


def test_prepare_rejects_inexact_same_record_and_same_session(memory):
    first, second = pair(memory)
    same_session = memory.store("A second record in the first session.", session_id="first",
                                auto_build_edges=False)
    for from_id, to_id in [(first.id, first.id), (first.id[:8], second.id),
                           (first.id, second.id[:8]), (first.id, same_session.id),
                           (None, second.id), (first.id, [])]:
        with pytest.raises(ValueError):
            memory.prepare_relation_review(from_id, to_id)
    assert memory.storage.get_all_edges_raw() == []


@pytest.mark.parametrize("owner", [{"agent_id": "other"}, {"tenant_id": "other"}])
def test_prepare_rejects_foreign_owners(memory, tmp_path, owner):
    first, second = pair(memory)
    args = dict(agent_id="review-agent", db_path=str(tmp_path / "review.db"), embedding_backend="tfidf")
    args.update(owner)
    with VibeMemory(**args) as foreign:
        for ids in [(first.id, second.id), (second.id, first.id)]:
            with pytest.raises(ValueError):
                foreign.prepare_relation_review(*ids)
        assert foreign.storage.get_all_edges_raw() == []


def test_pending_limit_refuses_without_evicting_and_consumption_frees_slot(memory):
    first, second = pair(memory)
    reviews = [memory.prepare_relation_review(first.id, second.id) for _ in range(32)]
    with pytest.raises(ValueError, match="32"):
        memory.prepare_relation_review(first.id, second.id)
    assert memory.apply_relation_review(reviews[0]["review_id"], decision="reject")["status"] == "reject"
    replacement = memory.prepare_relation_review(first.id, second.id)
    assert len({review["review_id"] for review in reviews} | {replacement["review_id"]}) == 33
    for review in reviews[1:] + [replacement]:
        assert memory.apply_relation_review(review["review_id"], decision="uncertain")["status"] == "uncertain"
    assert memory.storage.get_all_edges_raw() == []


def test_full_payload_character_budget_no_truncation_or_pending_eviction(memory):
    first, second = pair(memory)
    old = memory.prepare_relation_review(first.id, second.id)
    large = memory.store("远" * 20000, session_id="large", auto_build_edges=False)
    with pytest.raises(ValueError, match="20000"):
        memory.prepare_relation_review(first.id, large.id)
    assert memory.storage.get_atom(large.id).content == "远" * 20000
    assert memory.apply_relation_review(old["review_id"], decision="reject")["status"] == "reject"
    moderate = memory.store("近" * 3000, session_id="moderate", auto_build_edges=False)
    review = memory.prepare_relation_review(first.id, moderate.id)
    assert review["to"]["content"] == moderate.content
    assert len(json.dumps(review, ensure_ascii=False)) <= 20000


def test_other_instance_closed_and_restart_cannot_submit_old_review(memory, tmp_path):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as other:
        assert other.apply_relation_review(review["review_id"], decision="accept",
                                           from_quote="Order timeout", to_quote="Order timeout")["applied"] is False
    memory.close()
    memory.close()
    with pytest.raises(RuntimeError, match="closed"):
        memory.apply_relation_review(review["review_id"], decision="reject")
    with pytest.raises(RuntimeError, match="closed"):
        memory.prepare_relation_review(first.id, second.id)
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as restarted:
        assert restarted.apply_relation_review(review["review_id"], decision="reject")["applied"] is False
        assert restarted.storage.get_atom(first.id).content == first.content
        assert restarted.storage.get_all_edges_raw() == []


@pytest.mark.parametrize("field", ["context_before", "context_after"])
@pytest.mark.parametrize("preserve_existing", [False, True])
def test_atomic_storage_rejects_context_changes(memory, tmp_path, field, preserve_existing):
    first, second = pair(memory)
    expected = [memory.storage.get_atom(atom.id) for atom in (first, second)]
    edge = Edge(id=str(uuid.uuid4()), from_atom_id=first.id, to_atom_id=second.id,
                label=EdgeLabel.SIMILAR)
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as other:
        other.storage.delete_atom(first.id)
        other.storage.insert_atom(replace(expected[0], **{field: "Changed context"}))
        assert getattr(memory.storage.get_atom(first.id), field) == "Changed context"
        assert memory.storage.insert_edge_if_current(edge, *expected, preserve_existing=preserve_existing) is False
        assert memory.storage.get_all_edges_raw() == []


def test_atomic_storage_default_and_explicit_link_keep_replacement_compatibility(memory):
    first, second = pair(memory)
    original = memory.link(first.id, second.id, label=EdgeLabel.CAUSAL)
    expected = [memory.storage.get_atom(atom.id) for atom in (first, second)]
    replacement = replace(original, id=str(uuid.uuid4()), label=EdgeLabel.SIMILAR)
    assert memory.storage.insert_edge_if_current(replacement, *expected) is True
    assert memory.storage.get_all_edges_raw() == [replacement]
    assert memory.storage.insert_edge_if_current(original, *expected, preserve_existing=True) is False
    assert memory.storage.get_all_edges_raw() == [replacement]
    explicit = memory.link(first.id, second.id, label=EdgeLabel.REFERENCE)
    assert memory.storage.get_all_edges_raw() == [explicit]


def test_quotes_do_not_claim_semantic_verification(memory):
    first = memory.store("The order service uses retry backoff.", session_id="order", auto_build_edges=False)
    second = memory.store("The garden needs watering.", session_id="garden", auto_build_edges=False)
    review = memory.prepare_relation_review(first.id, second.id)
    result = memory.apply_relation_review(review["review_id"], decision="accept",
                                          from_quote="retry backoff", to_quote="watering")
    # Deliberately unrelated control: caller assertions are not independent truth.
    assert result["applied"] is True
    assert result["semantic_verified"] is False
    assert result["decision_origin"] == "caller_assertion"


@pytest.mark.parametrize("decision", ["reject", "uncertain"])
def test_nonaccepting_review_consumed_and_unknown_ids_never_write(memory, decision):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    assert memory.apply_relation_review(review["review_id"], decision=decision)["status"] == decision
    for review_id in (review["review_id"], str(uuid.uuid4()), review["review_id"][:8]):
        assert memory.apply_relation_review(review_id, decision="accept",
                                            from_quote="Order timeout", to_quote="Order timeout")["applied"] is False
    assert memory.storage.get_all_edges_raw() == []


def test_payload_exact_character_boundary_and_context_export(memory):
    first, second = pair(memory)
    initial = memory.prepare_relation_review(first.id, second.id)
    overhead = len(json.dumps(initial, ensure_ascii=False))
    memory.apply_relation_review(initial["review_id"], decision="reject")
    atom = memory.storage.get_atom(first.id)
    memory.storage.delete_atom(first.id)
    memory.storage.insert_atom(replace(atom, context_before="界" * (20000 - overhead)))
    review = memory.prepare_relation_review(first.id, second.id)
    assert len(json.dumps(review, ensure_ascii=False)) == 20000
    assert review["from"]["context_before"] == "界" * (20000 - overhead)
    memory.storage.delete_atom(first.id)
    memory.storage.insert_atom(replace(atom, context_before="界" * (20001 - overhead)))
    with pytest.raises(ValueError, match="20000"):
        memory.prepare_relation_review(first.id, second.id)
    assert memory.apply_relation_review(review["review_id"], decision="reject")["status"] == "reject"


def test_public_sdk_update_invalidates_retained_review(memory, tmp_path):
    first, second = pair(memory)
    review = memory.prepare_relation_review(first.id, second.id)
    with VibeMemory("review-agent", db_path=str(tmp_path / "review.db"),
                    embedding_backend="tfidf") as other:
        other.update(first.id, content="Order timeout requires new evidence.")
        assert memory.storage.get_atom(first.id).content == "Order timeout requires new evidence."
    assert memory.apply_relation_review(review["review_id"], decision="accept",
                                        from_quote="Order timeout", to_quote="Order timeout")["applied"] is False
    assert memory.storage.get_all_edges_raw() == []
