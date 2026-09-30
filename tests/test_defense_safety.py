"""Synthetic-only privacy scanner false-positive and overlap regressions."""
import pytest

from vibe_memory.defense import MemoryDefense, scan_before_store
from vibe_memory import VibeMemory


@pytest.mark.parametrize("content", [
    "commit: " + "abcdef0123456789" * 2 + "abcdef01",
    "timestamp: 1800000000000",
    "order_id: 1234567890123456",
    "trace: prefix13800138000suffix",
])
def test_normal_identifiers_are_not_redacted(content):
    assert MemoryDefense().scan(content) == (content, [])


@pytest.mark.parametrize("content", [
    "token=" + "sk-" + "A" * 40,
    "email: person@example.invalid",
    "phone: 13800138000",
    "电话13800138000请联系",
    "credit_card: 4111111111111111",
    "api_key: " + "B" * 40,
])
def test_supported_secrets_still_redact(content):
    cleaned, violations = MemoryDefense().scan(content)
    assert violations
    assert "[REDACTED:" in cleaned
    assert content != cleaned


def test_overlapping_matches_are_replaced_once_from_original():
    content = "before token=sk-" + "A" * 40 + " after"
    cleaned, violations = MemoryDefense().scan(content)
    assert len(violations) >= 2
    assert cleaned == "before [REDACTED:credential_in_text] after"
    assert all(content[start:end] == item["match"] for item in violations for start, end in [item["position"]])


def test_custom_nested_and_adjacent_matches():
    defense = MemoryDefense(patterns=[("abcdef", "outer"), ("bc", "inner"), ("XYZ", "adjacent")])
    assert defense.scan("abcdefXYZ tail")[0] == "[REDACTED:outer][REDACTED:adjacent] tail"


def test_warn_block_and_exclusion_contract():
    content = "email: person@example.invalid"
    for mode in ("warn", "block"):
        cleaned, violations, blocked = scan_before_store(content, MemoryDefense(mode=mode))
        assert cleaned == content and violations
        assert blocked == (mode == "block")
    assert MemoryDefense(exclude_patterns=["email"]).scan(content) == (content, [])


def test_sdk_persists_clean_overlap_without_damaging_identifier():
    mem = VibeMemory(agent_id="defense-test", db_path=":memory:", embedding_backend="tfidf")
    try:
        content = "timestamp: 1800000000000; token=sk-" + "A" * 40
        atom = mem.store(content, auto_build_edges=False, auto_episode=False)
        assert atom.content == "timestamp: 1800000000000; [REDACTED:credential_in_text]"
        assert mem.storage.get_atom(atom.id).content == atom.content
    finally:
        mem.storage.conn.close()
