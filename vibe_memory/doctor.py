"""End-to-end diagnostics for the VibeMemory MCP stdio interface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import uuid


REQUIRED_TOOLS = {
    "vibe_store",
    "vibe_recall",
    "vibe_forget",
}


class DoctorError(RuntimeError):
    """A user-actionable diagnostic failure."""


class MCPProcess:
    """Small JSON-RPC client backed by a real VibeMemory MCP subprocess."""

    def __init__(
        self,
        db_path: str,
        agent_id: str,
        timeout: float,
        python_executable: str,
    ):
        self.timeout = timeout
        try:
            self.proc = subprocess.Popen(
                [
                    python_executable,
                    "-m",
                    "vibe_memory.mcp_server",
                    "--db-path",
                    db_path,
                    "--agent-id",
                    agent_id,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
        except OSError as error:
            raise DoctorError(
                f"Could not start MCP with Python interpreter {python_executable}"
            ) from error
        self._responses: queue.Queue[str] = queue.Queue()
        self._request_id = 0
        threading.Thread(target=self._read_stdout, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._responses.put(line)

    def request(self, method: str, params: dict | None = None) -> dict:
        if self.proc.poll() is not None:
            raise DoctorError(self._process_error("MCP process exited"))
        self._request_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        try:
            line = self._responses.get(timeout=self.timeout)
        except queue.Empty as error:
            raise DoctorError(
                self._process_error(
                    f"Timed out after {self.timeout:g}s waiting for {method}"
                )
            ) from error
        try:
            response = json.loads(line)
        except json.JSONDecodeError as error:
            raise DoctorError(f"MCP returned invalid JSON: {line.strip()}") from error
        if "error" in response:
            detail = response["error"].get("message", str(response["error"]))
            raise DoctorError(f"MCP {method} failed: {detail}")
        return response["result"]

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        result = self.request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )
        try:
            return json.loads(result["content"][0]["text"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise DoctorError(f"Tool {name} returned an invalid result") from error

    def _process_error(self, prefix: str) -> str:
        detail = ""
        if self.proc.poll() is not None and self.proc.stderr is not None:
            detail = self.proc.stderr.read().strip()
        return f"{prefix}: {detail}" if detail else prefix

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


def _check_environment(db_path: Path) -> None:
    if sys.version_info < (3, 10):
        raise DoctorError("Python 3.10 or newer is required")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=db_path.parent, delete=True):
            pass
    except OSError as error:
        raise DoctorError(
            f"Database directory is not writable: {db_path.parent}"
        ) from error


def _start(
    db_path: Path,
    agent_id: str,
    timeout: float,
    python_executable: str,
) -> MCPProcess:
    client = MCPProcess(str(db_path), agent_id, timeout, python_executable)
    try:
        initialized = client.request("initialize")
        if initialized.get("serverInfo", {}).get("name") != "vibe-memory":
            raise DoctorError("Unexpected MCP server identity")
        return client
    except Exception:
        client.close()
        raise


def run_doctor(
    db_path: Path,
    agent_id: str,
    timeout: float,
    python_executable: str = sys.executable,
) -> list[str]:
    """Run the complete MCP persistence journey and return passed step names."""
    passed: list[str] = []
    _check_environment(db_path)
    passed.append("Environment")

    token = uuid.uuid4().hex
    query = f"vibe-doctor-{token} request hangs"
    catalog_scope = f"doctor-{token}-catalog"
    orders_scope = f"doctor-{token}-orders"
    stored_ids: list[str] = []

    client = _start(db_path, agent_id, timeout, python_executable)
    passed.append("MCP startup")
    try:
        tools = {tool["name"] for tool in client.request("tools/list")["tools"]}
        missing = REQUIRED_TOOLS - tools
        if missing:
            raise DoctorError(f"Required MCP tools are missing: {sorted(missing)}")
        passed.append("Tool discovery")

        catalog = client.call_tool(
            "vibe_store",
            {
                "content": f"{query} Catalog",
                "scope": {"service": catalog_scope},
                "tags": ["vibe-doctor"],
            },
        )
        orders = client.call_tool(
            "vibe_store",
            {
                "content": f"{query} Orders pool exhausted",
                "scope": {"service": orders_scope},
                "tags": ["vibe-doctor"],
            },
        )
        stored_ids.extend([catalog["id"], orders["id"]])
        passed.append("Store")
    finally:
        client.close()

    client = _start(db_path, agent_id, timeout, python_executable)
    passed.append("Process restart")
    try:
        recalled = client.call_tool(
            "vibe_recall",
            {"query": query, "scope": {"service": orders_scope}},
        )
        memories = recalled.get("memories", [])
        recalled_ids = {memory.get("id") for memory in memories}
        orders_recall_id = orders["id"][:8]
        if orders_recall_id not in recalled_ids:
            returned = [memory.get("content", "") for memory in memories[:3]]
            raise DoctorError(
                "Stored memory was not recalled after process restart; "
                f"received {returned!r}"
            )
        passed.append("Cross-session recall")

        if (
            not memories
            or memories[0].get("id") != orders_recall_id
            or not recalled.get("scope_boosted")
        ):
            raise DoctorError("Explicit scope did not boost the matching memory")
        passed.append("Scope")

        for atom_id in stored_ids:
            deleted = client.call_tool("vibe_forget", {"atom_id": atom_id})
            if not deleted.get("deleted"):
                raise DoctorError(f"Could not clean up diagnostic memory {atom_id}")
        passed.append("Cleanup")
    finally:
        client.close()

    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vibe-doctor",
        description="Verify VibeMemory MCP startup, persistence, recall, scope, and cleanup.",
    )
    parser.add_argument("--db-path", default=".vibe/memory.db")
    parser.add_argument("--agent-id", default="vibe-doctor")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--python",
        dest="python_executable",
        default=sys.executable,
        help="Python interpreter used to start the MCP server",
    )
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        passed = run_doctor(
            Path(args.db_path).resolve(),
            args.agent_id,
            args.timeout,
            args.python_executable,
        )
    except (DoctorError, OSError, subprocess.SubprocessError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1

    for step in passed:
        print(f"[PASS] {step}")
    print("\nVibeMemory MCP end-to-end check succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
