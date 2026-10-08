"""
VibeMemory OpenAI Agents SDK Adapter

Plain memory functions for optional OpenAI Agents SDK integration (openai-agents).
Wrap them with function_tool before passing them to Agent; the factory itself
does not import the Agents SDK or return FunctionTool objects.

Usage:
    from agents import Agent, function_tool
    from vibe_memory import VibeMemory
    from vibe_memory.openai_agents import create_vibe_tools

    with VibeMemory("my-agent", "memory.db", embedding_backend="tfidf") as memory:
        functions = create_vibe_tools(memory=memory)
        tools = [function_tool(fn) for fn in functions]
        agent = Agent(
            name="Assistant",
            instructions="You have memory. Use vibe_store and vibe_recall.",
            tools=tools,
        )
        # Complete the Agent/Runner workflow before leaving this context.
"""

import json
import uuid
from typing import Optional
from datetime import datetime

from vibe_memory import VibeMemory


def create_vibe_tools(
    agent_id: str = "openai-agent",
    db_path: str = ":memory:",
    embedding_backend: str = "tfidf",
    *,
    memory: Optional[VibeMemory] = None,
):
    """
    Create VibeMemory tools for OpenAI Agents SDK.

    Returns a list of plain Python functions. With openai-agents installed,
    wrap each using agents.function_tool before passing the result to Agent().
    Direct function calls remain supported without the framework dependency.

    memory: Optional caller-owned SDK. Its agent/database/backend are used;
    do not combine it with non-default construction options. The caller must
    keep it open for the entire tool workflow and close it afterwards. The
    factory neither closes nor flushes a borrowed SDK. Without memory, legacy
    construction remains supported but the returned list has no close handle.

    Tools:
      - vibe_store(content, tags, summary, session_id)
      - vibe_recall(query, mode, top_k)
      - vibe_session_start(context)
      - vibe_session_end(summary, highlights)
      - vibe_stats()
      - vibe_link(from_id, to_id, label)
      - vibe_forget(atom_id)
    """
    from vibe_memory.models.memory_atom import EdgeLabel

    if memory is not None and (agent_id != "openai-agent" or db_path != ":memory:"
                               or embedding_backend != "tfidf"):
        raise ValueError("memory cannot be combined with non-default construction options")
    mem = memory if memory is not None else VibeMemory(
        agent_id=agent_id,
        db_path=db_path,
        embedding_backend=embedding_backend,
    )

    _session_id: Optional[str] = None

    # Tool implementations as plain functions (compatible with @function_tool)
    def vibe_store(
        content: str,
        tags: Optional[list[str]] = None,
        summary: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Write a memory atom. Use this to remember important facts, decisions, bug fixes, or user preferences."""
        atom = mem.store(
            content=content,
            tags=tags or [],
            summary=summary,
            session_id=session_id or _session_id,
            auto_build_edges=False,
        )
        return json.dumps({
            "id": atom.id[:8],
            "full_id": atom.id,
            "summary": atom.summary[:100],
            "tags": atom.tags,
            "status": "stored",
        }, ensure_ascii=False)

    def vibe_recall(
        query: str,
        mode: str = "precision",
        top_k: int = 20,
    ) -> str:
        """Retrieve memories. Use 'precision' for exact match, 'recall' for comprehensive, 'budget' for fast."""
        result = mem.recall(query=query, mode=mode, top_k=top_k)
        atoms = result.get("atoms", [])
        return json.dumps({
            "count": len(atoms),
            "memories": [
                {"id": a.id[:8], "full_id": a.id, "summary": a.summary[:120], "tags": a.tags}
                for a in atoms
            ],
        }, ensure_ascii=False)

    def vibe_session_start(context: str = "") -> str:
        """Start a new session. Recalls relevant memories from previous sessions."""
        nonlocal _session_id
        result = mem.recall(context or "general", mode="precision", top_k=10)
        _session_id = str(uuid.uuid4())
        return json.dumps({
            "session_id": _session_id[:8],
            "memories_recalled": len(result.get("atoms", [])),
        }, ensure_ascii=False)

    def vibe_session_end(
        summary: str = "",
        highlights: Optional[list[str]] = None,
    ) -> str:
        """End current session. Stores summary and key highlights."""
        sid = _session_id or str(uuid.uuid4())
        stored = 0
        if summary:
            mem.store(content=summary, session_id=sid, tags=["session-summary"], auto_build_edges=False)
            stored += 1
        for hl in (highlights or []):
            mem.store(content=hl, session_id=sid, tags=["session-highlight"], auto_build_edges=False)
            stored += 1
        return json.dumps({"session_id": sid[:8], "stored": stored}, ensure_ascii=False)

    def vibe_stats() -> str:
        """View memory statistics."""
        stats = mem.stats()
        return json.dumps({
            "total_atoms": stats["total_atoms"],
            "total_edges": stats["total_edges"],
            "active_atoms": stats["active_atoms"],
        }, ensure_ascii=False)

    def vibe_link(from_id: str, to_id: str, label: str = "similar") -> str:
        """Create a relationship edge between two memories. label: causal/revision/similar/adjacent."""
        label_map = {
            "causal": EdgeLabel.CAUSAL, "revision": EdgeLabel.REVISION,
            "similar": EdgeLabel.SIMILAR, "adjacent": EdgeLabel.ADJACENT,
        }
        # Exact IDs take precedence; display prefixes must be unique in this owner scope.
        all_atoms = mem.storage.get_atoms_by_agent(mem.agent_id, tenant_id=mem.tenant_id)
        id_map = {a.id: a.id for a in all_atoms}
        for atom_id in (from_id, to_id):
            if atom_id in id_map or len(atom_id) != 8:
                continue
            # ponytail: scoped linear scan; index if link lookup becomes costly.
            matches = [a.id for a in all_atoms if a.id.startswith(atom_id)]
            if len(matches) > 1:
                return json.dumps({"error": "Ambiguous atom ID prefix; use full IDs"})
            if matches:
                id_map[atom_id] = matches[0]
        edge = mem.link(id_map.get(from_id, from_id), id_map.get(to_id, to_id),
                        label=label_map.get(label, EdgeLabel.SIMILAR))
        if edge:
            return json.dumps({"id": edge.id[:8], "label": edge.label.value, "status": "created"}, ensure_ascii=False)
        return json.dumps({"error": "Failed to create edge"}, ensure_ascii=False)

    def vibe_forget(atom_id: str) -> str:
        """Delete a memory atom."""
        ok = mem.forget(atom_id)
        return json.dumps({"deleted": ok}, ensure_ascii=False)

    return [
        vibe_store, vibe_recall, vibe_session_start, vibe_session_end,
        vibe_stats, vibe_link, vibe_forget,
    ]
