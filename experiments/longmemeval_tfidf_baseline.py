"""Project-untuned LongMemEval cleaned-S turn-evidence retrieval baseline."""

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from time import perf_counter, sleep

from experiments.hybrid_embedding_probe import working_set_bytes
from vibe_memory.embedding.provider import SentenceTransformerProvider, TfidfProvider
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.retrieval.ppr import recall
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


SOURCE = "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned"
SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"


def save_checkpoint(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    for attempt in range(10):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            sleep(0.1)


def prepare(case):
    sessions = case["haystack_sessions"]
    session_ids = case["haystack_session_ids"]
    dates = case["haystack_dates"]
    if not len(sessions) == len(session_ids) == len(dates):
        raise ValueError(f'{case["question_id"]}: session metadata length mismatch')
    atoms, evidence = [], set()
    for si, (session, session_id, date) in enumerate(zip(sessions, session_ids, dates)):
        timestamp = datetime.strptime(date, "%Y/%m/%d (%a) %H:%M")
        for ti, turn in enumerate(session):
            if turn["role"] not in ("user", "assistant") or not isinstance(turn["content"], str):
                raise ValueError(f'{case["question_id"]}: invalid turn {si}:{ti}')
            atom_id = f'{case["question_id"]}:{si}:{ti}'
            content = f'{turn["role"]}: {turn["content"]}'
            atoms.append(MemoryAtom(id=atom_id, agent_id=case["question_id"],
                                    tenant_id="longmemeval", session_id=session_id,
                                    content=content, summary=content,
                                    created_at=timestamp + timedelta(microseconds=ti)))
            if turn.get("has_answer") is True:
                evidence.add(atom_id)
    if not case["question_id"].endswith("_abs") and not evidence:
        raise ValueError(f'{case["question_id"]}: no turn-level evidence')
    return atoms, evidence


def run(dataset: Path, smoke: int = 0, model_dir: Path | None = None,
        checkpoint: Path | None = None):
    raw = dataset.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SHA256:
        raise ValueError(f"dataset SHA-256 mismatch: {digest}")
    cases = json.loads(raw)
    if len(cases) != 500 or len({case["question_id"] for case in cases}) != 500:
        raise ValueError("expected 500 unique official question IDs")
    if sum(case["question_id"].endswith("_abs") for case in cases) != 30:
        raise ValueError("expected 30 abstention cases")
    prepared = [(case, *prepare(case)) for case in cases]  # Validate before scoring.
    selected = prepared[:smoke] if smoke else prepared
    if checkpoint is not None and model_dir is None:
        raise ValueError("checkpoint requires --model-dir")
    question_ids = [case["question_id"] for case, _, _ in selected
                    if not case["question_id"].endswith("_abs")]
    rows = []
    before_memory = working_set_bytes()
    model = None
    model_load_ms = None
    model_hash = None
    prior_load_ms = 0.0
    if model_dir is not None:
        if not model_dir.is_dir():
            raise FileNotFoundError(model_dir)
        model_hash = hashlib.sha256((model_dir / "model.safetensors").read_bytes()).hexdigest()
        if checkpoint is not None and checkpoint.exists():
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            if (saved.get("source_sha256"), saved.get("model_weight_sha256"),
                    saved.get("question_ids")) != (digest, model_hash, question_ids):
                raise ValueError("checkpoint dataset, model, or question order mismatch")
            rows = saved["rows"]
            if [row["id"] for row in rows] != question_ids[:len(rows)] or len(rows) > len(question_ids):
                raise ValueError("checkpoint rows are not the expected question prefix")
            prior_load_ms = saved.get("model_load_total_ms", 0.0)
        model = SentenceTransformerProvider(model_name=str(model_dir), device="cpu")
        if not model.available:
            raise RuntimeError("sentence-transformers unavailable")
        start = perf_counter()
        model._get_model()
        model_load_ms = round((perf_counter() - start) * 1000, 1)
    completed = len(rows)
    eligible_index = -1
    for index, (case, atoms, evidence) in enumerate(selected):
        if case["question_id"].endswith("_abs"):
            continue
        eligible_index += 1
        if eligible_index < completed:
            continue
        store = VibeStorage(":memory:", tenant_id="longmemeval")
        try:
            start = perf_counter()
            for atom in atoms:
                store.insert_atom(atom)
            write_ms = (perf_counter() - start) * 1000
            stored = store.get_atoms_by_agent(case["question_id"])
            documents = [atom.content for atom in stored]
            key = tuple((atom.id, atom.version) for atom in stored)
            start = perf_counter()
            tfidf = TfidfProvider().fit(documents)
            bm25 = BM25Strategy()
            bm25.fit(documents)
            setup_ms = (perf_counter() - start) * 1000
            bm25_cache = {"key": key, "index": bm25}
            model_setup_ms = None
            if model is not None:
                start = perf_counter()
                vectors = model.encode(documents)
                model_setup_ms = (perf_counter() - start) * 1000
                if model.name == "tfidf(fallback)":
                    raise RuntimeError("semantic model fell back to TF-IDF")
            results = {}
            order = ("tfidf", "model") if index % 2 == 0 else ("model", "tfidf")
            for arm in order if model is not None else ("tfidf",):
                start = perf_counter()
                found = recall(case["question"], case["question_id"], store,
                               mode="precision", top_k=5, tenant_id="longmemeval",
                               embedding_provider=tfidf if arm == "tfidf" else model,
                               semantic_cache=({"key": key, "tfidf_fitted": True}
                                               if arm == "tfidf" else {"key": key, "vectors": vectors}),
                               bm25_cache=bm25_cache)["atoms"]
                results[arm] = (found, (perf_counter() - start) * 1000)
            found, query_ms = results["tfidf"]
            returned = [atom.id for atom in found]
            hits = evidence.intersection(returned)
            rows.append({"id": case["question_id"], "type": case["question_type"],
                         "turns": len(atoms), "evidence_turns": len(evidence),
                         "top5_ids": returned, "hit": bool(hits),
                         "evidence_recall": len(hits) / len(evidence),
                         "session_hit": bool({atom.session_id for atom in found}
                                             & set(case["answer_session_ids"])),
                         "write_ms": round(write_ms, 1),
                         "setup_ms": round(setup_ms, 1),
                         "query_ms": round(query_ms, 1)})
            if model is not None:
                model_found, model_query_ms = results["model"]
                model_ids = [atom.id for atom in model_found]
                model_hits = evidence.intersection(model_ids)
                rows[-1].update(model_top5_ids=model_ids, model_hit=bool(model_hits),
                                model_evidence_recall=len(model_hits) / len(evidence),
                                model_session_hit=bool({atom.session_id for atom in model_found}
                                                       & set(case["answer_session_ids"])),
                                model_setup_ms=round(model_setup_ms, 1),
                                model_query_ms=round(model_query_ms, 1))
        finally:
            store.conn.close()
        if checkpoint is not None:
            saved = {"source_sha256": digest, "model_weight_sha256": model_hash,
                     "question_ids": question_ids, "model_load_total_ms": prior_load_ms + model_load_ms,
                     "rows": rows}
            save_checkpoint(checkpoint, saved)
            if len(rows) % 25 == 0:
                print(f"completed {len(rows)}/{len(question_ids)}", flush=True)
    counts = Counter(row["type"] for row in rows)
    report = {"source": SOURCE, "source_revision": "98d7416", "source_sha256": digest,
            "source_bytes": len(raw), "mode": "precision Top-5; warm core; direct SQLite writes",
            "scope": "first-N adapter smoke, not benchmark" if smoke else "all eligible official cases",
            "selected_instances": len(selected), "excluded_abstention": sum(
                case["question_id"].endswith("_abs") for case, _, _ in selected),
            "scored": len(rows), "question_types": dict(counts),
            "evidence_top5_hits": sum(row["hit"] for row in rows),
            "evidence_session_top5_hits": sum(row["session_hit"] for row in rows),
            "mean_turn_evidence_recall": (sum(row["evidence_recall"] for row in rows) / len(rows)
                                          if rows else None),
            "write_p50_ms": median(row["write_ms"] for row in rows) if rows else None,
            "setup_p50_ms": median(row["setup_ms"] for row in rows) if rows else None,
            "query_p50_ms": median(row["query_ms"] for row in rows) if rows else None,
            "working_set_before_bytes": before_memory,
            "working_set_after_bytes": working_set_bytes(),
            "paid_api_calls": 0, "rows": rows,
            "limits": "Official evidence is not exhaustive relevance; no answer generation. Direct SQLite writes and warm core queries are not SDK/MCP onboarding or end-to-end latency. Public questions may occur in model pretraining. No human review or production change."}
    if model is not None:
        report.update(model_dir=str(model_dir), model_load_ms=model_load_ms,
                      model_load_total_ms=prior_load_ms + model_load_ms,
                      resumed_rows=completed, model_weight_sha256=model_hash,
                      model_files_bytes=sum(path.stat().st_size for path in model_dir.rglob("*")
                                            if path.is_file()),
                      model_evidence_top5_hits=sum(row["model_hit"] for row in rows),
                      model_evidence_session_top5_hits=sum(row["model_session_hit"] for row in rows),
                      model_rescued=[row["id"] for row in rows if row["model_hit"] and not row["hit"]],
                      model_lost=[row["id"] for row in rows if row["hit"] and not row["model_hit"]],
                      model_setup_p50_ms=median(row["model_setup_ms"] for row in rows) if rows else None,
                      model_query_p50_ms=median(row["model_query_ms"] for row in rows) if rows else None)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--smoke", type=int, default=0, help="First N instances; not benchmark")
    parser.add_argument("--model-dir", type=Path, help="Local English sentence-transformers snapshot")
    parser.add_argument("--checkpoint", type=Path, help="Atomic per-question progress file")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.smoke < 0:
        parser.error("--smoke must be nonnegative")
    report = run(args.dataset, args.smoke, args.model_dir, args.checkpoint)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        args.json.write_text(output, encoding="utf-8")
    print(output)
