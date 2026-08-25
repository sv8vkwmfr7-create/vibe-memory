"""
VibeMemory MCP Server — Model Context Protocol integration

Exposes VibeMemory as MCP tools for Claude Code, Codex, and any MCP client.
Communicates via JSON-RPC 2.0 over stdio.

Tools:
  - vibe_store: Write a memory atom
  - vibe_recall: Retrieve memories by query
  - vibe_session_start: Start session, recall + inject context
  - vibe_session_end: End session, store summary + highlights
  - vibe_stats: Get memory statistics
  - vibe_link: Create manual edge between atoms
  - vibe_forget: Delete a memory atom
  - vibe_flush: Process LLM edge classification queue

Usage:
  # In Claude Code claude.md or Codex AGENTS.md:
  mcp vibe-memory python -m vibe_memory.mcp_server

  # Or as standalone:
  python -m vibe_memory.mcp_server --db-path .vibe/memory.db --agent-id my-agent
"""

import json
import sys
import os
import uuid
import argparse
from typing import Optional
from datetime import datetime


def run_server(db_path: str, agent_id: str, vibe_dir: str):
    """Run MCP server over stdio."""
    from vibe_memory.sdk import VibeMemory

    mem = VibeMemory(
        agent_id=agent_id,
        db_path=db_path,
        embedding_backend="tfidf",
    )

    session_id: Optional[str] = None
    inject_file = os.path.join(vibe_dir, "inject.md") if vibe_dir else None

    # Keep track of session state
    _state = {}

    def send_response(id, result):
        """Send JSON-RPC response."""
        msg = json.dumps({"jsonrpc": "2.0", "id": id, "result": result}, ensure_ascii=False)
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()

    def send_error(id, code, message):
        """Send JSON-RPC error."""
        msg = json.dumps({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}, ensure_ascii=False)
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()

    def send_notification(method, params):
        """Send JSON-RPC notification."""
        msg = json.dumps({"jsonrpc": "2.0", "method": method, "params": params}, ensure_ascii=False)
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()

    # Tool definitions
    tools = {
        "vibe_store": {
            "description": "Write a memory atom to VibeMemory. Use this to remember important facts, decisions, bug fixes, user preferences, or any information worth recalling across sessions.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The memory content to store"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization (e.g. ['bug', 'api', 'fix'])"},
                    "summary": {"type": "string", "description": "Short summary (auto-generated from content if omitted)"},
                    "session_id": {"type": "string", "description": "Session ID (auto-generated if omitted)"},
                },
                "required": ["content"],
            },
        },
        "vibe_recall": {
            "description": "Retrieve memories from VibeMemory. Use this to recall what happened in previous sessions, find related bug fixes, or understand project context without asking the user to repeat.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "mode": {"type": "string", "enum": ["precision", "recall", "budget"], "description": "Retrieval mode: precision (no noise, top-5), recall (comprehensive, top-15), budget (fast, top-3)"},
                    "top_k": {"type": "integer", "description": "Max seeds for vector pre-screening"},
                },
                "required": ["query"],
            },
        },
        "vibe_session_start": {
            "description": "Start a new VibeMemory session. Recalls relevant memories from previous sessions and prepares context injection. Call this at the beginning of each task or conversation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "What this session is about (used to find relevant past memories)"},
                },
            },
        },
        "vibe_session_end": {
            "description": "End current VibeMemory session. Stores summary and key highlights as memory atoms. Call this when a task is complete or the conversation is ending.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "One-sentence summary of what was accomplished in this session"},
                    "highlights": {"type": "array", "items": {"type": "string"}, "description": "Key discoveries, decisions, or insights from this session"},
                },
            },
        },
        "vibe_stats": {
            "description": "View VibeMemory statistics: total atoms, edges, sessions, and system health.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        "vibe_link": {
            "description": "Create a manual relationship edge between two memory atoms. Use when you discover a causal link, revision, or similarity between two memories.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "from_id": {"type": "string", "description": "Source atom ID (first 8 chars is enough)"},
                    "to_id": {"type": "string", "description": "Target atom ID (first 8 chars is enough)"},
                    "label": {"type": "string", "enum": ["causal", "revision", "similar", "adjacent"], "description": "Relationship type"},
                },
                "required": ["from_id", "to_id", "label"],
            },
        },
        "vibe_forget": {
            "description": "Delete a memory atom. Use when information is outdated, incorrect, or should no longer be remembered.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "atom_id": {"type": "string", "description": "Atom ID to delete"},
                },
                "required": ["atom_id"],
            },
        },
        "vibe_flush": {
            "description": "Process the LLM edge classification queue. If an LLM classifier is configured, this will classify pending cross-session edge candidates.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "max_batch": {"type": "integer", "description": "Max candidates to process"},
                },
            },
        },
    }

    def handle_tool_call(tool_name: str, arguments: dict):
        """Dispatch tool call to VibeMemory SDK."""
        nonlocal session_id

        if tool_name == "vibe_store":
            content = arguments["content"]
            tags = arguments.get("tags", [])
            summary = arguments.get("summary")
            sid = arguments.get("session_id") or session_id
            atom = mem.store(
                content=content,
                tags=tags,
                summary=summary,
                session_id=sid,
                auto_build_edges=False,  # Let client control when to build edges
            )
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "id": atom.id,
                    "summary": atom.summary[:120],
                    "tags": atom.tags,
                    "session_id": atom.session_id[:8],
                    "message": "Memory stored successfully",
                }, ensure_ascii=False)}],
            }

        elif tool_name == "vibe_recall":
            query = arguments["query"]
            mode = arguments.get("mode", "precision")
            top_k = arguments.get("top_k", 20)
            result = mem.recall(query=query, mode=mode, top_k=top_k)

            atoms = result.get("atoms", [])
            trace = result.get("trace", [])

            formatted = []
            for atom in atoms:
                formatted.append({
                    "id": atom.id[:8],
                    "summary": atom.summary[:150],
                    "content": atom.content[:300],
                    "session_id": atom.session_id[:8],
                    "tags": atom.tags,
                })

            return {
                "content": [{"type": "text", "text": json.dumps({
                    "count": len(atoms),
                    "mode": result.get("mode"),
                    "memories": formatted,
                    "relationships": trace[:5],
                }, ensure_ascii=False)}],
            }

        elif tool_name == "vibe_session_start":
            context = arguments.get("context", "")
            result = mem.recall(context, mode="precision", top_k=10)

            session_id = str(uuid.uuid4())
            _state["session_id"] = session_id
            _state["started_at"] = datetime.now().isoformat()
            _state["context"] = context[:500]

            atoms = result.get("atoms", [])

            # Build injection context
            if atoms:
                lines = [
                    "<!-- VibeMemory: recalled from previous sessions -->",
                    "## Context from Previous Sessions",
                    "",
                ]
                for atom in atoms:
                    lines.append(f"- **{atom.summary[:100]}**")
                    if atom.tags:
                        lines.append(f"  Tags: {', '.join(atom.tags[:5])}")
                    lines.append("")
                injection = "\n".join(lines)
            else:
                injection = "<!-- VibeMemory: no relevant memories from previous sessions -->"

            if inject_file:
                os.makedirs(os.path.dirname(inject_file), exist_ok=True)
                with open(inject_file, "w", encoding="utf-8") as f:
                    f.write(injection)

            return {
                "content": [{"type": "text", "text": json.dumps({
                    "session_id": session_id[:8],
                    "memories_recalled": len(atoms),
                    "injection_length": len(injection),
                    "inject_file": inject_file,
                    "message": f"Session started. {len(atoms)} memories recalled from previous sessions.",
                }, ensure_ascii=False)}],
            }

        elif tool_name == "vibe_session_end":
            summary = arguments.get("summary", "")
            highlights = arguments.get("highlights", [])
            sid = session_id or str(uuid.uuid4())

            stored = []
            if summary:
                atom = mem.store(
                    content=summary,
                    session_id=sid,
                    tags=["session-summary"],
                    auto_build_edges=False,
                )
                stored.append({"id": atom.id[:8], "type": "summary"})

            for hl in highlights:
                atom = mem.store(
                    content=hl,
                    session_id=sid,
                    tags=["session-highlight"],
                    auto_build_edges=False,
                )
                stored.append({"id": atom.id[:8], "type": "highlight"})

            _state["ended_at"] = datetime.now().isoformat()
            _state["stored_count"] = len(stored)

            return {
                "content": [{"type": "text", "text": json.dumps({
                    "session_id": sid[:8],
                    "stored": len(stored),
                    "items": stored,
                    "message": f"Session ended. {len(stored)} memories stored.",
                }, ensure_ascii=False)}],
            }

        elif tool_name == "vibe_stats":
            stats = mem.stats()
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "total_atoms": stats["total_atoms"],
                    "active_atoms": stats["active_atoms"],
                    "total_edges": stats["total_edges"],
                    "store_count": stats["store_count"],
                    "recall_count": stats["recall_count"],
                    "embedding_backend": stats["embedding_backend"],
                    "partitions": stats.get("partitions", {}),
                    "edge_labels": stats.get("edge_labels", {}),
                }, ensure_ascii=False)}],
            }

        elif tool_name == "vibe_link":
            from_id = arguments["from_id"]
            to_id = arguments["to_id"]
            label_str = arguments["label"]

            from vibe_memory.models.memory_atom import EdgeLabel

            # Try to resolve short IDs to full IDs
            all_atoms = mem.storage.get_atoms_by_agent(mem.agent_id, tenant_id=mem.tenant_id)
            id_map = {}
            for a in all_atoms:
                id_map[a.id[:8]] = a.id
                id_map[a.id] = a.id

            full_from = id_map.get(from_id, from_id)
            full_to = id_map.get(to_id, to_id)
            label_map = {
                "causal": EdgeLabel.CAUSAL,
                "revision": EdgeLabel.REVISION,
                "similar": EdgeLabel.SIMILAR,
                "adjacent": EdgeLabel.ADJACENT,
            }
            label = label_map.get(label_str, EdgeLabel.SIMILAR)

            edge = mem.link(full_from, full_to, label=label)
            if edge:
                return {
                    "content": [{"type": "text", "text": json.dumps({
                        "id": edge.id[:8],
                        "from": edge.from_atom_id[:8],
                        "to": edge.to_atom_id[:8],
                        "label": edge.label.value,
                        "message": "Edge created successfully",
                    }, ensure_ascii=False)}],
                }
            else:
                return {
                    "content": [{"type": "text", "text": json.dumps({
                        "error": "Failed to create edge. Check atom IDs exist and belong to same tenant.",
                    }, ensure_ascii=False)}],
                }

        elif tool_name == "vibe_forget":
            atom_id = arguments["atom_id"]
            # Try exact match first, then prefix match
            ok = mem.forget(atom_id)
            if not ok:
                # Try to find by prefix
                all_atoms = mem.storage.get_atoms_by_agent(mem.agent_id, tenant_id=mem.tenant_id)
                for a in all_atoms:
                    if a.id.startswith(atom_id):
                        ok = mem.forget(a.id)
                        break
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "deleted": ok,
                    "atom_id": atom_id[:8],
                    "message": "Memory deleted" if ok else "Memory not found",
                }, ensure_ascii=False)}],
            }

        elif tool_name == "vibe_flush":
            max_batch = arguments.get("max_batch")
            n = mem.flush_index(max_batch=max_batch)
            return {
                "content": [{"type": "text", "text": json.dumps({
                    "edges_created": n,
                    "message": f"Flushed index: {n} edges created",
                }, ensure_ascii=False)}],
            }

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    # --- Main loop: read JSON-RPC from stdin ---
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            send_response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "vibe-memory",
                    "version": "0.3.0",
                },
            })

        elif method == "notifications/initialized":
            # No response needed for notifications
            pass

        elif method == "tools/list":
            send_response(req_id, {
                "tools": [
                    {
                        "name": name,
                        "description": info["description"],
                        "inputSchema": info["inputSchema"],
                    }
                    for name, info in tools.items()
                ],
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name not in tools:
                send_error(req_id, -32601, f"Unknown tool: {tool_name}")
                continue

            try:
                result = handle_tool_call(tool_name, arguments)
                send_response(req_id, result)
            except Exception as e:
                send_error(req_id, -32000, f"Tool error: {e}")

        elif method == "ping":
            send_response(req_id, {})

        else:
            send_error(req_id, -32601, f"Unknown method: {method}")


def main():
    parser = argparse.ArgumentParser(description="VibeMemory MCP Server")
    parser.add_argument("--db-path", default=".vibe/memory.db", help="SQLite database path")
    parser.add_argument("--agent-id", default="mcp-agent", help="Agent identifier")
    parser.add_argument("--vibe-dir", default=".vibe", help="Vibe state directory")
    args = parser.parse_args()

    run_server(
        db_path=args.db_path,
        agent_id=args.agent_id,
        vibe_dir=args.vibe_dir,
    )


if __name__ == "__main__":
    main()