"""Pinned first-three PersonaMem-v2 text-validation adapter smoke, not a benchmark."""

import argparse
import ast
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

from experiments.locomo_adjacent_context_probe import write_texts
from experiments.longmemeval_lexical_slot_probe import rank_fused_ids
from experiments.longmemeval_stage_probe import STAGES, loss_stage
from experiments.personamem_evidence import evidence_indices
from experiments.precision_stage_diagnostics import _rank, _recall_with_stages
from vibe_memory.embedding import index_flat
from vibe_memory.embedding.provider import SentenceTransformerProvider, TfidfProvider
from vibe_memory.models.memory_atom import MemoryAtom
from vibe_memory.retrieval.strategies import BM25Strategy
from vibe_memory.storage.sqlite_store import VibeStorage


REVISION = "ed956dea41521fc4499acbc63f966e0fd3c053ba"
CSV_SHA256 = "a47a7dd3879de5e282c6d15266437ed44cf69c0c93c79634645dbd73d655b29a"
HISTORIES = {
    "988": "54b4b069d9b0dafa68fd96bab6f2b2330393ab1414b680dda7ee599f7e2031b1",
    "782": "5efec92c18af920d19dc6a0cf8977d5f39bd4003df9ea45959f69b33cd8e824f",
    "730": "943d5af3c3dded94c80dd1641901473b6f1cb8b1d46280d3c2d58c189182fcaa",
}


def parse_query(value: str) -> str:
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, dict) or parsed.get("role") != "user" or not isinstance(parsed.get("content"), str) or not parsed["content"].strip():
        raise ValueError("expected nonempty user query dict")
    return parsed["content"]


def stage_diagnosis(evidence: set[str], stages: dict) -> dict:
    return {"loss_stage": loss_stage(evidence, stages),
            "ids": {name: stages[name] for name in STAGES},
            "fused_top5_snippet_hit": bool(evidence.intersection(stages["fused"][:5])),
            "evidence_ranks": {atom_id: {name: _rank(stages[name], atom_id) for name in STAGES}
                               for atom_id in sorted(evidence)}}


def rank_positions(atom_ids: list[str], ranked: list, evidence: set[str]) -> dict:
    positions = {atom_ids[int(i)]: {"rank": rank, "score": float(score), "positive_score": bool(score > 0)}
                 for rank, (i, score) in enumerate(ranked, 1)}
    found = {atom_id: positions.get(atom_id, {"rank": None, "score": None, "positive_score": False})
             for atom_id in sorted(evidence)}
    return {"ranked_count": len(ranked), "top5_ids": [atom_ids[int(i)] for i, _ in ranked[:5]],
            "evidence": found,
            "nearest_positive_snippet_rank": min((item["rank"] for item in found.values() if item["positive_score"]), default=None)}


def preceding_texts(atoms: list[MemoryAtom]) -> list[str]:
    return [text for text, _ in write_texts(
        [{"id": atom.id, "session_id": atom.session_id, "content": atom.content} for atom in atoms], True)]


