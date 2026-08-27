"""
Reflect — Cross-memory reasoning for VibeMemory

Periodically analyzes stored memories using an LLM to generate new
insights, discover patterns, and form connections between memories.
Inspired by Hindsight's reflect operation.

Usage:
    from vibe_memory.reflect import Reflector
    from vibe_memory.llm import OpenAIProvider

    reflector = Reflector(
        memory=mem,
        provider=OpenAIProvider(api_key="sk-xxx", model="gpt-4o-mini"),
    )
    insights = reflector.reflect("What patterns do you see in recent bugs?")
    # → [MemoryAtom, ...] new insights stored as atoms

    # Or auto-reflect on recent activity
    reflector.auto_reflect(since_hours=24)
"""

import json
from typing import Optional
from datetime import datetime, timedelta

from vibe_memory.models.memory_atom import MemoryAtom, Lifecycle, GraphPartition


REFLECT_SYSTEM_PROMPT = """You are a memory analyst. You will be given a set of memory atoms from an AI agent's conversation history. Your job is to analyze them and generate insights.

## What to Look For

1. **Patterns**: recurring themes, bugs, or user preferences across sessions
2. **Causal chains**: sequences of events where A led to B led to C
3. **Contradictions**: memories that conflict with each other
4. **Gaps**: missing information or unanswered questions
5. **Decisions**: key decisions and their rationale
6. **Risks**: potential issues or technical debt mentioned

## Output Format

Respond with JSON only:
{
  "insights": [
    {
      "type": "pattern|causal|contradiction|gap|decision|risk",
      "summary": "one-sentence insight",
      "detail": "2-3 sentence explanation",
      "confidence": 0.0-1.0,
      "related_atom_ids": ["id1", "id2"]
    }
  ]
}

If no meaningful insights are found, respond with {"insights": []}."""


