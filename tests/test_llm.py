"""
LLM Module Tests

Verifies:
  1. LLMProvider base class / interface
  2. OpenAIProvider: chat, error handling, retries, timeout
  3. LLMError: proper exception hierarchy
  4. EdgeClassifier: prompt building, JSON parsing, label mapping
  5. EdgeClassifier: classify with mock provider
  6. EdgeClassifier: fallback when LLM fails
  7. EdgeClassifier: merge decision
  8. EdgeClassifier: "none" label handling
  9. EdgeClassifier: stats tracking
  10. create_llm_classify_callback: compatibility
  11. JSON extraction: pure JSON, code block, inline
  12. EdgeClassifier: retry on transient errors
  13. SDK integration: llm_classifier constructor param
  14. SDK integration: stats() includes llm_classifier
  15. SDK integration: flush_index uses LLM classifier
  16. Prompt template: contains context_before/after
  17. Confidence clamping: 0.0-1.0 range
  18. Merge prompt: structure and content
"""

import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from vibe_memory.llm.provider import (
    LLMProvider, OpenAIProvider, LLMError, create_provider,
)
from vibe_memory.llm.edge_classifier import (
    LLMEdgeClassifier,
    create_llm_classify_callback,
    build_classification_messages,
    build_merge_messages,
    _extract_json,
    _parse_label,
    LABEL_MAP,
    CLASSIFICATION_SYSTEM_PROMPT,
    MERGE_SYSTEM_PROMPT,
)
from vibe_memory.models.memory_atom import (
    MemoryAtom, EdgeLabel, Edge, EdgeSource, EdgeStatus,
    GraphPartition, Lifecycle,
)
from vibe_memory.sdk import VibeMemory


# ── Helpers ──

def _make_atom(id: str, content: str, session: str = "s1", tags: list[str] = None,
               context_before: str = "", context_after: str = "") -> MemoryAtom:
    return MemoryAtom(
        id=id, agent_id="agent-1", session_id=session,
        content=content, summary=content[:100],
        tags=tags or ["routine"],
        context_before=context_before,
        context_after=context_after,
    )


class MockProvider(LLMProvider):
    """Mock LLM provider for testing"""

    def __init__(self, responses: list[dict] = None, raise_on: int = None):
        self.responses = responses or []
        self.raise_on = raise_on
        self.call_count = 0
        self.last_messages = None

    @property
    def name(self) -> str:
        return "mock"

    def chat(self, messages, temperature=0.1, max_tokens=512, timeout=30.0):
        self.call_count += 1
        self.last_messages = messages
        if self.raise_on is not None and self.call_count <= self.raise_on:
            raise LLMError("Mock transient error")
        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return {"content": '{"label": "similar", "confidence": 0.5}', "model": "mock", "usage": {}}


# ── 1. LLMProvider base ──

def test_llm_provider_abc():
    """Test: LLMProvider is abstract, can't instantiate"""
    # Verify it has abstract methods
    assert hasattr(LLMProvider, 'chat')
    assert hasattr(LLMProvider, 'name')
    print("[PASS] llm_provider_abc")


def test_llm_error():
    """Test: LLMError is proper exception"""
    err = LLMError("test error")
    assert str(err) == "test error"
    assert isinstance(err, Exception)
    print("[PASS] llm_error")


# ── 2. OpenAIProvider ──

def test_openai_provider_init():
    """Test: OpenAIProvider initializes with defaults"""
    p = OpenAIProvider(api_key="sk-test")
    assert p.api_key == "sk-test"
    assert p.base_url == "https://api.openai.com/v1"
    assert p.model == "gpt-4o-mini"
    assert p.timeout == 30.0
    assert p.max_retries == 2
    assert p.name == "openai:gpt-4o-mini"
    print("[PASS] openai_provider_init")


def test_openai_provider_custom():
    """Test: OpenAIProvider with custom base_url and model"""
    p = OpenAIProvider(
        api_key="sk-test",
        base_url="http://localhost:11434/v1",
        model="llama3.2",
        timeout=60.0,
        max_retries=3,
    )
    assert p.base_url == "http://localhost:11434/v1"
    assert p.model == "llama3.2"
    assert p.name == "openai:llama3.2"
    print("[PASS] openai_provider_custom")


