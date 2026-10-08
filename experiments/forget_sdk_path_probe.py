"""Trace real SDK seed, batch/episode and merge forgetting with disposable synthetic data."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from vibe_memory import VibeMemory


FACT = "Configuration display color preference is violet."
QUERY = "display color preference violet"
FIXTURE = Path(__file__).parent / "fixtures" / "forget_seed_fixture.json"


def contains_fact(atoms, fields=("content", "summary")):
    return any("violet" in getattr(atom, field).lower() for atom in atoms for field in fields)


def seed_trace(db):
    memory = VibeMemory(agent_id="seed-trace", db_path=db, embedding_backend="tfidf")
    try:
        memory.cold_start.seed_memory_path = str(FIXTURE)
        original = memory.cold_start.bootstrap()[0]
        before = memory.recall(QUERY)["atoms"]
        deleted = memory.forget(original.id)
        after = memory.recall(QUERY)["atoms"]
        report = {
            "stored_source": original.source,
            "persisted_clone_recalled_before_forget": original.id in {a.id for a in before},
            "forget_returned_true": deleted,
            "rows_after_forget": memory.storage.count_atoms_by_agent(memory.agent_id),
            "persisted_clone_not_returned_after_forget": original.id not in {a.id for a in after},
            "unpersisted_template_returned_after_forget": any(
                a.agent_id == "__seed__" and "violet" in a.content and memory.storage.get_atom(a.id) is None
                for a in after),
            "mac_prompt_contains_fact_after_forget": "violet" in memory.inject(QUERY).lower(),
            "same_client_rebootstrap_count": len(memory.cold_start.bootstrap()),
        }
    finally:
        memory.storage.conn.close()
    memory = VibeMemory(agent_id="seed-trace", db_path=db, embedding_backend="tfidf")
    try:
        report["reopen_without_seed_config_returns_fact"] = contains_fact(memory.recall(QUERY)["atoms"])
        memory.cold_start.seed_memory_path = str(FIXTURE)
        reimported = memory.cold_start.bootstrap()
        report["configured_rebootstrap_count"] = len(reimported)
        report["configured_rebootstrap_restores_fact_with_new_id"] = any(
            atom.id != original.id and memory.storage.get_atom(atom.id) is not None for atom in reimported)
    finally:
        memory.storage.conn.close()
    return report


def batch_episode_trace(db):
    memory = VibeMemory(agent_id="batch-trace", db_path=db, embedding_backend="tfidf")
    try:
        messages = [
            {"role": "user", "content": "Use violet for my display configuration."},
            {"role": "assistant", "content": FACT},
            {"role": "user", "content": "Keep calendar reminders enabled."},
            {"role": "assistant", "content": "Configuration calendar reminders remain enabled."},
            {"role": "user", "content": "Keep the calendar timezone at UTC."},
            {"role": "assistant", "content": "Configuration calendar timezone remains UTC."},
        ]
        stored = memory.store_batch(messages, session_id="batch-session")
        target = stored[0]
        episodes_before = memory.storage.get_episodes_by_session("batch-session")
        if len(stored) != 3 or not contains_fact(memory.recall(QUERY)["atoms"]):
            raise RuntimeError("batch fixture must store three atoms and recall the target before deletion")
        deleted = memory.forget(target.id)
        survivors = memory.storage.get_atoms_by_agent(memory.agent_id)
        returned = memory.recall(QUERY)["atoms"]
        episodes_after = memory.storage.get_episodes_by_session("batch-session")
        report = {
            "stored_assistant_atoms": len(stored),
            "all_atom_sources_are_session_id": all(a.source == "batch-session" for a in stored),
            "episodes_before_forget": len(episodes_before),
            "forget_returned_true": deleted,
            "target_row_absent": memory.storage.get_atom(target.id) is None,
            "surviving_atom_count": len(survivors),
            "surviving_context_contains_fact": contains_fact(survivors, ("context_before", "context_after")),
            "returned_atom_context_contains_fact": contains_fact(returned, ("context_before", "context_after")),
            "returned_content_or_summary_contains_fact": contains_fact(returned),
            "mac_prompt_contains_fact_after_forget": "violet" in memory.inject(QUERY).lower(),
            "episodes_after_forget": len(episodes_after),
            "episode_summary_contains_fact": any("violet" in ep.summary for ep in episodes_after),
            "episode_references_deleted_atom": any(target.id in ep.atom_ids for ep in episodes_after),
        }
        reimported = memory.store_batch(messages, session_id="batch-session")
        report["reimport_uses_fresh_ids"] = not {a.id for a in stored}.intersection(a.id for a in reimported)
        report["reimport_restores_recall"] = contains_fact(memory.recall(QUERY)["atoms"])
    finally:
        memory.storage.conn.close()
    return report


def merge_trace(db):
    memory = VibeMemory(agent_id="merge-trace", db_path=db, embedding_backend="tfidf")
    try:
        original = memory.store(FACT, session_id="first-source", tags=["config"], auto_episode=False)
        inserted_ids = []
        insert = memory.storage.insert_atom
        def observe_insert(atom):
            inserted_ids.append(atom.id)
            return insert(atom)
        memory.storage.insert_atom = observe_insert
        try:
            second = memory.store(FACT, session_id="second-source",
                                  tags=["config"], auto_episode=False)
        finally:
            memory.storage.insert_atom = insert
        second_parent_id = inserted_ids[0]
        live = memory.storage.get_atoms_by_agent(memory.agent_id)
        if len(live) != 1 or "violet" not in live[0].content:
            raise RuntimeError("identical fixture text must trigger the automatic merge path")
        merged = live[0]
        report = {
            "active_atom_count_after_two_stores": len(live),
            "both_parent_rows_absent": memory.storage.get_atom(original.id) is None and memory.storage.get_atom(second_parent_id) is None,
            "returned_second_atom_not_persisted": memory.storage.get_atom(second.id) is None,
            "returned_second_atom_is_live_merged": second.id == merged.id and memory.storage.get_atom(second.id) is not None,
            "source_names_immediate_parent_ids": merged.source == f"merged({original.id}, {second_parent_id})",
            "previous_version_points_to_deleted_parent": merged.previous_version_id == original.id,
            "merged_session_is_first_session_only": merged.session_id == "first-source",
            "original_source_sessions_not_in_merged_source": "first-source" not in merged.source and "second-source" not in merged.source,
            "forget_original_id_returned_true": memory.forget(original.id),
            "merged_fact_still_recalled": contains_fact(memory.recall(QUERY)["atoms"]),
            "forget_live_merged_id_returned_true": memory.forget(merged.id),
            "fact_recalled_after_live_delete": contains_fact(memory.recall(QUERY)["atoms"]),
        }
    finally:
        memory.storage.conn.close()
    return report


def run():
    with TemporaryDirectory(prefix="vibe-forget-sdk-paths-") as directory:
        seed = seed_trace(str(Path(directory) / "seed.db"))
        batch_episode = batch_episode_trace(str(Path(directory) / "batch.db"))
        merge = merge_trace(str(Path(directory) / "merge.db"))
    project = Path(__file__).resolve().parents[1]
    files = ("vibe_memory/sdk.py", "vibe_memory/coldstart.py", "vibe_memory/chunking/chunker.py",
             "vibe_memory/chunking/episode.py", "vibe_memory/edges/edge_builder.py",
             "vibe_memory/storage/sqlite_store.py", "vibe_memory/injection.py")
    return {"scenario": "synthetic_real_sdk_forget_path_trace",
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "seed_fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "sdk_file_sha256": {file: hashlib.sha256((project / file).read_bytes()).hexdigest() for file in files},
            "seed": seed, "batch_episode": batch_episode, "merge": merge,
            "production_changed": False, "evaluation_is_independent": False, "paid_api_calls": 0,
            "limits": "Three temporary synthetic TF-IDF databases; one explicitly configured seed template, six dialogue messages, "
                      "two single SDK stores with identical fact text and config tags. Actual SDK calls with a pass-through "
                      "insertion observer recording the incoming parent ID, no forced candidate classification or direct atom inserts. "
                      "Random UUIDs/timestamps omitted from the report; relationships tested using actual IDs. "
                      "Seed path is opt-in, not configured by default. Completed seed initialization suppresses template augmentation; "
                      "with zero stored rows recall/MAC no longer return this seed fact, and same-version rebootstrap adds zero clones. Surviving batch context retains old content; "
                      "affected Episode rows are invalidated on deletion, and the batch MAC prompt does not include the old fact. "
                      "This is not proof of complete derived-memory erasure. Automatic merging requires identical text; "
                      "store returns the live merged ID and deleting that ID works. No general provenance guarantee, dense-model "
                      "evaluation, SDK/MCP/HTTP release interface tests, final model answers, concurrency or physical/backups "
                      "erasure. Independent judgments and user time/price costs unmeasured; no real user data deleted."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"seed_prompt_restores_fact": result["seed"]["mac_prompt_contains_fact_after_forget"],
                      "episode_retains_fact": result["batch_episode"]["episode_summary_contains_fact"],
                      "stale_original_delete_succeeds": result["merge"]["forget_original_id_returned_true"]}))