class Reflector:
    """
    Cross-memory reasoning engine.

    Args:
        memory: VibeMemory instance
        provider: LLM provider (OpenAI, Anthropic, or any OpenAI-compatible)
        max_atoms_per_reflect: Max atoms to analyze per call (default 50)
        auto_store: Store insights as memory atoms (default True)
    """

    def __init__(
        self,
        memory,
        provider,
        max_atoms_per_reflect: int = 50,
        auto_store: bool = True,
    ):
        self.memory = memory
        self.provider = provider
        self.max_atoms_per_reflect = max_atoms_per_reflect
        self.auto_store = auto_store
        self._reflect_count = 0
        self._insight_count = 0

    def reflect(
        self,
        prompt: Optional[str] = None,
        since_hours: Optional[int] = None,
        top_k: Optional[int] = None,
        custom_prompt: Optional[str] = None,
    ) -> list[MemoryAtom]:
        """
        Analyze memories and generate insights.

        Args:
            prompt: What to reflect on (e.g. "What patterns in recent bugs?")
            since_hours: Only analyze memories from last N hours
            top_k: Max memories to analyze (default: max_atoms_per_reflect)
            custom_prompt: Override the system prompt

        Returns:
            List of insight MemoryAtoms stored (empty if nothing found)
        """
        # Get recent memories
        atoms = self._get_recent_atoms(since_hours=since_hours, top_k=top_k or self.max_atoms_per_reflect)

        if len(atoms) < 3:
            return []  # Not enough to reflect on

        # Build reflection prompt
        system_prompt = custom_prompt or REFLECT_SYSTEM_PROMPT
        user_prompt = self._build_reflection_prompt(atoms, prompt)

        # Call LLM
        try:
            result = self.provider.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            parsed = self._parse_reflection(result["content"])
        except Exception as e:
            return []

        self._reflect_count += 1

        # Store insights
        stored = []
        if self.auto_store and parsed.get("insights"):
            for insight in parsed["insights"]:
                atom = self._store_insight(insight)
                if atom:
                    stored.append(atom)
                    self._insight_count += 1

        return stored

    def auto_reflect(self, since_hours: int = 24) -> list[MemoryAtom]:
        """
        Auto-reflect on recent activity. No custom prompt needed.

        Args:
            since_hours: Analyze memories from last N hours

        Returns:
            Insight atoms
        """
        return self.reflect(
            prompt="Analyze recent memories and identify patterns, causal chains, and risks.",
            since_hours=since_hours,
        )

    def reflect_on_topic(self, topic: str, top_k: int = 50) -> list[MemoryAtom]:
        """Reflect on a specific topic."""
        # Search for relevant memories first
        result = self.memory.recall(topic, mode="recall", top_k=top_k)
        atoms = result.get("atoms", [])

        if len(atoms) < 3:
            return []

        user_prompt = self._build_reflection_prompt(atoms, f"Analyze these memories about '{topic}'.")
        try:
            result = self.provider.chat(
                messages=[
                    {"role": "system", "content": REFLECT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            parsed = self._parse_reflection(result["content"])
        except Exception:
            return []

        stored = []
        if self.auto_store and parsed.get("insights"):
            for insight in parsed["insights"]:
                atom = self._store_insight(insight)
                if atom:
                    stored.append(atom)

        return stored

    def stats(self) -> dict:
        return {
            "reflect_count": self._reflect_count,
            "insight_count": self._insight_count,
            "auto_store": self.auto_store,
        }

    # ── Internal ──

    def _get_recent_atoms(
        self,
        since_hours: Optional[int] = None,
        top_k: int = 50,
    ) -> list[MemoryAtom]:
        """Get recent memory atoms."""
        atoms = self.memory.storage.get_atoms_by_agent(
            self.memory.agent_id,
            tenant_id=self.memory.tenant_id,
        )
        active = [a for a in atoms if a.lifecycle.value in ("active", "warm")]

        if since_hours:
            cutoff = datetime.now() - timedelta(hours=since_hours)
            active = [a for a in active if hasattr(a, 'created_at') and a.created_at and a.created_at >= cutoff]

        # Sort by recency
        active.sort(key=lambda a: a.created_at if hasattr(a, 'created_at') and a.created_at else datetime.min, reverse=True)
        return active[:top_k]

    def _build_reflection_prompt(
        self,
        atoms: list[MemoryAtom],
        prompt: Optional[str] = None,
    ) -> str:
        """Build the user prompt for reflection."""
        lines = [
            f"Analyze the following {len(atoms)} memory atoms from an AI agent's history.",
            "",
        ]

        if prompt:
            lines.append(f"Focus on: {prompt}")
            lines.append("")

        lines.append("## Memories")
        lines.append("")

        for i, atom in enumerate(atoms, 1):
            lines.append(f"### {i}. [{atom.id[:8]}] {atom.summary[:120]}")
            lines.append(f"Session: {atom.session_id[:8] if hasattr(atom, 'session_id') else 'unknown'}")
            lines.append(f"Content: {atom.content[:300]}")
            if atom.tags:
                lines.append(f"Tags: {', '.join(atom.tags[:5])}")
            lines.append("")

        return "\n".join(lines)

    def _parse_reflection(self, content: str) -> dict:
        """Parse LLM reflection response."""
        # Try direct JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try ```json code block
        import re
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try first { ... }
        match = re.search(r'\{[^{}]*"insights"[^{}]*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {"insights": []}

    def _store_insight(self, insight: dict) -> Optional[MemoryAtom]:
        """Store an insight as a memory atom."""
        try:
            return self.memory.store(
                content=f"[{insight.get('type', 'insight').upper()}] {insight.get('detail', insight.get('summary', ''))}",
                summary=insight.get("summary", "")[:200],
                tags=["reflect", insight.get("type", "insight")],
                auto_build_edges=False,
            )
        except Exception:
            return None


# ── Convenience ──

def create_reflector(
    memory,
    provider_type: str = "openai",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "gpt-4o-mini",
    **kwargs,
) -> Reflector:
    """
    Create a Reflector with zero-config provider setup.

    Args:
        memory: VibeMemory instance
        provider_type: "openai", "anthropic", or "deepseek"
        api_key: API key (uses env var if not set)
        base_url: API base URL
        model: Model name
        **kwargs: Passed to Reflector

    Returns:
        Configured Reflector instance
    """
    from vibe_memory.llm.provider import create_provider

    provider_params = {"model": model}
    if api_key:
        provider_params["api_key"] = api_key
    if base_url:
        provider_params["base_url"] = base_url

    provider = create_provider(provider_type, **provider_params)
    return Reflector(memory=memory, provider=provider, **kwargs)