def test_create_provider():
    """Test: create_provider factory"""
    p = create_provider("openai", api_key="sk-test", model="gpt-4o-mini")
    assert isinstance(p, OpenAIProvider)
    assert p.model == "gpt-4o-mini"

    try:
        create_provider("unknown")
        assert False, "Should raise"
    except ValueError:
        pass
    print("[PASS] create_provider")


# ── 3. Prompt Building ──

def test_build_classification_messages():
    """Test: classification prompt structure"""
    a = _make_atom("a1", "Fixed API timeout bug", session="s1", tags=["error", "api"])
    b = _make_atom("b1", "Timeout increased to 60s", session="s2", tags=["error", "config"])

    msgs = build_classification_messages(a, b)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Atom A" in msgs[1]["content"]
    assert "Atom B" in msgs[1]["content"]
    assert "Fixed API timeout bug" in msgs[1]["content"]
    assert "Timeout increased to 60s" in msgs[1]["content"]
    print("[PASS] build_classification_messages")


def test_build_classification_messages_with_context():
    """Test: prompt includes context_before/after"""
    a = _make_atom("a1", "Fixed bug", context_before="User reported error", context_after="Test passed")
    b = _make_atom("b1", "Deployed fix", context_before="CI passed", context_after="Monitoring")

    msgs = build_classification_messages(a, b)
    assert "Context before: User reported error" in msgs[1]["content"]
    assert "Context after: Test passed" in msgs[1]["content"]
    assert "Context before: CI passed" in msgs[1]["content"]
    print("[PASS] build_classification_messages_with_context")


def test_build_merge_messages():
    """Test: merge prompt structure"""
    a = _make_atom("a1", "Config timeout=30s", session="s1", tags=["config"])
    b = _make_atom("b1", "Config timeout=30s confirmed", session="s2", tags=["config"])

    msgs = build_merge_messages(a, b)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "merge" in msgs[0]["content"].lower()
    assert "Config timeout=30s" in msgs[1]["content"]
    print("[PASS] build_merge_messages")


# ── 4. JSON Parsing ──

def test_extract_json_pure():
    """Test: extract pure JSON"""
    result = _extract_json('{"label": "causal", "confidence": 0.9}')
    assert result["label"] == "causal"
    assert result["confidence"] == 0.9
    print("[PASS] extract_json_pure")


def test_extract_json_code_block():
    """Test: extract JSON from ```json code block"""
    result = _extract_json('```json\n{"label": "similar", "confidence": 0.7}\n```')
    assert result["label"] == "similar"
    assert result["confidence"] == 0.7
    print("[PASS] extract_json_code_block")


def test_extract_json_inline():
    """Test: extract JSON from text with surrounding content"""
    result = _extract_json('Here is my analysis: {"label": "revision", "confidence": 0.85, "reasoning": "B overrides A"}')
    assert result["label"] == "revision"
    assert result["confidence"] == 0.85
    print("[PASS] extract_json_inline")


def test_extract_json_invalid():
    """Test: extract_json raises on invalid input"""
    try:
        _extract_json("no json here at all")
        assert False, "Should raise"
    except ValueError:
        pass
    print("[PASS] extract_json_invalid")


def test_parse_label():
    """Test: label string → EdgeLabel mapping"""
    assert _parse_label("causal") == EdgeLabel.CAUSAL
    assert _parse_label("similar") == EdgeLabel.SIMILAR
    assert _parse_label("revision") == EdgeLabel.REVISION
    assert _parse_label("adjacent") == EdgeLabel.ADJACENT
    assert _parse_label("none") is None
    assert _parse_label("CAUSAL") == EdgeLabel.CAUSAL  # case insensitive
    assert _parse_label("  causal  ") == EdgeLabel.CAUSAL  # strip
    print("[PASS] parse_label")


# ── 5. LLMEdgeClassifier: classify ──

