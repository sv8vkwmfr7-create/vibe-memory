"""
Prompt Injection — MAC & MAG dual-mode context injection

MAC (Memory-Augmented Context): Full-text injection of all recalled atoms
with relationship traces. For debugging, coding, and tasks requiring complete
context. High token cost, high fidelity.

MAG (Memory-Augmented Gating): Gated signal injection — summaries and key
signals only, with priority-based grouping. For strategy, creative, and tasks
where too much context constrains creativity. Low token cost, high signal.

Edge-label-aware priority:
- causal / revision: HIGH — direct injection, critical context
- similar: MEDIUM — reference injection, related experience
- adjacent / cross-partition: LOW — weak injection, FYI only

Usage:
    from vibe_memory.injection import build_injection, MACInjector, MAGInjector

    mac = MACInjector(max_tokens=4000)
    prompt = mac.build(result)

    mag = MAGInjector(max_tokens=1000)
    signal = mag.build(result)
"""

from typing import Optional
from vibe_memory.models.memory_atom import MemoryAtom, EdgeLabel


# --- Priority mapping ---

EDGE_PRIORITY = {
    EdgeLabel.CAUSAL: "high",
    EdgeLabel.REVISION: "high",
    EdgeLabel.SIMILAR: "medium",
    EdgeLabel.ADJACENT: "low",
    EdgeLabel.REFERENCE: "low",
    EdgeLabel.LOOKUP: "low",
    EdgeLabel.INFLUENCE: "medium",
    EdgeLabel.VERSION: "high",
}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _atom_priority(atom: MemoryAtom, trace: list[dict]) -> str:
    """Determine injection priority for an atom based on its edges."""
    atom_id = atom.id
    best = "low"
    for t in trace:
        if t.get("from") == atom_id or t.get("to") == atom_id:
            label_str = t.get("edge_label", "")
            for label in EdgeLabel:
                if label.value == label_str:
                    p = EDGE_PRIORITY.get(label, "low")
                    if PRIORITY_ORDER[p] < PRIORITY_ORDER[best]:
                        best = p
    return best


# --- MAC: Memory-Augmented Context (full-text) ---

