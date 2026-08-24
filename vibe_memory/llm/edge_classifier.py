"""
LLM Edge Classifier — classify cross-session edges with LLM

Replaces rule-based `classify_cross_session_edge()`.
Supports any OpenAI-compatible API, with fallback, retry, structured output parsing.

Usage:
    from vibe_memory.llm.provider import OpenAIProvider
    from vibe_memory.llm.edge_classifier import LLMEdgeClassifier

    provider = OpenAIProvider(api_key="sk-xxx", model="gpt-4o-mini")
    classifier = LLMEdgeClassifier(provider)

    label, confidence = classifier.classify(atom_a, atom_b)
"""

import json
import re
from typing import Optional, Callable
from datetime import datetime

from vibe_memory.models.memory_atom import MemoryAtom, EdgeLabel
from vibe_memory.llm.provider import LLMProvider, LLMError


# --- Prompt Templates ---

CLASSIFICATION_SYSTEM_PROMPT = """You are a memory graph edge classifier. Your job is to classify the relationship between two memory atoms from an AI agent's conversation history.

A memory atom is a self-contained semantic chunk extracted from a conversation. You will see two atoms (A and B), and you must determine their relationship type.

## Relationship Types

- **causal**: A directly caused or led to B. B is a follow-up, consequence, or continuation of A.
  Example: A="fixed timeout bug", B="timeout increased to 60s"
- **similar**: A and B describe the same type of problem, experience, or topic. They are related but not causally connected.
  Example: A="API error handling in Python", B="error handling in JavaScript"
- **revision**: B corrects, contradicts, or overrides A's conclusion. B is a newer version of the truth.
  Example: A="use timeout=30s", B="actually timeout=60s is better"
- **adjacent**: A and B appeared close together in the same conversation, but have no strong causal or thematic link.
  Example: A="check weather API", B="fix database pool config"
- **none**: No meaningful relationship between A and B. They are completely unrelated.

## Confidence Guidelines

- 0.9-1.0: Clear causal chain or direct contradiction
- 0.7-0.89: Strong thematic overlap, likely related
- 0.5-0.69: Weak connection, could go either way
- 0.3-0.49: Vague similarity, probably unrelated
- 0.0-0.29: No relationship

Respond with JSON only, no other text:
{"label": "causal|similar|revision|adjacent|none", "confidence": 0.0-1.0, "reasoning": "one sentence explaining why"}"""