def test_classifier_classify_causal():
    """Test: classify returns causal"""
    provider = MockProvider([
        {"content": '{"label": "causal", "confidence": 0.95}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "Found timeout bug", session="s1", tags=["bug"])
    b = _make_atom("b1", "Fixed timeout to 60s", session="s2", tags=["fix"])

    label, conf = classifier.classify(a, b)
    assert label == EdgeLabel.CAUSAL
    assert conf == 0.95
    assert classifier._classify_calls == 1
    assert classifier._classify_success == 1
    print("[PASS] classifier_classify_causal")


def test_classifier_classify_similar():
    """Test: classify returns similar"""
    provider = MockProvider([
        {"content": '{"label": "similar", "confidence": 0.8}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "API error in Python", session="s1", tags=["api"])
    b = _make_atom("b1", "Error handling in JS", session="s2", tags=["api"])

    label, conf = classifier.classify(a, b)
    assert label == EdgeLabel.SIMILAR
    assert conf == 0.8
    print("[PASS] classifier_classify_similar")


def test_classifier_classify_revision():
    """Test: classify returns revision"""
    provider = MockProvider([
        {"content": '{"label": "revision", "confidence": 0.9}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "Use timeout=30s", session="s1", tags=["config"])
    b = _make_atom("b1", "Change timeout to 60s", session="s2", tags=["config"])

    label, conf = classifier.classify(a, b)
    assert label == EdgeLabel.REVISION
    print("[PASS] classifier_classify_revision")


def test_classifier_classify_none():
    """Test: classify returns 'none' → very low confidence"""
    provider = MockProvider([
        {"content": '{"label": "none", "confidence": 0.1}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "API timeout fix", session="s1", tags=["api"])
    b = _make_atom("b1", "CSS layout bug", session="s2", tags=["css"])

    label, conf = classifier.classify(a, b)
    # "none" returns SIMILAR with 0.01 confidence (effectively no edge)
    assert conf == 0.01
    print("[PASS] classifier_classify_none")


def test_classifier_confidence_clamping():
    """Test: confidence is clamped to [0.0, 1.0]"""
    provider = MockProvider([
        {"content": '{"label": "causal", "confidence": 1.5}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "Bug found", session="s1")
    b = _make_atom("b1", "Bug fixed", session="s2")

    _, conf = classifier.classify(a, b)
    assert conf == 1.0  # clamped

    provider2 = MockProvider([
        {"content": '{"label": "similar", "confidence": -0.5}', "model": "mock", "usage": {}}
    ])
    classifier2 = LLMEdgeClassifier(provider2)
    _, conf = classifier2.classify(a, b)
    assert conf == 0.0  # clamped
    print("[PASS] classifier_confidence_clamping")


# ── 6. LLMEdgeClassifier: fallback ──

def test_classifier_fallback_on_error():
    """Test: classifier falls back to rules when LLM fails"""
    provider = MockProvider(raise_on=1)  # always fails
    classifier = LLMEdgeClassifier(provider, max_retries=0)

    a = _make_atom("a1", "API timeout error", session="s1", tags=["error", "api"])
    b = _make_atom("b1", "API timeout investigation", session="s2", tags=["error", "api"])

    label, conf = classifier.classify(a, b)
    assert classifier._classify_fallback == 1
    assert conf <= 0.4  # fallback confidence is low
    print("[PASS] classifier_fallback_on_error")


def test_classifier_retry_then_fallback():
    """Test: retries transient errors then succeeds"""
    provider = MockProvider(raise_on=2)  # fails first 2 calls
    provider.responses = [
        {},  # call 1 raises
        {},  # call 2 raises
        {"content": '{"label": "causal", "confidence": 0.85}', "model": "mock", "usage": {}},
    ]
    classifier = LLMEdgeClassifier(provider, max_retries=2)

    a = _make_atom("a1", "Bug found", session="s1")
    b = _make_atom("b1", "Bug fixed", session="s2")

    label, conf = classifier.classify(a, b)
    # Call 3 succeeds (index 2 in responses)
    assert classifier._classify_success == 1
    assert label == EdgeLabel.CAUSAL
    print("[PASS] classifier_retry_then_fallback")


# ── 7. LLMEdgeClassifier: merge ──

def test_classifier_merge_true():
    """Test: should_merge returns True"""
    provider = MockProvider([
        {"content": '{"merge": true, "confidence": 0.9}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "Config timeout=30s", session="s1", tags=["config"])
    b = _make_atom("b1", "Config timeout=30s", session="s2", tags=["config"])

    should, conf = classifier.should_merge(a, b)
    assert should is True
    assert conf == 0.9
    assert classifier._merge_calls == 1
    assert classifier._merge_success == 1
    print("[PASS] classifier_merge_true")


def test_classifier_merge_false():
    """Test: should_merge returns False"""
    provider = MockProvider([
        {"content": '{"merge": false, "confidence": 0.95}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "API timeout", session="s1", tags=["api"])
    b = _make_atom("b1", "DB pool config", session="s2", tags=["db"])

    should, conf = classifier.should_merge(a, b)
    assert should is False
    print("[PASS] classifier_merge_false")


def test_classifier_merge_fallback():
    """Test: merge fallback when LLM fails"""
    provider = MockProvider(raise_on=1)
    classifier = LLMEdgeClassifier(provider, max_retries=0)

    # High overlap → should merge
    a = _make_atom("a1", "API timeout error fix", session="s1", tags=["api", "error", "fix"])
    b = _make_atom("b1", "API timeout error fix", session="s2", tags=["api", "error", "fix"])

    should, conf = classifier.should_merge(a, b)
    assert classifier._merge_fallback == 1
    # With 3 shared tags and high content overlap, should merge
    assert should is True
    print("[PASS] classifier_merge_fallback")


# ── 8. Stats ──

def test_classifier_stats():
    """Test: classifier tracks stats correctly"""
    provider = MockProvider([
        {"content": '{"label": "causal", "confidence": 0.9}', "model": "mock", "usage": {}},
        {"content": '{"label": "similar", "confidence": 0.7}', "model": "mock", "usage": {}},
    ])
    classifier = LLMEdgeClassifier(provider)
    a = _make_atom("a1", "Bug found", session="s1")
    b = _make_atom("b1", "Bug fixed", session="s2")
    c = _make_atom("c1", "Another bug", session="s3")

    classifier.classify(a, b)
    classifier.classify(a, c)

    stats = classifier.stats()
    assert stats["provider"] == "mock"
    assert stats["classify_calls"] == 2
    assert stats["classify_success"] == 2
    assert stats["classify_fallback"] == 0
    assert stats["classify_success_rate"] == 1.0
    assert stats["merge_calls"] == 0
    print("[PASS] classifier_stats")


# ── 9. create_llm_classify_callback ──

def test_create_llm_classify_callback():
    """Test: callback is compatible with classify_cross_session_edge signature"""
    provider = MockProvider([
        {"content": '{"label": "causal", "confidence": 0.9}', "model": "mock", "usage": {}}
    ])
    classifier = LLMEdgeClassifier(provider)
    callback = create_llm_classify_callback(classifier)

    a = _make_atom("a1", "Found bug", session="s1")
    b = _make_atom("b1", "Fixed bug", session="s2")

    label, conf = callback(a, b)
    assert label == EdgeLabel.CAUSAL
    assert conf == 0.9
    print("[PASS] create_llm_classify_callback")


# ── 10. Code block JSON extraction ──

def test_extract_json_code_block_no_lang():
    """Test: extract JSON from ``` code block without language"""
    result = _extract_json('```\n{"label": "causal", "confidence": 0.9}\n```')
    assert result["label"] == "causal"
    print("[PASS] extract_json_code_block_no_lang")


def test_extract_json_with_reasoning():
    """Test: extract JSON with reasoning field"""
    result = _extract_json(
        '{"label": "similar", "confidence": 0.75, "reasoning": "Both describe API error handling patterns"}'
    )
    assert result["label"] == "similar"
    assert result["confidence"] == 0.75
    assert "reasoning" in result
    print("[PASS] extract_json_with_reasoning")


# ── 11. Prompt template content ──

def test_classification_prompt_contains_edge_types():
    """Test: system prompt mentions all edge types"""
    assert "causal" in CLASSIFICATION_SYSTEM_PROMPT
    assert "similar" in CLASSIFICATION_SYSTEM_PROMPT
    assert "revision" in CLASSIFICATION_SYSTEM_PROMPT
    assert "adjacent" in CLASSIFICATION_SYSTEM_PROMPT
    assert "none" in CLASSIFICATION_SYSTEM_PROMPT
    print("[PASS] classification_prompt_contains_edge_types")


def test_merge_prompt_structure():
    """Test: merge prompt has required sections"""
    assert "merge" in MERGE_SYSTEM_PROMPT.lower()
    assert "When to Merge" in MERGE_SYSTEM_PROMPT
    assert "When NOT to Merge" in MERGE_SYSTEM_PROMPT
    print("[PASS] merge_prompt_structure")


# ── 12. SDK Integration ──

def test_sdk_llm_classifier_constructor():
    """Test: SDK accepts llm_classifier"""
    provider = MockProvider()
    classifier = LLMEdgeClassifier(provider)
    mem = VibeMemory(
        agent_id="test-agent",
        db_path=":memory:",
        llm_classifier=classifier,
    )
    assert mem.llm_classifier is classifier
    assert mem.indexer.llm_classify is not None
    print("[PASS] sdk_llm_classifier_constructor")


def test_sdk_stats_includes_llm_classifier():
    """Test: stats() includes llm_classifier when present"""
    provider = MockProvider()
    classifier = LLMEdgeClassifier(provider)
    mem = VibeMemory(
        agent_id="test-agent",
        db_path=":memory:",
        llm_classifier=classifier,
    )
    stats = mem.stats()
    assert "llm_classifier" in stats
    assert stats["llm_classifier"]["provider"] == "mock"
    print("[PASS] sdk_stats_includes_llm_classifier")


def test_sdk_stats_no_llm_classifier():
    """Test: stats() works without llm_classifier"""
    mem = VibeMemory(agent_id="test-agent", db_path=":memory:")
    stats = mem.stats()
    assert "llm_classifier" not in stats
    print("[PASS] sdk_stats_no_llm_classifier")


def test_sdk_flush_index_with_llm():
    """Test: flush_index uses LLM classifier when available"""
    provider = MockProvider([
        {"content": '{"label": "causal", "confidence": 0.85}', "model": "mock", "usage": {}},
    ])
    classifier = LLMEdgeClassifier(provider)
    mem = VibeMemory(
        agent_id="test-agent",
        db_path=":memory:",
        llm_classifier=classifier,
        embedding_backend="tfidf",
    )

    # Store atoms in different sessions
    a1 = mem.store("API timeout error found", session_id="llm-s1", tags=["api", "error"],
                   auto_build_edges=False, auto_episode=False)
    a2 = mem.store("API timeout fixed to 60s", session_id="llm-s2", tags=["api", "fix"],
                   auto_build_edges=False, auto_episode=False)

    # Manually enqueue cross-session candidate
    mem.indexer.enqueue(a2, a1, 0.75)

    # Flush with LLM
    edges = mem.flush_index()
    assert edges == 1  # LLM classified as causal

    idx_stats = mem.indexer.stats()
    assert idx_stats["edges_created"] == 1
    print("[PASS] sdk_flush_index_with_llm")


def test_sdk_flush_index_llm_error_graceful():
    """Test: flush_index handles LLM errors gracefully"""
    provider = MockProvider(raise_on=1)
    classifier = LLMEdgeClassifier(provider, max_retries=0)
    mem = VibeMemory(
        agent_id="test-agent",
        db_path=":memory:",
        llm_classifier=classifier,
        embedding_backend="tfidf",
    )

    a1 = mem.store("API error", session_id="s1", auto_build_edges=False, auto_episode=False)
    a2 = mem.store("API fix", session_id="s2", auto_build_edges=False, auto_episode=False)

    mem.indexer.enqueue(a2, a1, 0.75)
    edges = mem.flush_index()

    # LLM failed, but flush_index should not crash
    # The candidate is processed (processed_count increased) but edge may not be created
    # due to low fallback confidence
    idx_stats = mem.indexer.stats()
    assert idx_stats["processed_count"] == 1
    print("[PASS] sdk_flush_index_llm_error_graceful")


# ── 13. Edge source tracking ──

def test_llm_classifier_edge_source():
    """Test: edges created by LLM classifier use EdgeSource.LLM"""
    provider = MockProvider([
        {"content": '{"label": "causal", "confidence": 0.9}', "model": "mock", "usage": {}},
    ])
    classifier = LLMEdgeClassifier(provider)
    mem = VibeMemory(
        agent_id="test-agent",
        db_path=":memory:",
        llm_classifier=classifier,
        embedding_backend="tfidf",
    )

    a1 = mem.store("Bug found", session_id="s1", auto_build_edges=False, auto_episode=False)
    a2 = mem.store("Bug fixed", session_id="s2", auto_build_edges=False, auto_episode=False)

    mem.indexer.enqueue(a2, a1, 0.8)
    mem.flush_index()

    all_edges = mem.storage.get_all_edges()
    assert len(all_edges) == 1
    assert all_edges[0].source == EdgeSource.LLM
    print("[PASS] llm_classifier_edge_source")


# ── 14. Default classifier values ──

def test_classifier_default_values():
    """Test: classifier has sensible defaults"""
    provider = MockProvider()
    classifier = LLMEdgeClassifier(provider)
    assert classifier.max_retries == 2
    assert classifier.default_label == EdgeLabel.SIMILAR
    assert classifier.default_confidence == 0.3
    print("[PASS] classifier_default_values")


def test_classifier_custom_defaults():
    """Test: classifier accepts custom defaults"""
    provider = MockProvider()
    classifier = LLMEdgeClassifier(
        provider,
        max_retries=5,
        default_label=EdgeLabel.CAUSAL,
        default_confidence=0.5,
    )
    assert classifier.max_retries == 5
    assert classifier.default_label == EdgeLabel.CAUSAL
    assert classifier.default_confidence == 0.5
    print("[PASS] classifier_custom_defaults")


# ── 15. Messages contain tags ──

def test_build_messages_contains_tags():
    """Test: user prompt includes tags"""
    a = _make_atom("a1", "Content A", tags=["error", "api", "timeout"])
    b = _make_atom("b1", "Content B", tags=["error", "fix"])

    msgs = build_classification_messages(a, b)
    assert "Tags: error, api, timeout" in msgs[1]["content"]
    assert "Tags: error, fix" in msgs[1]["content"]
    print("[PASS] build_messages_contains_tags")


# ─── Run all ───

if __name__ == "__main__":
    tests = [
        test_llm_provider_abc,
        test_llm_error,
        test_openai_provider_init,
        test_openai_provider_custom,
        test_create_provider,
        test_build_classification_messages,
        test_build_classification_messages_with_context,
        test_build_merge_messages,
        test_extract_json_pure,
        test_extract_json_code_block,
        test_extract_json_inline,
        test_extract_json_invalid,
        test_parse_label,
        test_classifier_classify_causal,
        test_classifier_classify_similar,
        test_classifier_classify_revision,
        test_classifier_classify_none,
        test_classifier_confidence_clamping,
        test_classifier_fallback_on_error,
        test_classifier_retry_then_fallback,
        test_classifier_merge_true,
        test_classifier_merge_false,
        test_classifier_merge_fallback,
        test_classifier_stats,
        test_create_llm_classify_callback,
        test_extract_json_code_block_no_lang,
        test_extract_json_with_reasoning,
        test_classification_prompt_contains_edge_types,
        test_merge_prompt_structure,
        test_sdk_llm_classifier_constructor,
        test_sdk_stats_includes_llm_classifier,
        test_sdk_stats_no_llm_classifier,
        test_sdk_flush_index_with_llm,
        test_sdk_flush_index_llm_error_graceful,
        test_llm_classifier_edge_source,
        test_classifier_default_values,
        test_classifier_custom_defaults,
        test_build_messages_contains_tags,
    ]

    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")

    print(f"\n{passed}/{len(tests)} tests passed")