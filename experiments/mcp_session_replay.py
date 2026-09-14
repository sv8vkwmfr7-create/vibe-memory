"""Local labeled-corpus MCP replay. Never includes corpus text in its report."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory.storage.sqlite_store import VibeStorage
from vibe_memory.models.memory_atom import EdgeLabel
from experiments.mcp_maintenance_smoke import summary


def replay(data, enabled, seed_path=None):
    root = Path(tempfile.mkdtemp(prefix="vibe-mcp-session-"))
    path = root / "memory.db"
    # Both variants use WAL, so the flag does not change the journal-mode baseline.
    storage = VibeStorage(str(path), journal_mode="wal")
    if seed_path is not None:
        import sqlite3
        with sqlite3.connect(f"file:{Path(seed_path).as_posix()}?mode=ro", uri=True) as source:
            source.backup(storage.conn)
    storage.conn.close()
    process = subprocess.Popen(
        [sys.executable, "-m", "vibe_memory.mcp_server", "--db-path", str(path),
         "--vibe-dir", str(root), "--agent-id", "local-replay"]
        + (["--wal-maintenance"] if enabled else []),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    request_id = 0
    def request(method, params):
        nonlocal request_id
        request_id += 1
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                       "method": method, "params": params}, ensure_ascii=False) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("MCP server exited without a response")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["result"]
    def tool(name, arguments):
        return json.loads(request("tools/call", {"name": name, "arguments": arguments})["content"][0]["text"])
    mapping, anonymous, rows, maintenance = {}, {}, [], []
    try:
        request("initialize", {})
        for index, atom in enumerate(data["atoms"]):
            stored = {"id": atom["id"]} if seed_path is not None else tool("vibe_store", {"content": atom["content"], "summary": atom["summary"],
                                         "session_id": atom["session_id"]})
            mapping[atom["id"]] = stored["id"][:8]
            anonymous[stored["id"][:8]] = f"atom-{index}"
        for edge in data.get("edges", []):
            if seed_path is not None:
                continue
            linked = tool("vibe_link", {"from_id": mapping[edge["from_atom_id"]],
                                        "to_id": mapping[edge["to_atom_id"]],
                                        "label": EdgeLabel(edge["label"]).name.lower()})
            if "error" in linked:
                raise RuntimeError("Corpus edge could not be replayed")
        for index, query in enumerate(data["queries"]):
            boundary_start = perf_counter()
            # No queued request and all previous operations returned; this is an explicit idle boundary.
            if enabled:
                start = perf_counter()
                report = tool("vibe_checkpoint", {})
                maintenance.append({"status": report["status"], "elapsed_ms": report["elapsed_ms"],
                                    "round_trip_ms": round((perf_counter() - start) * 1000, 3),
                                    "wal_bytes_after": report["wal_bytes_after"]})
                assert report["status"] == "truncated", report
            start = perf_counter()
            started = tool("vibe_session_start", {"context": query["text"]})
            session_ms = (perf_counter() - start) * 1000
            boundary_to_session_ms = (perf_counter() - boundary_start) * 1000
            relevant = {mapping[atom_id] for atom_id in query["relevant_ids"]}
            for mode in ("precision", "budget"):
                start = perf_counter()
                recalled = tool("vibe_recall", {"query": query["text"], "mode": mode, "top_k": 5})
                elapsed = (perf_counter() - start) * 1000
                returned = [m["id"] for m in recalled["memories"]]
                hits = len(set(returned) & relevant)
                rows.append({"query_id": f"query-{index}", "mode": mode,
                             "returned_ids": [anonymous[atom_id] for atom_id in returned],
                             "precision": hits / len(returned) if returned else 0,
                             "recall": hits / len(relevant), "round_trip_ms": round(elapsed, 3),
                             "session_start_ms": round(session_ms, 3),
                             "boundary_to_session_ms": round(boundary_to_session_ms, 3),
                             "session_memories_count": started["memories_recalled"]})
        aggregates = {}
        for mode in ("precision", "budget"):
            selected = [row for row in rows if row["mode"] == mode]
            aggregates[mode] = {"mean_precision": sum(row["precision"] for row in selected) / len(selected),
                                "mean_recall": sum(row["recall"] for row in selected) / len(selected),
                                "round_trip_ms": summary([row["round_trip_ms"] for row in selected])}
        return {"maintenance_enabled": enabled, "rows": rows, "aggregates": aggregates,
                "maintenance": maintenance}
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8-sig"))
    if not data.get("queries") or any(not q["relevant_ids"] for q in data["queries"]):
        raise ValueError("Nonempty questions and labels required")
    print("REPORT=" + json.dumps({"dataset": "local-corpus-mcp-replay-v1",
        "atoms": len(data["atoms"]), "queries": len(data["queries"]),
        "runs": [replay(data, enabled) for enabled in (False, True)],
        "notes": "Private corpus text not reported; fresh WAL DBs; sequential MCP store/link/session-start/recall. Idle maintenance only after previous response and before session start; default precision and budget (not explicit two-hop). Corpus timestamps/tenant scope/lifecycle not replayed: all provided memories treated as currently available to one test agent. Synthetic reconstruction/labels require independent human review. No LLM/UI, raw-dialogue, temporal-cutoff, concurrency, stable timing or user-perception proof. Temporary DBs retained; existing data/configuration untouched."}))
