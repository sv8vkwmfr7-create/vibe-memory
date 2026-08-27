"""
VibeMemory Init — Auto-detect and configure coding agents

Detects the current environment and auto-configures VibeMemory
for Claude Code, Codex, Cursor, and other AI coding assistants.

Usage:
    vibe-memory init              # Auto-detect all agents
    vibe-memory init --agent claude-code  # Configure specific agent
    vibe-memory init --dry-run    # Show what would be done, don't write

Adds after `vibe-http` in pyproject.toml [project.scripts]:
    vibe-init = "vibe_memory.init:main"
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional


class AgentDetector:
    """Detect and configure AI coding assistants."""

    def __init__(self, vibe_dir: str = ".vibe", db_path: Optional[str] = None):
        self.vibe_dir = Path(vibe_dir)
        self.db_path = db_path or str(self.vibe_dir / "memory.db")
        self.cwd = Path.cwd()

    def detect_all(self) -> dict[str, bool]:
        """Detect which agents are available in the current project."""
        return {
            "claude-code": self._detect_claude_code(),
            "codex": self._detect_codex(),
            "cursor": self._detect_cursor(),
            "github-copilot": self._detect_copilot(),
        }

    def _detect_claude_code(self) -> bool:
        return (self.cwd / "CLAUDE.md").exists() or (self.cwd / ".claude").exists()

    def _detect_codex(self) -> bool:
        return (self.cwd / "AGENTS.md").exists() or (self.cwd / ".codex").exists()

    def _detect_cursor(self) -> bool:
        return (self.cwd / ".cursorrules").exists() or (self.cwd / ".cursor").exists()

    def _detect_copilot(self) -> bool:
        return (self.cwd / ".github" / "copilot-instructions.md").exists()

    def configure(self, agent: str, dry_run: bool = False) -> dict:
        """Configure a specific agent. Returns what was done."""
        handler = {
            "claude-code": self._configure_claude_code,
            "codex": self._configure_codex,
            "cursor": self._configure_cursor,
            "github-copilot": self._configure_copilot,
        }.get(agent)

        if handler is None:
            return {"agent": agent, "status": "unsupported"}

        if dry_run:
            return {"agent": agent, "status": "would_configure"}

        return handler()

    def _mcp_config(self) -> dict:
        """Generate MCP server configuration."""
        return {
            "mcpServers": {
                "vibe-memory": {
                    "command": sys.executable,
                    "args": [
                        "-m", "vibe_memory.mcp_server",
                        "--db-path", str(self.db_path),
                        "--agent-id", self._agent_id(),
                        "--vibe-dir", str(self.vibe_dir),
                    ],
                },
            },
        }

    def _agent_id(self) -> str:
        return os.environ.get("VIBE_AGENT_ID", f"agent-{self.cwd.name}")

    def _configure_claude_code(self) -> dict:
        result = {"agent": "claude-code", "actions": []}

        # MCP config
        mcp_file = self.cwd / ".claude" / "mcp.json"
        mcp_file.parent.mkdir(parents=True, exist_ok=True)
        config = self._mcp_config()
        if mcp_file.exists():
            try:
                existing = json.loads(mcp_file.read_text())
                existing["mcpServers"] = {**existing.get("mcpServers", {}), **config["mcpServers"]}
                config = existing
            except json.JSONDecodeError:
                pass
        mcp_file.write_text(json.dumps(config, indent=2))
        result["actions"].append(f"MCP config written to {mcp_file}")

        # CLAUDE.md hook
        claude_md = self.cwd / "CLAUDE.md"
        hook = self._injection_hook()
        if claude_md.exists():
            content = claude_md.read_text(encoding="utf-8")
            if "VibeMemory" not in content:
                claude_md.write_text(content + "\n\n" + hook, encoding="utf-8")
                result["actions"].append(f"VibeMemory section added to CLAUDE.md")
        else:
            claude_md.write_text(hook, encoding="utf-8")
            result["actions"].append(f"CLAUDE.md created with VibeMemory setup")

        result["status"] = "configured"
        return result

    def _configure_codex(self) -> dict:
        result = {"agent": "codex", "actions": []}

        # MCP config
        codex_config = Path.home() / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        mcp_entry = (
            f'[mcp_servers.vibe-memory]\n'
            f'command = "{sys.executable}"\n'
            f'args = ["-m", "vibe_memory.mcp_server", "--db-path", "{self.db_path}", "--agent-id", "{self._agent_id()}", "--vibe-dir", "{self.vibe_dir}"]\n'
        )
        if codex_config.exists():
            content = codex_config.read_text()
            if "vibe-memory" not in content:
                codex_config.write_text(content + "\n" + mcp_entry)
                result["actions"].append(f"MCP config added to {codex_config}")
        else:
            codex_config.write_text(mcp_entry)
            result["actions"].append(f"Codex config created at {codex_config}")

        # AGENTS.md hook
        agents_md = self.cwd / "AGENTS.md"
        hook = self._injection_hook()
        if agents_md.exists():
            content = agents_md.read_text(encoding="utf-8")
            if "VibeMemory" not in content:
                agents_md.write_text(content + "\n\n" + hook, encoding="utf-8")
                result["actions"].append(f"VibeMemory section added to AGENTS.md")
        else:
            agents_md.write_text(hook, encoding="utf-8")
            result["actions"].append(f"AGENTS.md created with VibeMemory setup")

        result["status"] = "configured"
        return result

    def _configure_cursor(self) -> dict:
        result = {"agent": "cursor", "actions": []}

        rules_file = self.cwd / ".cursorrules"
        hook = self._injection_hook()
        if rules_file.exists():
            content = rules_file.read_text(encoding="utf-8")
            if "VibeMemory" not in content:
                rules_file.write_text(content + "\n\n" + hook, encoding="utf-8")
                result["actions"].append(f"VibeMemory section added to .cursorrules")
        else:
            rules_file.write_text(hook, encoding="utf-8")
            result["actions"].append(f".cursorrules created with VibeMemory setup")

        result["status"] = "configured"
        return result

    def _configure_copilot(self) -> dict:
        result = {"agent": "github-copilot", "actions": []}

        instructions = self.cwd / ".github" / "copilot-instructions.md"
        instructions.parent.mkdir(parents=True, exist_ok=True)
        hook = self._injection_hook()
        if instructions.exists():
            content = instructions.read_text(encoding="utf-8")
            if "VibeMemory" not in content:
                instructions.write_text(content + "\n\n" + hook, encoding="utf-8")
                result["actions"].append(f"VibeMemory section added to copilot-instructions.md")
        else:
            instructions.write_text(hook, encoding="utf-8")
            result["actions"].append(f"copilot-instructions.md created")

        result["status"] = "configured"
        return result

    def _injection_hook(self) -> str:
        return f"""## VibeMemory — Long-term Agent Memory

