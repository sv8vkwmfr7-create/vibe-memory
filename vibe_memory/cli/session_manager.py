"""
Session Manager — VibeMemory + Claude Code integration

Manages session lifecycle for real agent sessions:
  - start: recall relevant memories, prepare context injection
  - end: summarize session, store key memories
  - recall: ad-hoc memory retrieval

Files:
  .vibe/
  ├── session.json          ← current session state
  ├── inject.md             ← context to inject into next prompt
  └── memory.db             ← SQLite database (if using file-based)

Usage:
    from vibe_memory.cli.session_manager import SessionManager

    mgr = SessionManager(agent_id="claude-code", db_path=".vibe/memory.db")
    mgr.start_session()
    # ... agent works ...
    mgr.end_session(conversation_summary="Fixed API timeout bug")
"""

import os
import json
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

from vibe_memory.sdk import VibeMemory


class SessionManager:
    """
    Session lifecycle manager for VibeMemory + Claude Code.

    Args:
        agent_id: Agent identifier (e.g. "claude-code")
        vibe_dir: Directory for Vibe state files (default: ".vibe/")
        db_path: SQLite database path (default: "{vibe_dir}/memory.db")
        embedding_backend: Vectorization backend
        max_context_chars: Max characters for injected context
    """

    def __init__(
        self,
        agent_id: str,
        vibe_dir: str = ".vibe",
        db_path: Optional[str] = None,
        embedding_backend: str = "tfidf",
        max_context_chars: int = 8000,
    ):
        self.agent_id = agent_id
        self.vibe_dir = Path(vibe_dir)
        self.vibe_dir.mkdir(parents=True, exist_ok=True)
        self.max_context_chars = max_context_chars

        db = db_path or str(self.vibe_dir / "memory.db")

        self.mem = VibeMemory(
            agent_id=agent_id,
            db_path=db,
            embedding_backend=embedding_backend,
        )

        self.session_file = self.vibe_dir / "session.json"
        self.inject_file = self.vibe_dir / "inject.md"

    # --- Session Lifecycle ---

    def start_session(
        self,
        context: Optional[str] = None,
    ) -> dict:
        """
        Start a new session.

        1. Reads previous session info (if any)
        2. Recalls relevant memories based on context
        3. Writes injection file for Claude Code to read
        4. Creates new session entry

        Args:
            context: Optional context string (e.g. CLAUDE.md content, user's first message)

        Returns:
            {session_id, previous_session_id, memories_count, ...}
        """
        previous = self._read_session_state()

        # Build recall query from context
        recall_query = self._build_recall_query(context, previous)

        # Recall relevant memories
        recall_result = self.mem.recall(recall_query, mode="precision", top_k=10)

        # Generate injection context
        injection = self._build_injection(recall_result, previous)

        # Write injection file
        self.inject_file.write_text(injection, encoding="utf-8")

        # Create new session
        session_id = str(uuid.uuid4())
        state = {
            "session_id": session_id,
            "previous_session_id": previous.get("session_id"),
            "started_at": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "context": context[:500] if context else "",
            "memories_recalled": len(recall_result.get("atoms", [])),
        }
        self._write_session_state(state)

        return {
            "session_id": session_id,
            "previous_session_id": previous.get("session_id"),
            "memories_count": len(recall_result.get("atoms", [])),
            "inject_file": str(self.inject_file),
            "injection_length": len(injection),
        }

    def end_session(
        self,
        summary: Optional[str] = None,
        highlights: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
    ) -> dict:
        """
        End current session and store key memories.

        Args:
            summary: Session summary (1-2 sentences)
            highlights: Key highlights/bullet points
            tags: Manual tags for the session

        Returns:
            {stored_count, session_id, ...}
        """
        state = self._read_session_state()
        session_id = state.get("session_id", "")

        if not session_id:
            return {"stored_count": 0, "error": "No active session"}

        stored = []

        # Store summary as a memory atom
        if summary:
            atom = self.mem.store(
                content=summary,
                session_id=session_id,
                tags=tags or ["session-summary"],
                auto_build_edges=False,
            )
            stored.append(atom)

        # Store highlights as individual atoms
        if highlights:
            for hl in highlights:
                atom = self.mem.store(
                    content=hl,
                    session_id=session_id,
                    tags=tags or ["session-highlight"],
                    auto_build_edges=False,
                )
                stored.append(atom)

        # Mark session as ended
        state["ended_at"] = datetime.now().isoformat()
        state["stored_count"] = len(stored)
        self._write_session_state(state)

        return {
            "session_id": session_id,
            "stored_count": len(stored),
            "ended_at": state["ended_at"],
        }

    # --- Ad-hoc Recall ---

    def recall(self, query: str, mode: str = "precision") -> dict:
        """
        Ad-hoc memory recall.

        Args:
            query: Search query
            mode: "precision" | "recall" | "budget"

        Returns:
            {atoms, trace, mode, total_walked, ...}
        """
        return self.mem.recall(query, mode=mode)

    # --- Stats ---

    def stats(self) -> dict:
        """Get session and memory stats."""
        session_state = self._read_session_state()
        mem_stats = self.mem.stats()
        return {
            "session": session_state,
            "memory": mem_stats,
        }

    # --- Internal ---

    def _read_session_state(self) -> dict:
        """Read current session state."""
        if self.session_file.exists():
            try:
                return json.loads(self.session_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {}

    def _write_session_state(self, state: dict) -> None:
        """Write session state to file."""
        self.session_file.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _build_recall_query(
        self,
        context: Optional[str],
        previous: dict,
    ) -> str:
        """Build recall query from context and previous session."""
        parts = []

        if context:
            parts.append(context[:1000])

        if previous.get("context"):
            parts.append(previous["context"][:500])

        if not parts:
            parts.append("general context")

        return " ".join(parts)

    def _build_injection(
        self,
        recall_result: dict,
        previous: dict,
    ) -> str:
        """Build injection context from recall results."""
        atoms = recall_result.get("atoms", [])
        if not atoms:
            return "<!-- VibeMemory: no relevant memories found -->\n"

        lines = [
            "<!-- VibeMemory: auto-injected context from previous sessions -->",
            "## Context from Previous Sessions",
            "",
            "The following memories were recalled from previous sessions. "
            "Use this context to understand the user's history and preferences "
            "without requiring them to repeat information.",
            "",
        ]

        # Group by session for readability
        by_session: dict[str, list] = {}
        for atom in atoms:
            sid = atom.session_id[:8] if atom.session_id else "unknown"
            by_session.setdefault(sid, []).append(atom)

        total_chars = sum(len(l) for l in lines)

        for sid, session_atoms in by_session.items():
            header = f"### Session {sid}\n\n"
            if total_chars + len(header) > self.max_context_chars:
                break

            lines.append(header)
            total_chars += len(header)

            for atom in session_atoms:
                entry = f"- **{atom.summary[:100]}**"
                if atom.tags:
                    entry += f" `{' '.join('#' + t for t in atom.tags[:3])}`"
                entry += "\n"

                if total_chars + len(entry) > self.max_context_chars:
                    lines.append(f"  _(truncated, {len(atoms)} total memories)_\n")
                    return "\n".join(lines)

                lines.append(entry)
                total_chars += len(entry)

        lines.append("")
        lines.append("---")
        lines.append("*End of VibeMemory context injection*")

        return "\n".join(lines)


# --- Convenience Functions ---

def quick_start(
    agent_id: str = "claude-code",
    vibe_dir: str = ".vibe",
    context: Optional[str] = None,
) -> SessionManager:
    """Quick start: create manager and start session."""
    mgr = SessionManager(agent_id=agent_id, vibe_dir=vibe_dir)
    result = mgr.start_session(context=context)
    return mgr


def quick_end(
    agent_id: str = "claude-code",
    vibe_dir: str = ".vibe",
    summary: Optional[str] = None,
) -> dict:
    """Quick end: end session and store summary."""
    mgr = SessionManager(agent_id=agent_id, vibe_dir=vibe_dir)
    return mgr.end_session(summary=summary)