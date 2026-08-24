"""
LLM Edge Classifier — Real API Validation

Tests cross-session edge classification with real Anthropic Claude API.
Validates: classification quality, latency, cost, fallback behavior.

Usage:
    python experiments/llm_validation.py
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vibe_memory.models.memory_atom import MemoryAtom, EdgeLabel, Lifecycle, GraphPartition
from vibe_memory.llm import AnthropicProvider, LLMEdgeClassifier, LLMError


# ── Test Cases ──

# Each test case: (atom_a, atom_b, expected_label, description)
# Atoms are realistic conversation chunks from the VibeMemory project

ATOM_A = MemoryAtom(
    id="a1", agent_id="test", session_id="s1",
    content="Fixed API timeout error, changed from 30s to 60s",
    summary="Fixed API timeout",
    tags=["error", "config", "fix"],
    context_before="User reported API calls timing out",
    context_after="Tests passing with new timeout",
    lifecycle=Lifecycle.ACTIVE,
    type=GraphPartition.SESSION,
)

ATOM_B = MemoryAtom(
    id="a2", agent_id="test", session_id="s2",
    content="API timeout increased to 60s, but now seeing connection pool exhaustion",
    summary="Timeout fix caused pool issue",
    tags=["error", "config", "fix"],
    context_before="After increasing timeout to 60s",
    context_after="Need to increase pool size too",
    lifecycle=Lifecycle.ACTIVE,
    type=GraphPartition.SESSION,
)

ATOM_C = MemoryAtom(
    id="a3", agent_id="test", session_id="s3",
    content="Database connection pool size should be 20, not 10",
    summary="DB pool config",
    tags=["config", "database"],
    context_before="Investigating connection pool exhaustion",
    context_after="Pool size changed to 20",
    lifecycle=Lifecycle.ACTIVE,
    type=GraphPartition.SESSION,
)

ATOM_D = MemoryAtom(
    id="a4", agent_id="test", session_id="s4",
    content="Actually, the timeout should be 120s, not 60s. 60s was still too short for large queries.",
    summary="Timeout revised to 120s",
    tags=["error", "config", "revision"],
    context_before="60s timeout still causing issues",
    context_after="120s confirmed working for all query sizes",
    lifecycle=Lifecycle.ACTIVE,
    type=GraphPartition.SESSION,
)

ATOM_E = MemoryAtom(
    id="a5", agent_id="test", session_id="s5",
    content="Checked the weather API for tomorrow's forecast",
    summary="Weather check",
    tags=["query", "weather"],
    lifecycle=Lifecycle.ACTIVE,
    type=GraphPartition.SESSION,
)

# Merge test: near-duplicate atoms
ATOM_F = MemoryAtom(
    id="a6", agent_id="test", session_id="s6",
    content="Fixed API timeout error by increasing from 30s to 60s in the config",
    summary="Fixed API timeout to 60s",
    tags=["error", "config", "fix"],
    lifecycle=Lifecycle.ACTIVE,
    type=GraphPartition.SESSION,
)

ATOM_G = MemoryAtom(
    id="a7", agent_id="test", session_id="s7",
    content="Fixed the API timeout: changed from 30 seconds to 60 seconds in configuration",
    summary="Fixed API timeout (30→60s)",
    tags=["error", "config", "fix"],
    lifecycle=Lifecycle.ACTIVE,
    type=GraphPartition.SESSION,
)

TEST_CASES = [
    # (atom_a, atom_b, expected_label, description)
    (ATOM_A, ATOM_B, EdgeLabel.CAUSAL,
     "Causal: timeout fix → pool exhaustion (follow-up consequence)"),
    (ATOM_A, ATOM_C, EdgeLabel.SIMILAR,
     "Similar: both config changes (timeout & pool) but not causal"),
    (ATOM_A, ATOM_D, EdgeLabel.REVISION,
     "Revision: 60s timeout → corrected to 120s"),
    (ATOM_A, ATOM_E, None,
     "None: API timeout fix vs weather query — unrelated"),
    (ATOM_B, ATOM_D, EdgeLabel.CAUSAL,
     "Causal: 60s still insufficient → 120s fix"),
    (ATOM_F, ATOM_G, EdgeLabel.SIMILAR,
     "Similar: near-duplicate descriptions of same fix"),
]

MERGE_TESTS = [
    (ATOM_F, ATOM_G, True,
     "Merge: near-duplicate with different wording"),
    (ATOM_A, ATOM_B, False,
     "No merge: causal chain, not duplicate"),
    (ATOM_A, ATOM_D, False,
     "No merge: revision relationship, not duplicate"),
]


def run_classification_tests(classifier: LLMEdgeClassifier):
    """Run all classification test cases."""
    print("=" * 70)
    print("Classification Tests")
    print("=" * 70)

    results = []
    correct = 0
    total = len(TEST_CASES)

    for i, (atom_a, atom_b, expected, desc) in enumerate(TEST_CASES, 1):
        t0 = time.perf_counter()
        label, confidence = classifier.classify(atom_a, atom_b)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Judge correctness
        if expected is None:
            # Expected "none" — check if confidence is very low (< 0.3)
            is_correct = confidence < 0.3
        else:
            is_correct = (label == expected)

        status = "✅" if is_correct else "❌"
        if is_correct:
            correct += 1

        print(f"\n  {status} Test {i}: {desc}")
        print(f"     Expected: {expected.value if expected else 'none'} | "
              f"Got: {label.value} (conf={confidence:.2f}) | "
              f"{elapsed_ms:.0f}ms")

        results.append({
            "test": desc,
            "expected": expected.value if expected else "none",
            "got": label.value,
            "confidence": confidence,
            "correct": is_correct,
            "latency_ms": elapsed_ms,
        })

    print(f"\n  Accuracy: {correct}/{total} ({correct/total*100:.0f}%)")
    return results


def run_merge_tests(classifier: LLMEdgeClassifier):
    """Run all merge test cases."""
    print("\n" + "=" * 70)
    print("Merge Decision Tests")
    print("=" * 70)

    results = []
    correct = 0
    total = len(MERGE_TESTS)

    for i, (atom_a, atom_b, expected, desc) in enumerate(MERGE_TESTS, 1):
        t0 = time.perf_counter()
        should_merge, confidence = classifier.should_merge(atom_a, atom_b)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        is_correct = (should_merge == expected)
        if is_correct:
            correct += 1

        status = "✅" if is_correct else "❌"
        print(f"\n  {status} Test {i}: {desc}")
        print(f"     Expected: merge={expected} | "
              f"Got: merge={should_merge} (conf={confidence:.2f}) | "
              f"{elapsed_ms:.0f}ms")

        results.append({
            "test": desc,
            "expected_merge": expected,
            "got_merge": should_merge,
            "confidence": confidence,
            "correct": is_correct,
            "latency_ms": elapsed_ms,
        })

    print(f"\n  Accuracy: {correct}/{total} ({correct/total*100:.0f}%)")
    return results


def run_fallback_test(classifier: LLMEdgeClassifier):
    """Test fallback by using invalid provider."""
    print("\n" + "=" * 70)
    print("Fallback Test")
    print("=" * 70)

    # Create classifier with non-existent URL to trigger fallback
    bad_provider = AnthropicProvider(
        api_key="fake-key",
        base_url="https://localhost:99999",
        model="claude-sonnet-4-20250514",
        timeout=2.0,
        max_retries=0,
    )
    fallback_classifier = LLMEdgeClassifier(bad_provider, max_retries=0)

    t0 = time.perf_counter()
    label, confidence = fallback_classifier.classify(ATOM_A, ATOM_B)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\n  Input: A=timeout fix, B=pool fix (both error+config tags)")
    print(f"  Result: {label.value} (conf={confidence:.2f}) | {elapsed_ms:.0f}ms")
    print(f"  Fallback stats: {fallback_classifier.stats()}")

    # Verify fallback was triggered
    stats = fallback_classifier.stats()
    assert stats["classify_fallback"] == 1, "Fallback should have been triggered"
    assert stats["classify_success"] == 0, "No real API calls should succeed"
    print(f"  ✅ Fallback triggered correctly (confidence={confidence}, should be <= 0.4)")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["anthropic", "transformers"], default="transformers")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-0.5B-Instruct")
    args = parser.parse_args()

    print("VibeMemory LLM Edge Classifier — Real Validation")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Provider: {args.provider}, Model: {args.model}")

    # Initialize
    if args.provider == "anthropic":
        from vibe_memory.llm import AnthropicProvider
        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
    else:
        from vibe_memory.llm import TransformersProvider
        provider = TransformersProvider(model_name=args.model)
        print("(first call will download model — this may take a minute)")

    classifier = LLMEdgeClassifier(provider)

    print(f"Provider: {provider.name}")

    if args.provider == "anthropic" and not provider.api_key:
        print("\n⚠️  No Anthropic API key found. Set ANTHROPIC_AUTH_TOKEN env var.")
        print("   Running fallback test only...")
        run_fallback_test(classifier)
        return

    # Run all tests
    class_results = run_classification_tests(classifier)
    merge_results = run_merge_tests(classifier)
    run_fallback_test(classifier)
    run_end_to_end_with_provider(args.provider, args.model)

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    class_correct = sum(1 for r in class_results if r["correct"])
    merge_correct = sum(1 for r in merge_results if r["correct"])
    class_avg_latency = sum(r["latency_ms"] for r in class_results) / len(class_results) if class_results else 0
    merge_avg_latency = sum(r["latency_ms"] for r in merge_results) / len(merge_results) if merge_results else 0

    print(f"\n  Classification: {class_correct}/{len(class_results)} correct "
          f"({class_avg_latency:.0f}ms avg)")
    print(f"  Merge:          {merge_correct}/{len(merge_results)} correct "
          f"({merge_avg_latency:.0f}ms avg)")
    print(f"  Fallback:       ✅ works")

    classifier_stats = classifier.stats()
    print(f"\n  Total API calls: {classifier_stats['classify_success'] + classifier_stats['merge_success']}")
    print(f"  Total fallbacks: {classifier_stats['classify_fallback'] + classifier_stats['merge_fallback']}")
    print(f"  Overall avg latency: {classifier_stats['avg_latency_ms']:.0f}ms")


def run_end_to_end_with_provider(provider_type: str, model_name: str):
    """Full end-to-end with specified provider."""
    print("\n" + "=" * 70)
    print("End-to-End: LLM-Powered Edge Building")
    print("=" * 70)

    from vibe_memory import VibeMemory
    from vibe_memory.llm import AnthropicProvider, TransformersProvider, LLMEdgeClassifier

    if provider_type == "anthropic":
        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
    else:
        provider = TransformersProvider(model_name=model_name)

    classifier = LLMEdgeClassifier(provider)

    mem = VibeMemory(
        agent_id="e2e-test",
        db_path=":memory:",
        embedding_backend="tfidf",
        llm_classifier=classifier,
    )

    # Session 1: initial timeout fix
    a1 = mem.store(
        content="Fixed API timeout error, changed from 30s to 60s",
        session_id="s1",
        tags=["error", "config", "fix"],
    )
    print(f"\n  S1 Stored: {a1.id[:8]} — {a1.summary[:60]}")

    # Session 2: follow-up — pool issue caused by timeout fix
    a2 = mem.store(
        content="After increasing timeout to 60s, connection pool exhausted. Increased pool size to 20.",
        session_id="s2",
        tags=["error", "config", "fix"],
    )
    print(f"  S2 Stored: {a2.id[:8]} — {a2.summary[:60]}")

    # Session 3: correction — 60s still too short
    a3 = mem.store(
        content="Actually, timeout should be 120s not 60s. 60s was still too short for large queries.",
        session_id="s3",
        tags=["error", "config", "revision"],
    )
    print(f"  S3 Stored: {a3.id[:8]} — {a3.summary[:60]}")

    # Flush: LLM classifies all cross-session edges
    print("\n  Flushing index (LLM classification)...")
    n_edges = mem.flush_index()
    print(f"  Edges created: {n_edges}")

    # Verify edges
    edges = mem.storage.get_all_edges()
    print(f"\n  Created edges:")
    for e in edges:
        fa = mem.storage.get_atom(e.from_atom_id)
        ta = mem.storage.get_atom(e.to_atom_id)
        print(f"    {fa.summary[:50]} —[{e.label.value}]→ {ta.summary[:50]} "
              f"(conf={e.confidence:.2f}, source={e.source.value})")

    # Recall: query for timeout
    result = mem.recall("API timeout error", mode="precision")
    print(f"\n  Recall 'API timeout error': {len(result['atoms'])} atoms")
    for atom in result["atoms"]:
        print(f"    [{atom.session_id}] {atom.summary[:80]}")

    # Stats
    stats = mem.stats()
    print(f"\n  Final stats: {stats['total_atoms']} atoms, {stats['total_edges']} edges")
    if "llm_classifier" in stats:
        lc = stats["llm_classifier"]
        print(f"  LLM classifier: {lc['classify_success']} success, "
              f"{lc['classify_fallback']} fallback, "
              f"{lc['avg_latency_ms']:.0f}ms avg latency")


if __name__ == "__main__":
    main()