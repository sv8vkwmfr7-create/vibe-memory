"""
Memory Defense — Privacy scanning for VibeMemory

Scans content for PII and secrets before storage.
Inspired by Hindsight's Memory Defense.

Default: redact mode (replaces PII with [REDACTED:type]).
Can be set to block mode (rejects storage entirely).

Patterns detected:
  - API keys (OpenAI, Anthropic, GitHub, generic)
  - Passwords and credentials
  - Email addresses
  - Phone numbers (CN/US)
  - Credit card numbers
  - IP addresses
  - JWT tokens
  - Chinese ID numbers
  - AWS/GCP/Azure keys

Usage:
    from vibe_memory.defense import MemoryDefense

    defense = MemoryDefense(mode="redact")
    clean_content, violations = defense.scan("my content with sk-abc123")
    # → ("my content with [REDACTED:openai_api_key]", [{"type": "openai_api_key", ...}])
"""

import re
from typing import Optional
from enum import Enum


class DefenseMode(str, Enum):
    REDACT = "redact"      # Replace PII with [REDACTED:type]
    BLOCK = "block"        # Reject storage entirely
    WARN = "warn"          # Log warning, store anyway


# ═══════════════════════════════════════════════════════════════════
# Detection Patterns
# ═══════════════════════════════════════════════════════════════════

PATTERNS = [
    # API Keys
    (r'sk-[A-Za-z0-9]{32,}', "openai_api_key"),
    (r'sk-ant-[A-Za-z0-9\-]{32,}', "anthropic_api_key"),
    (r'ghp_[A-Za-z0-9]{36}', "github_pat"),
    (r'github_pat_[A-Za-z0-9_]{36,}', "github_pat"),
    (r'AIza[0-9A-Za-z\-_]{35}', "google_api_key"),
    (r'AKIA[0-9A-Z]{16}', "aws_access_key"),

    # Passwords & Credentials
    (r'(?:password|passwd|pwd)\s*[:=]\s*[\S]{4,}', "password_in_text"),
    (r'(?:secret|token|key)\s*[:=]\s*[\S]{8,}', "credential_in_text"),

    # Email addresses
    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "email"),

    # Phone numbers
    (r'(?<![A-Za-z0-9_])1[3-9]\d{9}(?![A-Za-z0-9_])', "cn_phone"),
    (r'\+\d{1,3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{4}', "international_phone"),

    # IP addresses
    (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', "ip_address"),

    # JWT tokens
    (r'eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*', "jwt_token"),

    # Chinese ID
    (r'\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b', "cn_id"),

    # AWS/GCP/Azure keys
    (r'(?:AWS|aws)[\s_]*?(?:SECRET|secret|Secret)[\s_]*?(?:ACCESS|access|Access)[\s_]*?(?:KEY|key|Key)\s*[:=]\s*\S{16,}', "aws_secret_key"),
    (r'(?:GCP|gcp)[\s_]*?(?:KEY|key|Key)\s*[:=]\s*[\S]{16,}', "gcp_key"),
    (r'(?:azure|Azure|AZURE)[\s_]*?(?:key|Key|KEY)\s*[:=]\s*[\S]{16,}', "azure_key"),
]

# Lower-confidence patterns (only match if context suggests it's a secret)
LOW_CONFIDENCE_PATTERNS = [
    (r'\b(?:api[ _-]?key|access[ _-]?key)\s*[:=]\s*[A-Za-z0-9+/]{40,}(?![A-Za-z0-9+/])', "generic_api_key"),
    (r'(?:\bcredit[ _-]?card\b|\bcard[ _-]?(?:number|no)\b|银行卡(?:号)?|信用卡(?:号)?)\s*[:=：]\s*(?:\d[ -]*?){13,19}(?!\d)', "credit_card"),
]


class MemoryDefense:
    """
    Privacy scanner for memory content.

    Args:
        mode: "redact" (default) — replace PII; "block" — reject; "warn" — return findings without rewriting
        patterns: Custom patterns to add (list of (regex, type) tuples)
        exclude_patterns: Pattern types to skip
    """

    def __init__(
        self,
        mode: str = "redact",
        patterns: Optional[list[tuple[str, str]]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ):
        self.mode = DefenseMode(mode)
        self.exclude = set(exclude_patterns or [])
        self._compiled = self._compile_patterns(patterns)

    def _compile_patterns(self, custom: Optional[list[tuple[str, str]]] = None):
        all_patterns = list(PATTERNS) + list(LOW_CONFIDENCE_PATTERNS)
        if custom:
            all_patterns.extend(custom)
        return [(re.compile(p, re.IGNORECASE), t) for p, t in all_patterns if t not in self.exclude]

    def scan(self, content: str) -> tuple[str, list[dict]]:
        """
        Scan content for PII.

        Generic keys and card numbers require explicit labels; identifiers are not
        secrets merely because of their length. This is a heuristic, not a DLP guarantee.
        Overlap markers use the leftmost, longest finding's type; all original
        findings (including raw matches) remain in violations. Do not log them.

        Returns:
            (cleaned_content, violations_list)
            cleaned_content: content with PII redacted (redact mode) or original
            violations: [{"type": str, "match": str, "position": (start, end)}, ...]
        """
        violations = []
        cleaned = content

        for pattern, ptype in self._compiled:
            for match in pattern.finditer(content):
                violations.append({
                    "type": ptype,
                    "match": match.group(),
                    "position": (match.start(), match.end()),
                })

        if self.mode == DefenseMode.BLOCK:
            return content, violations

        if self.mode == DefenseMode.REDACT and violations:
            # All offsets refer to the original text. Merge overlaps before replacement.
            spans = []
            for v in sorted(violations, key=lambda x: (x["position"][0], -x["position"][1])):
                start, end = v["position"]
                if spans and start < spans[-1][1]:
                    spans[-1][1] = max(spans[-1][1], end)
                else:
                    spans.append([start, end, v["type"]])
            for start, end, ptype in reversed(spans):
                cleaned = cleaned[:start] + f"[REDACTED:{ptype}]" + cleaned[end:]

        return cleaned, violations

    def is_blocked(self, content: str) -> bool:
        """Check if content should be blocked."""
        if self.mode != DefenseMode.BLOCK:
            return False
        _, violations = self.scan(content)
        return len(violations) > 0

    def stats(self) -> dict:
        return {
            "mode": self.mode.value,
            "patterns": len(self._compiled),
            "excluded": list(self.exclude),
        }


# Singleton for SDK integration
_default_defense = MemoryDefense(mode="redact")


def scan_before_store(content: str, defense: Optional[MemoryDefense] = None) -> tuple[str, list[dict], bool]:
    """
    Scan content before storing. Used by SDK's store() method.

    Args:
        content: Content to scan
        defense: MemoryDefense instance (None → default redact mode)

    Returns:
        (cleaned_content, violations, blocked)
    """
    d = defense or _default_defense
    cleaned, violations = d.scan(content)
    blocked = d.mode == DefenseMode.BLOCK and len(violations) > 0
    return cleaned, violations, blocked


def scan_text(text: str, defense: MemoryDefense) -> str:
    """Preflight a text field without exposing matched text in errors."""
    if not isinstance(text, str):
        raise ValueError("Memory text fields must be strings")
    cleaned, violations, blocked = scan_before_store(text, defense)
    if blocked:
        raise ValueError(f"Memory blocked by defense: {len(violations)} PII violations detected")
    return cleaned