This project uses VibeMemory for cross-session memory.

### Session Start
At the beginning of each task, recall relevant memories:
- Use the `vibe_session_start` MCP tool with context about the current task
- Read `.vibe/inject.md` for auto-injected context

### Session End
When a task is complete, store key findings:
- Use the `vibe_session_end` MCP tool with a summary and highlights
- Store important decisions, bug fixes, and user preferences

### During Work
- Use `vibe_store` to remember important findings immediately
- Use `vibe_recall` to search for related past work
- Use `vibe_link` to connect related memories

Memory DB: `{self.db_path}`
"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="VibeMemory — Auto-configure coding agents")
    parser.add_argument("--agent", "-a", choices=["claude-code", "codex", "cursor", "github-copilot"],
                        help="Configure specific agent (default: auto-detect all)")
    parser.add_argument("--vibe-dir", default=".vibe", help="Vibe state directory")
    parser.add_argument("--db-path", help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done, don't write")
    args = parser.parse_args()

    detector = AgentDetector(vibe_dir=args.vibe_dir, db_path=args.db_path)

    if args.agent:
        agents = {args.agent: True}
    else:
        agents = detector.detect_all()

    print("VibeMemory — Agent Configuration")
    print(f"  Vibe dir: {detector.vibe_dir}")
    print(f"  DB path: {detector.db_path}")
    print()

    configured = 0
    for agent, detected in agents.items():
        if not detected and not args.agent:
            print(f"  {agent}: not detected, skipping")
            continue

        result = detector.configure(agent, dry_run=args.dry_run)
        if result["status"] == "configured":
            configured += 1
            print(f"  ✅ {agent}: configured")
            for action in result.get("actions", []):
                print(f"     → {action}")
        elif result["status"] == "would_configure":
            print(f"  🔍 {agent}: would configure (dry-run)")
        elif result["status"] == "unsupported":
            print(f"  ❌ {agent}: unsupported")

    print()
    if args.dry_run:
        print(f"Dry run complete. {configured} agent(s) would be configured.")
    else:
        print(f"Done. {configured} agent(s) configured.")
        print(f"Restart your coding agent to use VibeMemory.")


if __name__ == "__main__":
    main()