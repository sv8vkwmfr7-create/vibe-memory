"""
VibeMemory LangChain Memory Adapter

Drop-in BaseMemory implementation for LangChain/LangGraph agents.
Works with any LangChain chain or agent that accepts a memory object.

Usage:
    from vibe_memory.langchain import VibeMemoryLC

    memory = VibeMemoryLC(agent_id="my-agent", db_path="memory.db")
    memory.save_context(
        {"input": "API timeout bug"},
        {"output": "Fixed by changing timeout from 30s to 60s"},
    )
    variables = memory.load_memory_variables({"query": "API timeout"})
    # → {"history": "Fixed API timeout by changing from 30s to 60s..."}
"""

import json
from typing import Any, Optional
from datetime import datetime

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel, EdgeSource


class VibeMemoryLC:
    """
    LangChain-compatible memory adapter.

    Implements the BaseMemory interface: save_context, load_memory_variables, clear.
    Uses VibeMemory's PPR graph retrieval under the hood.

    Args:
        agent_id: Agent identifier
        db_path: SQLite database path
        embedding_backend: Vectorization backend
        max_tokens: Max tokens returned in memory context
        recall_mode: PPR retrieval mode (precision/recall/budget)
    """

    def __init__(
        self,
        agent_id: str = "langchain-agent",
        db_path: str = ":memory:",
        embedding_backend: str = "tfidf",
        max_tokens: int = 4000,
        recall_mode: str = "precision",
    ):
        self.mem = VibeMemory(
            agent_id=agent_id,
            db_path=db_path,
            embedding_backend=embedding_backend,
        )
        self.max_tokens = max_tokens
        self.recall_mode = recall_mode
        self._session_id: Optional[str] = None
        self._input_key = "input"
        self._output_key = "output"
        self._memory_key = "history"

    # ── LangChain BaseMemory interface ──

    @property
    def memory_variables(self) -> list[str]:
        return [self._memory_key]

    def save_context(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None:
        """
        Store conversation turn as memory atoms.

        Creates two atoms: one for the input (user query) and one for
        the output (agent response), linked by an adjacent edge.
        """
        if not self._session_id:
            import uuid
            self._session_id = str(uuid.uuid4())

        input_text = str(inputs.get(self._input_key, inputs.get("input", "")))
        output_text = str(outputs.get(self._output_key, outputs.get("output", "")))

        if not input_text and not output_text:
            return

        # Store user input
        input_atom = None
        if input_text:
            input_atom = self.mem.store(
                content=input_text,
                session_id=self._session_id,
                tags=["user-input"],
                auto_build_edges=False,
            )

        # Store agent output
        output_atom = None
        if output_text:
            output_atom = self.mem.store(
                content=output_text,
                session_id=self._session_id,
                tags=["agent-output"],
                auto_build_edges=False,
            )

        # Link input → output as adjacent
        if input_atom and output_atom:
            self.mem.link(
                input_atom.id,
                output_atom.id,
                label=EdgeLabel.ADJACENT,
                source=EdgeSource.RULE,
            )

    def load_memory_variables(
        self,
        inputs: dict[str, Any],
    ) -> dict[str, str]:
        """
        Recall relevant memories for the current input.

        Searches all stored memories using PPR graph retrieval.
        """
        query = str(inputs.get(self._input_key, inputs.get("input", "")))
        if not query:
            query = str(inputs.get("query", ""))

        if not query:
            return {self._memory_key: ""}

        result = self.mem.recall(query, mode=self.recall_mode, top_k=10)
        atoms = result.get("atoms", [])

        if not atoms:
            return {self._memory_key: ""}

        # Build context
        lines = ["## Past Conversations (from memory)"]
        char_budget = self.max_tokens * 4

        for atom in atoms:
            entry = f"- {atom.summary[:120]}"
            if atom.tags:
                entry += f" [{', '.join(atom.tags[:3])}]"
            if len("\n".join(lines)) + len(entry) > char_budget:
                lines.append(f"  _(+{len(atoms) - atoms.index(atom)} more memories)_")
                break
            lines.append(entry)

        return {self._memory_key: "\n".join(lines)}

    def clear(self) -> None:
        """Clear all memories for this agent."""
        atoms = self.mem.storage.get_atoms_by_agent(self.mem.agent_id)
        for a in atoms:
            self.mem.forget(a.id)
        self._session_id = None

    # ── Extended API ──

    def start_session(self, context: str = "") -> dict:
        """Start a new session and recall relevant memories."""
        import uuid
        self._session_id = str(uuid.uuid4())
        result = self.mem.recall(context or "general", mode=self.recall_mode)
        return {
            "session_id": self._session_id,
            "memories_recalled": len(result.get("atoms", [])),
            "memories": [
                {"id": a.id[:8], "summary": a.summary[:100]}
                for a in result.get("atoms", [])
            ],
        }

    def end_session(self, summary: str = "", highlights: list[str] = None) -> dict:
        """End session and store summary."""
        sid = self._session_id or ""
        stored = []
        if summary:
            atom = self.mem.store(content=summary, session_id=sid,
                                  tags=["session-summary"], auto_build_edges=False)
            stored.append(atom.id[:8])
        for hl in (highlights or []):
            atom = self.mem.store(content=hl, session_id=sid,
                                  tags=["session-highlight"], auto_build_edges=False)
            stored.append(atom.id[:8])
        return {"session_id": sid[:8], "stored": len(stored)}


# Alias for LangChain import
VibeMemoryMemory = VibeMemoryLC