def run(directory: Path, model_dir: Path, stage_reference: Path | None = None, full_ranks: bool = False,
        previous_context: bool = False, include_timing: bool = False):
    if full_ranks and stage_reference is None:
        raise ValueError("full-rank observation requires a pinned original stage reference")
    if previous_context and stage_reference is None or include_timing and not previous_context:
        raise ValueError("previous context requires a stage reference; timing requires previous context")
    source = directory / "val.csv"
    source_raw = source.read_bytes()
    if hashlib.sha256(source_raw).hexdigest() != CSV_SHA256:
        raise ValueError("official validation-file SHA-256 mismatch")
    with source.open(encoding="utf-8", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    if len(all_rows) != 2061 or len(all_rows[0]) != 27 or [row["persona_id"] for row in all_rows[:3]] != list(HISTORIES):
        raise ValueError("pinned row count/schema/first-three selection mismatch")
    if previous_context and [(row["who"], row["pref_type"], row["updated"]) for row in all_rows[:3]] != [
            ("others", "anti_stereotypical_pref", "False"), ("self", "stereotypical_pref", "False"), ("self", "ask_to_forget", "True")]:
        raise ValueError("audited task metadata mismatch")
    prepared = []
    for index, row in enumerate(all_rows[:3]):
        persona = row["persona_id"]
        expected_path = f"data/chat_history_32k/chat_history_250913_163134_persona{persona}.json"
        if row["chat_history_32k_link"] != expected_path:
            raise ValueError("history path does not match pinned CSV link")
        raw = (directory / f"history{persona}.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != HISTORIES[persona]:
            raise ValueError("locally pinned history SHA-256 mismatch")
        data = json.loads(raw)
        history = data["chat_history"]
        if data["metadata"]["persona_id"] != int(persona) or data["metadata"]["total_messages"] != len(history):
            raise ValueError("history metadata mismatch")
        query = parse_query(row["user_query"])
        snippet = json.loads(row["related_conversation_snippet"])
        # All three must map before model setup; do not replace a failing row with a later one.
        evidence = evidence_indices(history, snippet)
        prepared.append((index, persona, expected_path, len(raw), history, query, evidence))
    model_hash = hashlib.sha256((model_dir / "model.safetensors").read_bytes()).hexdigest()
    if model_hash != "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db":
        raise ValueError("pinned MiniLM model mismatch")
    provider = SentenceTransformerProvider(model_name=str(model_dir), device="cpu")
    if not provider.available:
        raise RuntimeError("sentence-transformers unavailable")
    if previous_context:
        provider._get_model()  # Load once outside corpus-encoding timers.
    rows = []
    for index, persona, path, byte_count, history, query, evidence in prepared:
        store = VibeStorage(":memory:")
        try:
            for turn_index, turn in enumerate(history):
                if turn["role"] == "system":
                    continue
                store.insert_atom(MemoryAtom(
                    id=f"{persona}:{turn_index}", agent_id=persona, session_id="history",
                    content=f'{turn["role"]}: {turn["content"]}', summary=f'{turn["role"]}: {turn["content"]}',
                    created_at=datetime(2026, 9, 28) + timedelta(microseconds=turn_index)))
            stored = store.get_atoms_by_agent(persona)
            if len(stored) != sum(turn["role"] != "system" for turn in history):
                raise ValueError("dialogue write count mismatch")
            documents = [atom.content for atom in stored]
            key = tuple((atom.id, atom.version) for atom in stored)
            bm25 = BM25Strategy()
            bm25.fit(documents)
            tfidf = TfidfProvider().fit(documents)
            encoding_ms = {}
            if previous_context:
                context_documents = preceding_texts(stored)
                matrices = {}
                for name in (("baseline", "previous_context") if index % 2 == 0 else ("previous_context", "baseline")):
                    start = perf_counter() if include_timing else None
                    matrices[name] = provider.encode(documents if name == "baseline" else context_documents)
                    if include_timing:
                        encoding_ms[name] = (perf_counter() - start) * 1000
                vectors = matrices["baseline"]
            else:
                vectors = provider.encode(documents)
            if provider.name == "tfidf(fallback)":
                raise RuntimeError("MiniLM fallback forbidden")
            arms = {}
            traces = {}
            evidence_ids = {f"{persona}:{i}" for i in evidence}
            for name in (("tfidf", "model") if index % 2 == 0 else ("model", "tfidf")):
                ids, stages = _recall_with_stages(
                    store, query, causal_bridge=False, agent_id=persona,
                    embedding_provider=tfidf if name == "tfidf" else provider,
                    semantic_cache=({"key": key, "tfidf_fitted": True} if name == "tfidf" else {"key": key, "vectors": vectors}),
                    bm25_cache={"key": key, "index": bm25})
                arms[name] = ids
                if stage_reference is not None:
                    traces[name] = stage_diagnosis(evidence_ids, stages)
            lexical = [(stored[i].id, score) for i, score in bm25.search(query, top_k=5)]
            arms["rank_fusion"] = rank_fused_ids(arms["model"], lexical)
            if stage_reference is not None:
                inputs = {"model_final": arms["model"],
                          "positive_bm25": [atom_id for atom_id, score in lexical if score > 0]}
                traces["rank_fusion"] = {
                    "input_ids": inputs,
                    "evidence_input_ranks": {atom_id: {name: _rank(ids, atom_id) for name, ids in inputs.items()}
                                             for atom_id in sorted(evidence_ids)},
                    "snippet_in_input_union": bool(evidence_ids.intersection(set().union(*map(set, inputs.values()))))}
            metrics = {}
            for name, ids in arms.items():
                found = set(ids) & evidence_ids
                metrics[name] = {"ids": ids, "snippet_any_hit": bool(found),
                                 "whole_snippet_covered": found == evidence_ids,
                                 "snippet_turn_recall": len(found) / len(evidence_ids)}
            rows.append({"row_index": index, "persona_id": persona, "history_path": path,
                         "history_sha256": HISTORIES[persona], "history_bytes": byte_count,
                         "original_message_count": len(history), "stored_dialogue_count": len(stored),
                         "excluded_system_count": sum(turn["role"] == "system" for turn in history),
                         "evidence_original_indices": evidence, "arms": metrics})
            if stage_reference is not None:
                rows[-1]["traces"] = traces
            if full_ranks:
                atom_ids = [atom.id for atom in stored]
                tf_indices, tf_scores = tfidf.search(query, top_k=len(stored))
                model_indices, model_scores = index_flat(vectors, provider.encode_query(query), top_k=len(stored))
                full = {name: rank_positions(atom_ids, ranked, evidence_ids) for name, ranked in (
                    ("tfidf_semantic", list(zip(tf_indices, tf_scores))),
                    ("model_semantic", list(zip(model_indices, model_scores))),
                    ("bm25", bm25.search(query, top_k=len(stored))))}
                if (full["tfidf_semantic"]["top5_ids"] != traces["tfidf"]["ids"]["semantic"]
                        or full["model_semantic"]["top5_ids"] != traces["model"]["ids"]["semantic"]
                        or any(full["bm25"]["top5_ids"] != traces[arm]["ids"]["bm25"] for arm in ("tfidf", "model"))):
                    raise ValueError("full-ranking prefix does not reproduce production route Top-5")
                rows[-1]["full_route_ranks"] = full
            if previous_context:
                context_ids, context_stages = _recall_with_stages(
                    store, query, causal_bridge=False, agent_id=persona, embedding_provider=provider,
                    semantic_cache={"key": key, "vectors": matrices["previous_context"]},
                    bm25_cache={"key": key, "index": bm25})
                if context_stages["bm25"] != traces["model"]["ids"]["bm25"]:
                    raise ValueError("context representation changed lexical route")
                probe = {"protocol_id": "preceding-turn-context-v1", "candidate_ids": context_ids,
                         "candidate_trace": stage_diagnosis(evidence_ids, context_stages),
                         "encoded_characters": {"baseline": sum(map(len, documents)), "previous_context": sum(map(len, context_documents))},
                         "vector_bytes": {name: matrix.nbytes for name, matrix in matrices.items()},
                         "task": {"988": "other_person", "782": "implicit_self_preference", "730": "ask_to_forget"}[persona]}
                for name, ids in (("baseline", arms["model"]), ("previous_context", context_ids)):
                    found = evidence_ids.intersection(ids)
                    probe[name] = {"snippet_any_hit": bool(found), "snippet_turn_recall": len(found) / len(evidence_ids)}
                    if persona == "730":
                        probe[name]["forget_risk_ranks"] = {label: _rank(ids, f"730:{turn}") for label, turn in (
                            ("old_standalone_fact", 108), ("forget_instruction", 109), ("forget_confirmation", 110))}
                if include_timing:
                    times = {"baseline": [], "previous_context": []}
                    for trial in range(5):
                        for name in (("baseline", "previous_context") if (index + trial) % 2 == 0 else ("previous_context", "baseline")):
                            start = perf_counter()
                            ids, _ = _recall_with_stages(
                                store, query, causal_bridge=False, agent_id=persona, embedding_provider=provider,
                                semantic_cache={"key": key, "vectors": matrices[name]}, bm25_cache={"key": key, "index": bm25})
                            times[name].append((perf_counter() - start) * 1000)
                            if ids != (arms["model"] if name == "baseline" else context_ids):
                                raise ValueError("warm query ranking changed across repeats")
                    probe["timing"] = {"corpus_encoding_ms": encoding_ms, "warm_query_ms": times,
                                       "limits": "Model preloaded; one encoding per arm/case, five warmed query repeats. Includes stage-capture overhead; excludes download/model load/SQLite write/BM25 setup and context-text construction. Not SDK/MCP onboarding, peak RAM, electricity or a user SLA."}
                if [atom.content for atom in store.get_atoms_by_agent(persona)] != documents:
                    raise ValueError("context experiment modified original stored text")
                rows[-1]["context_probe"] = probe
        finally:
            store.conn.close()
    result = {"dataset": "bowen-upenn/PersonaMem-v2", "revision": REVISION, "license": "CC-BY-4.0",
            "source_sha256": CSV_SHA256, "source_bytes": len(source_raw), "source_rows": len(all_rows),
            "selection": "fixed first three val_text rows; text 32k; adapter smoke only",
            "candidate_rows": 3, "uniquely_mapped_rows": len(prepared), "excluded_rows": [],
            "model_weight_sha256": model_hash, "rows": rows, "paid_api_calls": 0,
            "eligible_for_default": False, "evaluation_is_independent": False,
            "production_defaults_changed": False,
            "provenance": "Mirror downloads at pinned publisher revision. CSV SHA-256 matches official file page; revision verified against official commit page. History SHA-256 values are locally pinned, not independently cross-checked with official per-file hashes. Snippets fully match each downloaded history.",
            "limits": "First-three adapter smoke on publisher LLM-generated data; no benchmark score, human relevance review or final-answer accuracy. Related snippets include generic openings, not minimal fact-bearing gold turns. System profiles excluded; queries/answers/preference metadata not stored. Direct SQLite writes and unchanged warm core retrieval, not SDK/MCP end-to-end. No real timestamps/session IDs published here; synthetic microsecond order used, no causal edges. No timing, memory, electricity or onboarding claims; downloaded subset now exposed and cannot be called fresh after future tuning."}
    if stage_reference is not None:
        reference_raw = stage_reference.read_bytes()
        without_traces = {**result, "rows": [{k: v for k, v in row.items() if k not in ("traces", "full_route_ranks", "context_probe")} for row in rows]}
        if without_traces != json.loads(reference_raw):
            raise ValueError("stage replay differs from original smoke report")
        result["stage_reference_sha256"] = hashlib.sha256(reference_raw).hexdigest()
        result["replay_match_rows"] = len(rows)
        result["stage_limits"] = "Observed presence/ranks only, not a ranking intervention. final_rerank means present in fused Top-10, absent from final Top-5; not necessarily demoted from fused Top-5 or proof of causal harm. Related spans are not minimal preference-fact gold. No corpus reduction or ranking fix."
    if full_ranks:
        result["full_rank_limits"] = "Unchanged final Top-5, full original corpus. Ranking positions/scores only; semantic zero-score padding distinguished from positive matches, BM25 unscored turns absent. Top-5 prefixes verified against actual core stages. No candidate-depth intervention, cutoff sweep, timing/cost or answer-quality measurement. Nearest related-span rank is not a recommended cutoff or proof of factual preference retrieval."
    if previous_context:
        result["context_limits"] = "Exploratory representation intervention on exposed first-three rows, not independent evaluation. Original stored/returned turns, BM25 and final Top-5 unchanged; semantic seeds, downstream graph results and similarity reranking may change due to the one representation intervention. Task metadata used only for scoring, not retrieval. Related spans are not uniformly positive targets: others, implicit self preference, and ask-to-forget disclosed separately. Prior fact 108 retrieval is a risk indicator, not final-answer misuse; no natural-language forgetting action or SDK deletion was performed. No production defaults, model download, paid API or answers. Default report excludes timing; explicit timing is bounded local core cost, not onboarding/peak RAM/electricity. encoded_characters counts supplied strings before tokenizer truncation, not actual encoded tokens; unchanged model context limits may truncate the previous-turn suffix."
        result["limits"] = "Original smoke provenance and input constraints retained; added context_probe rows describe an actual representation intervention. See context_limits for task/quality boundaries and per-row explicit timing limits when present. Not a benchmark score or final-answer accuracy."
        result["stage_limits"] = "Baseline stage observations unchanged; added candidate_trace reflects the preceding-turn representation intervention, not a stage-disable ablation or forgetting implementation."
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--stage-reference", type=Path, help="Capture stages and require exact replay of this original smoke report")
    parser.add_argument("--full-ranks", action="store_true", help="Observe full-corpus route ranks without changing final Top-5; requires --stage-reference")
    parser.add_argument("--previous-context", action="store_true", help="Frozen preceding-turn MiniLM representation experiment; requires --stage-reference")
    parser.add_argument("--include-timing", action="store_true", help="Record bounded encoding/warm-query costs; requires --previous-context")
    args = parser.parse_args()
    if args.full_ranks and args.stage_reference is None:
        parser.error("--full-ranks requires --stage-reference")
    if args.previous_context and args.stage_reference is None or args.include_timing and not args.previous_context:
        parser.error("--previous-context requires --stage-reference; --include-timing requires --previous-context")
    result = run(args.directory, args.model_dir, args.stage_reference, args.full_ranks, args.previous_context, args.include_timing)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_rows": result["candidate_rows"], "uniquely_mapped_rows": result["uniquely_mapped_rows"], "stored_dialogue_counts": [row["stored_dialogue_count"] for row in result["rows"]]}))
