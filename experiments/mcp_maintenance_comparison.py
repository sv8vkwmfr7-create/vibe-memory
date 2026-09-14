"""Same-seed fresh WAL-file MCP on/off replay; no LLM or concurrent writer."""
import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.storage.sqlite_store import VibeStorage
from experiments.disk_pressure_benchmark import QUERY
from experiments.mcp_maintenance_smoke import summary


def replay(seed, root, enabled, rounds):
    path = root / "memory.db"
    root.mkdir()
    destination = sqlite3.connect(path)
    seed.backup(destination)
    destination.close()
    observer = sqlite3.connect(path)
    observer.execute("PRAGMA journal_mode=WAL")
    observer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    process = subprocess.Popen(
        [sys.executable, "-m", "vibe_memory.mcp_server", "--db-path", str(path),
         "--vibe-dir", str(root), "--agent-id", "dense"]
        + (["--wal-maintenance"] if enabled else []),
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
            raise RuntimeError("MCP exited without a response")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["result"]
    def wal_bytes():
        wal = Path(str(path) + "-wal")
        return wal.stat().st_size if wal.exists() else 0
    events, queued, first_times, statuses, hits, peak = [], [], [], {}, 0, 0
    try:
        start = perf_counter()
        send("initialize", {})
        receive()
        initialization_ms = (perf_counter() - start) * 1000
        # Same warm-up call and store payload in both variants, with no external writer.
        send("tools/call", {"name": "vibe_recall", "arguments": {"query": QUERY, "mode": "budget", "top_k": 5}})
        warm = json.loads(receive()["content"][0]["text"])
        assert any(m["id"] == "dense-0" for m in warm["memories"])
        for cycle in range(rounds):
            send("tools/call", {"name": "vibe_store", "arguments": {
                "content": QUERY + " 桌面背景颜色图片设置日常维护记录 " * 5,
                "session_id": "writer", "tags": ["background"]}})
            receive()
            before = wal_bytes()
            peak = max(peak, before)
            start = perf_counter()
            send("tools/call", {"name": "vibe_checkpoint", "arguments": {}}) if enabled else send("ping", {})
            send("tools/call", {"name": "vibe_recall", "arguments": {"query": QUERY, "mode": "budget", "top_k": 5}})
            first = receive()
            first_ms = (perf_counter() - start) * 1000
            recall = json.loads(receive()["content"][0]["text"])
            total_ms = (perf_counter() - start) * 1000
            assert any(m["id"] == "dense-0" for m in recall["memories"]), recall
            hits += 1
            report = json.loads(first["content"][0]["text"]) if enabled else None
            if report is not None:
                statuses[report["status"]] = statuses.get(report["status"], 0) + 1
                assert report["status"] == "truncated", report
                assert report["wal_bytes_after"] == 0, report
            after = wal_bytes()
            peak = max(peak, after)
            first_times.append(first_ms)
            queued.append(total_ms)
            events.append({"round": cycle, "wal_bytes_before": before, "wal_bytes_after_pair": after,
                           "first_response_ms": round(first_ms, 3), "queued_pair_ms": round(total_ms, 3),
                           "maintenance": report})
        assert observer.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        observer.execute("INSERT INTO atoms_fts(atoms_fts,rank) VALUES('integrity-check',1)")
        observer.execute("INSERT INTO atoms_trigram(atoms_trigram,rank) VALUES('integrity-check',1)")
        observer.rollback()
        return {"enabled": enabled, "rounds": rounds, "anchor_hits": hits,
                "initialization_ms": round(initialization_ms, 3),
                "first_response_ms": summary(first_times), "queued_pair_ms": summary(queued),
                "maintenance_statuses": statuses, "sampled_wal_peak_bytes": peak,
                "sqlite_integrity": "ok", "fts_integrity": "ok", "events": events}
    finally:
        process.terminate()
        process.wait(timeout=10)
        observer.close()


def run(scale=100000, rounds=30):
    root = Path(tempfile.mkdtemp(prefix="vibe-mcp-comparison-"))
    storage = VibeStorage(str(root / "seed.db"), journal_mode="wal")
    try:
        background = QUERY + " 桌面背景颜色图片设置日常维护记录 " * 5
        for i in range(scale):
            content = QUERY if i == 0 else background
            storage.insert_atom(MemoryAtom(id=f"dense-{i}", agent_id="dense", session_id="s",
                content=content, summary=content, created_at=datetime(2026, 1 if i == 0 else 2, 1)))
            if (i + 1) % 10000 == 0:
                print(f"Seeded {i + 1}/{scale}", flush=True)
        storage.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        runs = []
        for index, enabled in enumerate([False, True, True, False]):
            result = replay(storage.conn, root / f"run-{index}", enabled, rounds)
            runs.append(result)
            print(f"Run {index}: maintenance={enabled}, hits={result['anchor_hits']}/{rounds}, queued p95={result['queued_pair_ms']['p95']}ms", flush=True)
        return {"dataset": "mcp-maintenance-comparison-v1", "scale": scale, "sqlite_version": sqlite3.sqlite_version,
                "runs": runs, "notes": "One synthetic dense Chinese seed cloned through SQLite backup into four fresh DBs; off/on/on/off order. All variants use WAL and default auto-checkpoint; off sends ping then recall, on sends checkpoint then recall. Same warm-up and one store per round, no concurrent writer, no held snapshots, no graph, seeding/initialization/warm-up excluded from pair latencies. Pair includes first request plus queued recall, not isolated recall. Event WAL sizes are sampled, not hard peaks; observer has no retained transaction during load. No formal tests concurrent. No LLM/UI/user perception or stable causal timing claim; temp DBs retained."}
    finally:
        storage.conn.close()


if __name__ == "__main__":
    print("REPORT=" + json.dumps(run()))
