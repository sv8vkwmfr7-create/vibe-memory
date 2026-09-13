"""Synthetic Chinese recall scaling; serial in-memory, not production proof."""
import argparse
import ctypes
import json
import platform
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vibe_memory import VibeMemory
from experiments.scale_visibility_benchmark import _summary


def working_set_mb():
    if sys.platform != "win32":
        return None
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                "peak", "working", "paged_peak", "paged", "nonpaged_peak",
                "nonpaged", "pagefile", "pagefile_peak",
            )]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return round(counters.working / 1024 ** 2, 2)


def run_scale(scale, samples):
    memory = VibeMemory(agent_id="chinese-scale", db_path=":memory:", embedding_backend="tfidf")
    start = time.perf_counter()
    old = memory.store("连接池耗尽导致接口超时，释放连接后恢复正常", session_id="old",
                       auto_build_edges=False, auto_episode=False)
    for index in range(scale - 1):
        memory.store(f"日常维护记录编号{index}，桌面主题颜色和背景图片设置完成",
                     session_id="background", auto_build_edges=False, auto_episode=False)
    write_seconds = time.perf_counter() - start
    before_mb = working_set_mb()
    tracemalloc.start()
    times, candidate_times, hits = [], [], 0
    try:
        for _ in range(samples):
            start = time.perf_counter()
            candidates = memory.storage.get_recall_candidates("chinese-scale", "接口超时如何修复连接池", 100)
            candidate_times.append((time.perf_counter() - start) * 1000)
            assert old.id in {atom.id for atom in candidates} and len(candidates) <= 100
            start = time.perf_counter()
            result = memory.recall("接口超时如何修复连接池", mode="budget", top_k=5)
            times.append((time.perf_counter() - start) * 1000)
            hits += int(old.id in {atom.id for atom in result["atoms"]})
        _, python_peak = tracemalloc.get_traced_memory()
        return {"atoms": scale, "samples": samples, "old_answer_hits": hits,
                "candidate_backend": "fts5-trigram" if memory.storage._trigram_enabled else "scoped-like",
                "candidate_latency_ms": _summary(candidate_times),
                "recall_cold_ms": round(times[0], 3),
                "recall_warm_ms": _summary(times[1:]),
                "store_ops_per_sec": round(scale / write_seconds, 2),
                "working_set_before_recall_mb": before_mb,
                "working_set_after_recall_mb": working_set_mb(),
                "python_recall_peak_mb": round(python_peak / 1024 ** 2, 2)}
    finally:
        tracemalloc.stop()
        memory.storage.conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, nargs="+", default=[1000, 10000, 100000])
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    if min(args.scale) < 2 or args.samples < 2:
        parser.error("scale and samples must be at least 2")
    print(json.dumps({"dataset_version": "chinese-scale-v1", "python": platform.python_version(),
                      "storage": ":memory:", "candidate_backend": "trigram-or-like",
                      "notes": "Repeated fixed query; tracemalloc enabled for recall, excludes native SQLite allocations; working set is process-wide and scales share a process; no graph edges",
                      "scales": [run_scale(scale, args.samples) for scale in args.scale]}, indent=2))


if __name__ == "__main__":
    main()
