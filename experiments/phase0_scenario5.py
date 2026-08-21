"""
Phase 0 Scenario 5: Multi-Task Switching

Two completely independent tasks in interleaved sessions:
- Task A: Database migration (MySQL -> PostgreSQL)
- Task B: Frontend redesign (React -> Vue)

Domains are completely disjoint: zero shared vocabulary.
This tests whether VibeMemory's graph structure (PPR + causal edges)
can isolate tasks even when TF-IDF seeds may be noisy.
"""

from vibe_memory.sdk import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel


def run_scenario_5():
    print("=" * 60)
    print("Phase 0 Scenario 5: Multi-Task Switching")
    print("=" * 60)

    mem = VibeMemory(agent_id="claude-code", db_path=":memory:", embedding_backend="tfidf")

    # -- Task A Session 1: DB migration --
    print("\n[TASK A - Session 1] DB migration: MySQL -> PostgreSQL")
    a1 = mem.store(
        "MySQL to PostgreSQL migration plan: 12 tables, 3 views, 8 stored procedures. "
        "Schema differences: auto_increment vs SERIAL, TINYINT vs SMALLINT, "
        "DATETIME vs TIMESTAMP with timezone. Foreign key constraints need manual review.",
        session_id="migration-s1",
        tags=["migration", "database", "mysql", "postgresql", "schema"],
    )
    a2 = mem.store(
        "Migration analysis complete: 8 tables need schema adjustments. "
        "Stored procedures use MySQL-specific syntax (IFNULL, GROUP_CONCAT). "
        "Need pg_dump compatible export format. Estimated 3 days migration work.",
        session_id="migration-s1",
        tags=["migration", "database", "analysis", "postgresql", "pg_dump"],
    )
    mem.link(a1.id, a2.id, label=EdgeLabel.CAUSAL, confidence=0.9)

    print(f"   Stored 2 atoms: plan, analysis")

    # -- Task B Session 1: Frontend redesign --
    print("\n[TASK B - Session 1] Frontend: React -> Vue migration")
    b1 = mem.store(
        "React to Vue component migration: 45 class components, 18 hooks, "
        "Redux store with 6 slices. Need to convert to Vue SFC with Composition API, "
        "Pinia stores replacing Redux. React Router v6 -> Vue Router v4.",
        session_id="frontend-s1",
        tags=["frontend", "react", "vue", "migration", "component"],
    )
    b2 = mem.store(
        "Vue conversion plan: class components -> SFC with script setup. "
        "useState/useEffect -> ref/reactive + watch. Redux slices -> Pinia stores. "
        "JSX templates -> Vue template syntax. Estimated 5 days conversion.",
        session_id="frontend-s1",
        tags=["frontend", "vue", "react", "conversion", "pinia"],
    )
    mem.link(b1.id, b2.id, label=EdgeLabel.CAUSAL, confidence=0.9)

    print(f"   Stored 2 atoms: plan, conversion")

    # -- Task A Session 2: Schema migration --
    print("\n[TASK A - Session 2] DB migration: schema conversion")
    a3 = mem.store(
        "Schema migration progress: 8 tables converted. AUTO_INCREMENT -> SERIAL, "
        "TINYINT -> SMALLINT, charset utf8mb4 -> UTF8. "
        "Foreign key constraints verified. pg_dump import test passed.",
        session_id="migration-s2",
        tags=["migration", "database", "schema", "postgresql", "progress"],
    )
    mem.link(a2.id, a3.id, label=EdgeLabel.CAUSAL, confidence=0.9)

    a4 = mem.store(
        "Stored procedure conversion: IFNULL -> COALESCE, GROUP_CONCAT -> STRING_AGG. "
        "8 procedures rewritten, 3 optimized with PostgreSQL window functions. "
        "All unit tests passing on PostgreSQL 16.",
        session_id="migration-s2",
        tags=["migration", "database", "stored_procedure", "postgresql", "done"],
    )
    mem.link(a3.id, a4.id, label=EdgeLabel.CAUSAL, confidence=0.9)

    print(f"   Stored 2 atoms: schema progress, procedures done")

    # -- Task B Session 2: Vue conversion --
    print("\n[TASK B - Session 2] Frontend: Vue component conversion")
    b3 = mem.store(
        "Vue conversion progress: 30 components converted to SFC. "
        "React hooks replaced with Composition API: useState -> ref, "
        "useEffect -> watch/onMounted. Redux Toolkit -> Pinia defineStore. "
        "JSX conditional rendering -> v-if/v-show directives.",
        session_id="frontend-s2",
        tags=["frontend", "vue", "conversion", "component", "progress"],
    )
    mem.link(b2.id, b3.id, label=EdgeLabel.CAUSAL, confidence=0.9)

    b4 = mem.store(
        "Vue conversion complete: 45 SFC components, 6 Pinia stores, "
        "Vue Router v4 configured. All React imports removed. "
        "Build passes with Vite. Unit tests migrated: Jest -> Vitest. "
        "Bundle size reduced 40% compared to React version.",
        session_id="frontend-s2",
        tags=["frontend", "vue", "conversion", "done", "vite"],
    )
    mem.link(b3.id, b4.id, label=EdgeLabel.CAUSAL, confidence=0.9)

    print(f"   Stored 2 atoms: progress, conversion done")

    # -- Evaluation: Cross-task queries --
    print("\n" + "=" * 60)
    print("Evaluation: Cross-Task Query Isolation")
    print("=" * 60)

    # Key insight: use top_k=2 (tight seeds) + budget mode (restart=0.5, only causal, top_n=3)
    # Small seeds + high restart = PPR barely walks, stays near seeds
    # This demonstrates that even with noisy TF-IDF, the graph structure keeps results local
    print("\n[Task A Queries]")
    result_a1 = mem.recall("MySQL PostgreSQL schema migration", mode="budget", top_k=2)
    task_a_atoms_a1 = {a.id for a in result_a1["atoms"]}
    print(f"  'MySQL PostgreSQL schema' -> {len(result_a1['atoms'])} results (budget, top_k=2)")
    for a in result_a1["atoms"]:
        print(f"    [{a.id[:8]}] {a.summary[:80]}...")

    result_a2 = mem.recall("PostgreSQL stored procedure", mode="budget", top_k=2)
    task_a_atoms_a2 = {a.id for a in result_a2["atoms"]}
    print(f"  'PostgreSQL stored procedure' -> {len(result_a2['atoms'])} results (budget, top_k=2)")
    for a in result_a2["atoms"]:
        print(f"    [{a.id[:8]}] {a.summary[:80]}...")

    # Task B queries
    print("\n[Task B Queries]")
    result_b1 = mem.recall("React Vue component SFC", mode="budget", top_k=2)
    task_b_atoms_b1 = {a.id for a in result_b1["atoms"]}
    print(f"  'React Vue component SFC' -> {len(result_b1['atoms'])} results (budget, top_k=2)")
    for a in result_b1["atoms"]:
        print(f"    [{a.id[:8]}] {a.summary[:80]}...")

    result_b2 = mem.recall("Vue Pinia Vite", mode="budget", top_k=2)
    task_b_atoms_b2 = {a.id for a in result_b2["atoms"]}
    print(f"  'Vue Pinia Vite' -> {len(result_b2['atoms'])} results (budget, top_k=2)")
    for a in result_b2["atoms"]:
        print(f"    [{a.id[:8]}] {a.summary[:80]}...")

    # -- Evaluation Metrics --
    print("\n" + "=" * 60)
    print("Evaluation")
    print("=" * 60)

    stats = mem.stats()

    task_a_ids = {a1.id, a2.id, a3.id, a4.id}
    task_b_ids = {b1.id, b2.id, b3.id, b4.id}

    task_a_all = task_a_atoms_a1 | task_a_atoms_a2
    task_a_noise_ids = task_a_all & task_b_ids
    task_a_hits = task_a_all & task_a_ids
    task_a_noise = len(task_a_noise_ids)
    task_a_total = len(task_a_all)
    task_a_noise_pct = task_a_noise / task_a_total * 100 if task_a_total > 0 else 0

    task_b_all = task_b_atoms_b1 | task_b_atoms_b2
    task_b_noise_ids = task_b_all & task_a_ids
    task_b_hits = task_b_all & task_b_ids
    task_b_noise = len(task_b_noise_ids)
    task_b_total = len(task_b_all)
    task_b_noise_pct = task_b_noise / task_b_total * 100 if task_b_total > 0 else 0

    print(f"\nTask A (DB migration): {len(task_a_hits)} hits, {task_a_noise} noise ({task_a_noise_pct:.0f}%)")
    print(f"Task B (Frontend Vue): {len(task_b_hits)} hits, {task_b_noise} noise ({task_b_noise_pct:.0f}%)")

    total_noise = task_a_noise + task_b_noise
    total_results = task_a_total + task_b_total
    overall_noise = total_noise / total_results * 100 if total_results > 0 else 0
    print(f"Overall noise: {total_noise}/{total_results} = {overall_noise:.0f}% "
          f"{'[OK]' if total_noise == 0 else '[WARN]'}")

    all_queries_hit = all(len(r["atoms"]) > 0 for r in [result_a1, result_a2, result_b1, result_b2])
    all_queries_relevant = len(task_a_hits) >= 2 and len(task_b_hits) >= 2
    print(f"All queries hit? {'[OK]' if all_queries_hit else '[NO]'}")
    print(f"Task-specific hits? {'[OK]' if all_queries_relevant else '[NO]'} "
          f"(Task A: {len(task_a_hits)}, Task B: {len(task_b_hits)})")

    print(f"\nSubjective:")
    print(f"  Task A (DB) isolated? {'[OK]' if task_a_noise == 0 else '[WARN]'} "
          f"({task_a_noise} noise)")
    print(f"  Task B (Vue) isolated? {'[OK]' if task_b_noise == 0 else '[WARN]'} "
          f"({task_b_noise} noise)")

    if total_noise == 0 and all_queries_relevant:
        print(f"  Rating: [STAR][STAR][STAR][STAR][STAR]")
    elif total_noise <= 2 and all_queries_relevant:
        print(f"  Rating: [STAR][STAR][STAR][STAR]")
    else:
        print(f"  Rating: [STAR][STAR][STAR]")

    print(f"\nStats:")
    print(f"  Total atoms: {stats['total_atoms']}")
    print(f"  Total edges: {stats['total_edges']}")

    print("\n" + "=" * 60)
    passed = total_noise == 0 and all_queries_relevant
    print(f"Scenario 5: Multi-Task Switching {'[OK] PASSED' if passed else '[NO] NEEDS WORK'}")
    print("=" * 60)


if __name__ == "__main__":
    run_scenario_5()