def build_classification_messages(
    atom_a: MemoryAtom,
    atom_b: MemoryAtom,
) -> list[dict]:
    """Build classification prompt messages."""

    def _format_atom(atom: MemoryAtom, label: str) -> str:
        parts = [
            f"## {label}",
            f"Session: {atom.session_id}",
            f"Content: {atom.content}",
        ]
        if atom.context_before:
            parts.append(f"Context before: {atom.context_before}")
        if atom.context_after:
            parts.append(f"Context after: {atom.context_after}")
        if atom.tags:
            parts.append(f"Tags: {', '.join(atom.tags)}")
        return "\n".join(parts)

    user_prompt = _format_atom(atom_a, "Atom A") + "\n\n" + _format_atom(atom_b, "Atom B")

    return [
        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# --- Merge Prompt ---

MERGE_SYSTEM_PROMPT = """You are a memory graph merge classifier. Two memory atoms appear to be highly similar. Decide whether they should be merged into one.

## When to Merge

Merge if:
- They describe the same event/fact from different angles
- One is a refined version of the other
- They are near-duplicates with minor wording differences

## When NOT to Merge

Keep separate if:
- They describe different events that happen to share keywords
- They are sequential steps in a process (use causal edge instead)
- One is a correction of the other (use revision edge instead)

Respond with JSON only:
{"merge": true|false, "confidence": 0.0-1.0, "reasoning": "one sentence"}"""


def build_merge_messages(
    atom_a: MemoryAtom,
    atom_b: MemoryAtom,
) -> list[dict]:
    """Build merge decision prompt."""

    parts = [
        f"## Atom A\nSession: {atom_a.session_id}\nContent: {atom_a.content}\nTags: {', '.join(atom_a.tags)}",
        f"## Atom B\nSession: {atom_b.session_id}\nContent: {atom_b.content}\nTags: {', '.join(atom_b.tags)}",
    ]

    return [
        {"role": "system", "content": MERGE_SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


# --- Response Parser ---

def _extract_json(text: str) -> dict:
    """Extract JSON object from LLM response."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try ```json ... ``` code block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try first { ... } object
    match = re.search(r'\{[^{}]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


LABEL_MAP = {
    "causal": EdgeLabel.CAUSAL,
    "similar": EdgeLabel.SIMILAR,
    "revision": EdgeLabel.REVISION,
    "adjacent": EdgeLabel.ADJACENT,
    "none": None,
}


def _parse_label(label_str: str) -> Optional[EdgeLabel]:
    """Parse label string to EdgeLabel."""
    return LABEL_MAP.get(label_str.lower().strip())


# --- LLM Edge Classifier ---

class LLMEdgeClassifier:
    """
    LLM-driven cross-session edge classifier.

    Features:
    - Structured prompt (with context)
    - Timeout/rate-limit auto-retry + fallback to rules
    - Robust parsing: pure JSON, ```json code block, direct extraction
    - Merge decision: whether highly similar atoms should be merged

    Args:
        provider: LLMProvider instance
        max_retries: max retry attempts
        default_label: fallback label when LLM unavailable
        default_confidence: fallback confidence when LLM unavailable
    """

    def __init__(
        self,
        provider: LLMProvider,
        max_retries: int = 2,
        default_label: EdgeLabel = EdgeLabel.SIMILAR,
        default_confidence: float = 0.3,
    ):
        self.provider = provider
        self.max_retries = max_retries
        self.default_label = default_label
        self.default_confidence = default_confidence

        # Stats
        self._classify_calls: int = 0
        self._classify_success: int = 0
        self._classify_fallback: int = 0
        self._merge_calls: int = 0
        self._merge_success: int = 0
        self._merge_fallback: int = 0
        self._total_latency_ms: float = 0.0

    # --- Classify ---

    def classify(
        self,
        atom_a: MemoryAtom,
        atom_b: MemoryAtom,
    ) -> tuple[EdgeLabel, float]:
        """
        Classify relationship between two atoms using LLM.

        Args:
            atom_a: Atom A
            atom_b: Atom B

        Returns:
            (EdgeLabel, confidence)
        """
        self._classify_calls += 1
        t0 = datetime.now()

        messages = build_classification_messages(atom_a, atom_b)

        for attempt in range(self.max_retries + 1):
            try:
                result = self.provider.chat(messages, temperature=0.1, max_tokens=256)
                parsed = _extract_json(result["content"])

                label_str = parsed.get("label", "")
                label = _parse_label(label_str)
                confidence = float(parsed.get("confidence", 0.5))

                if label is None:
                    # LLM returned "none" — very low confidence, edge won't be created
                    self._classify_success += 1
                    self._total_latency_ms += (datetime.now() - t0).total_seconds() * 1000
                    return EdgeLabel.SIMILAR, 0.01

                # Clamp confidence to [0.0, 1.0]
                confidence = max(0.0, min(1.0, confidence))

                self._classify_success += 1
                self._total_latency_ms += (datetime.now() - t0).total_seconds() * 1000
                return label, confidence

            except (LLMError, ValueError, KeyError) as e:
                if attempt < self.max_retries:
                    import time
                    time.sleep(1.5 ** attempt)
                    continue
                # All retries exhausted — fallback
                break

        # Fallback: rule-based
        self._classify_fallback += 1
        self._total_latency_ms += (datetime.now() - t0).total_seconds() * 1000
        return self._fallback_classify(atom_a, atom_b)

    # --- Merge Decision ---

    def should_merge(
        self,
        atom_a: MemoryAtom,
        atom_b: MemoryAtom,
    ) -> tuple[bool, float]:
        """
        Decide whether two highly similar atoms should be merged.

        Returns:
            (should_merge: bool, confidence: float)
        """
        self._merge_calls += 1
        t0 = datetime.now()

        messages = build_merge_messages(atom_a, atom_b)

        for attempt in range(self.max_retries + 1):
            try:
                result = self.provider.chat(messages, temperature=0.1, max_tokens=256)
                parsed = _extract_json(result["content"])

                should_merge = bool(parsed.get("merge", False))
                confidence = float(parsed.get("confidence", 0.5))

                self._merge_success += 1
                self._total_latency_ms += (datetime.now() - t0).total_seconds() * 1000
                return should_merge, max(0.0, min(1.0, confidence))

            except (LLMError, ValueError, KeyError):
                if attempt < self.max_retries:
                    import time
                    time.sleep(1.5 ** attempt)
                    continue
                break

        # Fallback: tag-overlap based
        self._merge_fallback += 1
        self._total_latency_ms += (datetime.now() - t0).total_seconds() * 1000
        return self._fallback_merge(atom_a, atom_b)

    # --- Fallback ---

    def _fallback_classify(
        self,
        atom_a: MemoryAtom,
        atom_b: MemoryAtom,
    ) -> tuple[EdgeLabel, float]:
        """Rule-based fallback classification (same logic as classify_cross_session_edge)."""
        from vibe_memory.edges.edge_builder import _tag_overlap_ratio, _has_causal_signal

        overlap = _tag_overlap_ratio(atom_a, atom_b)

        if _has_causal_signal(atom_a.content) and _has_causal_signal(atom_b.content):
            return EdgeLabel.CAUSAL, 0.4
        if overlap >= 0.5:
            return EdgeLabel.SIMILAR, 0.3
        return EdgeLabel.SIMILAR, 0.2

    def _fallback_merge(
        self,
        atom_a: MemoryAtom,
        atom_b: MemoryAtom,
    ) -> tuple[bool, float]:
        """Rule-based fallback merge decision."""
        from vibe_memory.edges.edge_builder import _tag_overlap_ratio

        overlap = _tag_overlap_ratio(atom_a, atom_b)
        # Tag overlap > 0.8 and high content similarity — merge
        if overlap > 0.8:
            words_a = set(atom_a.content.lower().split())
            words_b = set(atom_b.content.lower().split())
            content_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
            if content_overlap > 0.5:
                return True, 0.4
        return False, 0.0

    # --- Stats ---

    def stats(self) -> dict:
        """Classifier statistics."""
        return {
            "provider": self.provider.name,
            "classify_calls": self._classify_calls,
            "classify_success": self._classify_success,
            "classify_fallback": self._classify_fallback,
            "classify_success_rate": (
                self._classify_success / max(self._classify_calls, 1)
            ),
            "merge_calls": self._merge_calls,
            "merge_success": self._merge_success,
            "merge_fallback": self._merge_fallback,
            "merge_success_rate": (
                self._merge_success / max(self._merge_calls, 1)
            ),
            "avg_latency_ms": (
                self._total_latency_ms / max(self._classify_calls + self._merge_calls, 1)
            ),
        }


# --- Factory: create callback compatible with IncrementalIndexer ---

def create_llm_classify_callback(
    classifier: LLMEdgeClassifier,
) -> Callable[[MemoryAtom, MemoryAtom], tuple[EdgeLabel, float]]:
    """
    Create llm_classify callback compatible with IncrementalIndexer.

    Usage:
        classifier = LLMEdgeClassifier(provider)
        indexer = IncrementalIndexer(
            ...,
            llm_classify=create_llm_classify_callback(classifier),
        )
    """
    return classifier.classify