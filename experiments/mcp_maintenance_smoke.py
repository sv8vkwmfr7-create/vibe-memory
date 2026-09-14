"""Fresh-file MCP maintenance protocol replay; not an LLM/UI benchmark."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter


def summary(values):
    ordered = sorted(values)
    def percentile(q):
        position = (len(ordered) - 1) * q
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)
    return {"p50": percentile(.5), "p95": percentile(.95), "p99": percentile(.99)}


def run(rounds=30):
    root = Path(tempfile.mkdtemp(prefix="vibe-mcp-maintenance-"))
    process = subprocess.Popen(
        [sys.executable, "-m", "vibe_memory.mcp_server", "--db-path", str(root / "memory.db"),
         "--vibe-dir", str(root), "--agent-id", "maintenance-smoke", "--wal-maintenance"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    request_id = 0
    def send(method, params):
        nonlocal request_id
        request_id += 1
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                       "method": method, "params": params}) + "\n")
        process.stdin.flush()
    def receive():
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("MCP server exited without a response")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response
    def tool(name, arguments):
        send("tools/call", {"name": name, "arguments": arguments})
        return json.loads(receive()["result"]["content"][0]["text"])
    try:
        send("initialize", {})
        receive()
        tool("vibe_session_start", {"context": "API timeout"})
        tool("vibe_session_end", {"summary": "API timeout fixed to 60 seconds",
                                  "highlights": ["API timeout connection pool size 20"]})
        started = tool("vibe_session_start", {"context": "API timeout"})
        assert started["memories_recalled"] == 2
        checkpoint_ms, queued_ms, statuses, hits = [], [], {}, 0
        for _ in range(rounds):
            start = perf_counter()
            send("tools/call", {"name": "vibe_checkpoint", "arguments": {}})
            send("tools/call", {"name": "vibe_recall", "arguments": {"query": "API timeout"}})
            maintenance = json.loads(receive()["result"]["content"][0]["text"])
            checkpoint_ms.append((perf_counter() - start) * 1000)
            recall = json.loads(receive()["result"]["content"][0]["text"])
            queued_ms.append((perf_counter() - start) * 1000)
            statuses[maintenance["status"]] = statuses.get(maintenance["status"], 0) + 1
            assert maintenance["status"] == "truncated", maintenance
            assert maintenance["wal_bytes_after"] == 0, maintenance
            assert any("60 seconds" in atom["content"] for atom in recall["memories"]), recall
            hits += 1
        return {"dataset": "mcp-maintenance-smoke-v1", "initial_memories": 2,
                "rounds": rounds, "anchor_hits": hits, "maintenance_statuses": statuses,
                "checkpoint_round_trip_ms": summary(checkpoint_ms),
                "queued_checkpoint_plus_recall_ms": summary(queued_ms),
                "maintenance_enabled": True,
                "notes": "Fresh temporary file; actual MCP stdio subprocess; sequential server receives pipelined checkpoint then recall; queued latency includes maintenance and recall, not isolated recall latency. Two synthetic English memories, no other workers or external locks, no LLM/UI or user-perception claim. Temp DB retained; no background scheduler."}
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    print("REPORT=" + json.dumps(run()))