class MACInjector:
    """
    Full-text context injection for debugging/coding tasks.

    Injects complete atom content with relationship traces.
    High token cost, high fidelity.

    Args:
        max_tokens: Maximum tokens for injection (default: 4000)
        include_trace: Whether to include edge relationship traces
        include_content: Whether to include full content (True) or summaries only (False)
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        include_trace: bool = True,
        include_content: bool = True,
    ):
        self.max_tokens = max_tokens
        self.include_trace = include_trace
        self.include_content = include_content

    def build(self, recall_result: dict) -> str:
        """Build MAC injection prompt from recall results."""
        atoms = recall_result.get("atoms", [])
        trace = recall_result.get("trace", [])
        mode = recall_result.get("mode", "precision")

        if not atoms:
            return "<!-- VibeMemory MAC: no relevant memories -->\n"

        lines = [
            "<!-- VibeMemory MAC: full context injection -->",
            "## Memory-Augmented Context",
            "",
            "The following memories were recalled from previous sessions. "
            "They contain full context and relationship information. "
            "Use this to understand the complete history without asking the user to repeat.",
            "",
        ]

        token_budget = self.max_tokens - _estimate_tokens("\n".join(lines))

        # Group by session
        by_session: dict[str, list[MemoryAtom]] = {}
        for atom in atoms:
            sid = atom.session_id[:8] if atom.session_id else "unknown"
            by_session.setdefault(sid, []).append(atom)

        # Sort sessions: most recent first (by atom count as proxy)
        sorted_sessions = sorted(
            by_session.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        for sid, session_atoms in sorted_sessions:
            header = f"### Session {sid}\n\n"
            if _estimate_tokens(header) > token_budget:
                lines.append(f"\n_(truncated — {len(atoms)} memories total, token budget exceeded)_\n")
                break
            lines.append(header)
            token_budget -= _estimate_tokens(header)

            for atom in session_atoms:
                priority = _atom_priority(atom, trace)
                prefix = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(priority, "⚪")

                if self.include_content:
                    entry = f"{prefix} **{atom.summary[:120]}**\n"
                    entry += f"   {atom.content[:300]}\n"
                    if atom.tags:
                        entry += f"   Tags: {', '.join(atom.tags[:5])}\n"
                    entry += "\n"
                else:
                    entry = f"{prefix} **{atom.summary[:120]}**"
                    if atom.tags:
                        entry += f" `{' '.join('#' + t for t in atom.tags[:3])}`"
                    entry += "\n\n"

                if _estimate_tokens(entry) > token_budget:
                    lines.append(f"  _(truncated)_\n")
                    token_budget = 0
                    break
                lines.append(entry)
                token_budget -= _estimate_tokens(entry)

            if token_budget <= 0:
                break

        # Trace section
        if self.include_trace and trace and token_budget > 200:
            lines.append("### Relationship Map\n\n")
            shown = set()
            for t in trace:
                if len(shown) >= 5:
                    break
                key = (t.get("from", "")[:8], t.get("to", "")[:8])
                if key in shown:
                    continue
                shown.add(key)
                lines.append(
                    f"- `{t.get('from', '')[:8]}` "
                    f"—[{t.get('edge_label', '?')}]→ "
                    f"`{t.get('to', '')[:8]}` "
                    f"(confidence: {t.get('confidence', 0):.2f})\n"
                )

        lines.append("")
        lines.append("---")
        lines.append("*End of VibeMemory MAC injection*")

        return "\n".join(lines)


# --- MAG: Memory-Augmented Gating (signal) ---

class MAGInjector:
    """
    Gated signal injection for strategy/creative tasks.

    Injects only summaries and key signals, grouped by priority.
    Low token cost, high signal-to-noise ratio.

    "Gating" means: the injection tells the agent what categories of
    memory exist, without overwhelming it with full context. The agent
    can then decide whether to query deeper.

    Args:
        max_tokens: Maximum tokens for injection (default: 1000)
        emphasis: Whether to use priority markers (🔴🟡⚪)
    """

    def __init__(
        self,
        max_tokens: int = 1000,
        emphasis: bool = True,
    ):
        self.max_tokens = max_tokens
        self.emphasis = emphasis

    def build(self, recall_result: dict) -> str:
        """Build MAG gated signal from recall results."""
        atoms = recall_result.get("atoms", [])
        trace = recall_result.get("trace", [])
        mode = recall_result.get("mode", "precision")

        if not atoms:
            return "<!-- VibeMemory MAG: no signals -->\n"

        # Group by priority
        by_priority: dict[str, list[MemoryAtom]] = {
            "high": [], "medium": [], "low": [],
        }
        for atom in atoms:
            p = _atom_priority(atom, trace)
            by_priority[p].append(atom)

        lines = [
            "<!-- VibeMemory MAG: gated signal injection -->",
            "## Memory Signals",
            "",
            "Key signals from previous sessions. "
            "Use these as directional guidance, not as complete context.",
            "",
        ]

        token_budget = self.max_tokens - _estimate_tokens("\n".join(lines))

        sections = [
            ("Critical Context", "high", "These are causally linked or override previous conclusions:"),
            ("Related Experience", "medium", "These are similar patterns or experiences:"),
            ("Background", "low", "These are loosely related context:"),
        ]

        for title, priority, description in sections:
            group = by_priority.get(priority, [])
            if not group:
                continue

            section = f"### {title}\n\n"
            if token_budget < _estimate_tokens(section):
                break
            lines.append(section)
            token_budget -= _estimate_tokens(section)

            if self.emphasis and token_budget > _estimate_tokens(description):
                lines.append(f"_{description}_\n\n")
                token_budget -= _estimate_tokens(description)

            for atom in group:
                # MAG: summary only, 80 chars max
                summary = atom.summary[:80]
                if atom.tags:
                    tag_str = " ".join(f"#{t}" for t in atom.tags[:3])
                    entry = f"- {summary} `{tag_str}`\n"
                else:
                    entry = f"- {summary}\n"

                if _estimate_tokens(entry) > token_budget:
                    lines.append(f"  _(+{len(group) - group.index(atom)} more signals)_\n")
                    token_budget = 0
                    break
                lines.append(entry)
                token_budget -= _estimate_tokens(entry)

            if token_budget <= 0:
                break

        # Quick stats
        total = sum(len(v) for v in by_priority.values())
        lines.append(f"\n_{total} signals total — "
                     f"{len(by_priority['high'])} critical, "
                     f"{len(by_priority['medium'])} related, "
                     f"{len(by_priority['low'])} background_\n")

        lines.append("---")
        lines.append("*End of VibeMemory MAG signals*")

        return "\n".join(lines)


# --- Universal build function ---

def build_injection(
    recall_result: dict,
    mode: str = "mac",
    max_tokens: int = 4000,
    **kwargs,
) -> str:
    """
    Build injection prompt from recall results.

    Args:
        recall_result: Result from VibeMemory.recall()
        mode: "mac" (full context) or "mag" (gated signals)
        max_tokens: Token budget
        **kwargs: Passed to MACInjector or MAGInjector

    Returns:
        Injection prompt string
    """
    if mode == "mac":
        return MACInjector(max_tokens=max_tokens, **kwargs).build(recall_result)
    elif mode == "mag":
        return MAGInjector(max_tokens=max_tokens, **kwargs).build(recall_result)
    else:
        raise ValueError(f"Unknown injection mode: {mode}. Use 'mac' or 'mag'.")