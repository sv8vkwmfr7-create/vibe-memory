"""Public CLI behavior for the VibeMemory MCP end-to-end doctor."""

import subprocess
import sys
from pathlib import Path

import pytest


def test_doctor_verifies_restart_recall_scope_and_cleanup(tmp_path):
    db_path = tmp_path / "doctor.db"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibe_memory.doctor",
            "--db-path",
            str(db_path),
            "--agent-id",
            "doctor-test-agent",
            "--timeout",
            "5",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    for step in (
        "Environment",
        "MCP startup",
        "Tool discovery",
        "Store",
        "Process restart",
        "Cross-session recall",
        "Scope",
        "Cleanup",
    ):
        assert f"[PASS] {step}" in result.stdout
    assert "VibeMemory MCP end-to-end check succeeded." in result.stdout


def test_doctor_reports_an_unusable_python_interpreter(tmp_path):
    missing_python = tmp_path / "missing-python.exe"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibe_memory.doctor",
            "--db-path",
            str(tmp_path / "doctor.db"),
            "--python",
            str(missing_python),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )

    assert result.returncode == 1
    assert "[FAIL] Could not start MCP with Python interpreter" in result.stderr
    assert str(missing_python) in result.stderr


@pytest.mark.parametrize("close_count", [1, 2])
def test_mcp_close_releases_resources_without_warnings(tmp_path, close_count):
    script = """
import gc
import sys
import threading
from vibe_memory.doctor import DoctorError, MCPProcess

client = MCPProcess(sys.argv[1], "doctor-close-test", 5, sys.executable)
try:
    client.request("initialize")
finally:
    for _ in range(int(sys.argv[2])):
        client.close()
try:
    client.request("tools/list")
except DoctorError:
    pass
else:
    raise AssertionError("closed MCP process accepted a request")
del client
for thread in threading.enumerate():
    if thread is not threading.current_thread():
        thread.join(timeout=5)
gc.collect()
"""
    result = subprocess.run(
        [sys.executable, "-W", "always::ResourceWarning", "-c", script,
         str(tmp_path / "close.db"), str(close_count)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ResourceWarning" not in result.stderr, result.stderr
