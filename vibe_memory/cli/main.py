"""
VibeSession CLI — VibeMemory session management

Usage:
    # Start a new session (recalls memories, writes injection)
    vibe-session start

    # Start with context
    vibe-session start --context "Working on API timeout bug"

    # End session and store summary
    vibe-session end --summary "Fixed API timeout by increasing to 60s"

    # End with highlights
    vibe-session end --summary "Refactored auth module" --highlight "JWT expiry extended" --highlight "Rate limit bypass fixed"

    # Ad-hoc recall
    vibe-session recall "API timeout"

    # View stats
    vibe-session stats

    # Inject context into current shell
    eval $(vibe-session inject)

Config:
    Default: .vibe/ directory, agent_id="claude-code"
    Override: VIBE_AGENT_ID env var, VIBE_DIR env var
"""

import sys
import os
import argparse
from pathlib import Path


def get_vibe_dir() -> str:
    """Get Vibe directory from env or default."""
    return os.environ.get("VIBE_DIR", ".vibe")


def get_agent_id() -> str:
    """Get agent ID from env or default."""
    return os.environ.get("VIBE_AGENT_ID", "claude-code")


def cmd_start(args):
    """Start a new session."""
    from vibe_memory.cli.session_manager import SessionManager

    mgr = SessionManager(
        agent_id=get_agent_id(),
        vibe_dir=get_vibe_dir(),
    )
    result = mgr.start_session(context=args.context)

    print(f"Session started: {result['session_id'][:8]}...")
    print(f"Previous: {result['previous_session_id'] or 'none'}")
    print(f"Memories recalled: {result['memories_count']}")
    print(f"Injection file: {result['inject_file']} ({result['injection_length']} chars)")
    print(f"\nTip: cat {result['inject_file']} to see context")


def cmd_end(args):
    """End current session."""
    from vibe_memory.cli.session_manager import SessionManager

    mgr = SessionManager(
        agent_id=get_agent_id(),
        vibe_dir=get_vibe_dir(),
    )
    result = mgr.end_session(
        summary=args.summary,
        highlights=args.highlight,
        tags=args.tag,
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Session ended: {result['session_id'][:8]}...")
    print(f"Memories stored: {result['stored_count']}")


def cmd_recall(args):
    """Ad-hoc memory recall."""
    from vibe_memory.cli.session_manager import SessionManager

    mgr = SessionManager(
        agent_id=get_agent_id(),
        vibe_dir=get_vibe_dir(),
    )
    result = mgr.recall(args.query, mode=args.mode)

    atoms = result.get("atoms", [])
    if not atoms:
        print("No memories found.")
        return

    print(f"Found {len(atoms)} memories (mode: {result['mode']}):\n")
    for i, atom in enumerate(atoms, 1):
        tags = " ".join(f"#{t}" for t in atom.tags[:3]) if atom.tags else ""
        print(f"  {i}. [{atom.session_id[:8]}] {atom.summary[:120]}")
        if tags:
            print(f"     {tags}")
        print()


def cmd_stats(args):
    """View stats."""
    from vibe_memory.cli.session_manager import SessionManager

    mgr = SessionManager(
        agent_id=get_agent_id(),
        vibe_dir=get_vibe_dir(),
    )
    stats = mgr.stats()

    session = stats.get("session", {})
    memory = stats.get("memory", {})

    print("Session:")
    print(f"  ID:        {session.get('session_id', 'none')[:16] if session.get('session_id') else 'none'}")
    print(f"  Previous:  {session.get('previous_session_id', 'none')}")
    print(f"  Started:   {session.get('started_at', 'none')}")
    print(f"  Ended:     {session.get('ended_at', 'none')}")

    print("\nMemory:")
    print(f"  Atoms:     {memory.get('total_atoms', 0)} "
          f"(active: {memory.get('active_atoms', 0)}, "
          f"warm: {memory.get('warm_atoms', 0)}, "
          f"cold: {memory.get('cold_atoms', 0)})")
    print(f"  Edges:     {memory.get('total_edges', 0)}")
    print(f"  Stores:    {memory.get('store_count', 0)}")
    print(f"  Recalls:   {memory.get('recall_count', 0)}")
    print(f"  Embedding: {memory.get('embedding_backend', 'unknown')}")

    if memory.get("partitions"):
        print(f"  Partitions: {memory['partitions']}")

    if memory.get("indexer"):
        idx = memory["indexer"]
        print(f"\n  Indexer:")
        print(f"    Queue:    {idx['queue_size']}/{idx['max_queue_size']}")
        print(f"    Enqueued: {idx['enqueued_count']}")
        print(f"    Processed:{idx['processed_count']}")
        print(f"    Edges:    {idx['edges_created']}")


def cmd_inject(args):
    """Output injection file path for shell eval."""
    vibe_dir = Path(get_vibe_dir())
    inject_file = vibe_dir / "inject.md"

    if inject_file.exists():
        print(inject_file.read_text(encoding="utf-8"))
    else:
        print("<!-- VibeMemory: no context to inject -->")


def main():
    parser = argparse.ArgumentParser(
        description="VibeMemory Session Manager",
        prog="vibe-session",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # start
    p_start = sub.add_parser("start", help="Start a new session")
    p_start.add_argument("--context", "-c", type=str, help="Context for recall")

    # end
    p_end = sub.add_parser("end", help="End current session")
    p_end.add_argument("--summary", "-s", type=str, help="Session summary")
    p_end.add_argument("--highlight", "-H", action="append", help="Highlight (repeatable)")
    p_end.add_argument("--tag", "-t", action="append", help="Tag (repeatable)")

    # recall
    p_recall = sub.add_parser("recall", help="Ad-hoc memory recall")
    p_recall.add_argument("query", type=str, help="Search query")
    p_recall.add_argument("--mode", "-m", type=str, default="precision",
                          choices=["precision", "recall", "budget"])

    # stats
    sub.add_parser("stats", help="View session and memory stats")

    # inject
    sub.add_parser("inject", help="Output injection context")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "end":
        cmd_end(args)
    elif args.command == "recall":
        cmd_recall(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "inject":
        cmd_inject(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()