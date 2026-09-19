"""Public CLI behavior for the VibeMemory MCP end-to-end doctor."""

import subprocess
import sys


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
