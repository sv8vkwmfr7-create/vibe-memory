from contextlib import ExitStack

import pytest

from vibe_memory import VibeMemory
from vibe_memory.models.memory_atom import EdgeLabel, EdgeStatus


@pytest.mark.parametrize("mode", ["precision", "recall", "budget"])
def test_graph_recall_observes_other_connection_links_and_deletion(tmp_path, mode):
    path = str(tmp_path / "graph.db")
    with ExitStack() as stack:
        reader, writer = [
            stack.enter_context(VibeMemory("graph-visibility", path, embedding_backend="tfidf"))
            for _ in range(2)
        ]
        seeds = [
            writer.store(f"nebula incident {word}", session_id="incident",
                         auto_build_edges=False, auto_episode=False)
            for word in ("alpha", "beta", "gamma")
        ]
        cause = writer.store("certificate expired", session_id="cause",
                             auto_build_edges=False, auto_episode=False)
        for seed in seeds[:2]:
            assert writer.link(cause.id, seed.id, label=EdgeLabel.CAUSAL)
        first = reader.recall("nebula incident", mode=mode, top_k=10)
        assert cause.id in {atom.id for atom in first["atoms"]}
        assert first["failures"] == []
        assert any({edge["from"], edge["to"]} in (
                       {cause.id, seeds[0].id}, {cause.id, seeds[1].id})
                   for edge in first["trace"])

        replacement = writer.store("credential revoked", session_id="replacement",
                                   auto_build_edges=False, auto_episode=False)
        for seed in seeds[:2]:
            assert writer.link(replacement.id, seed.id, label=EdgeLabel.CAUSAL)
        assert writer.forget(cause.id)
        assert writer.update(seeds[0].id, summary="updated evidence")
        second = reader.recall("nebula incident", mode=mode, top_k=10)
        ids = {atom.id for atom in second["atoms"]}
        assert replacement.id in ids
        assert cause.id not in ids
        assert second["failures"] == []
        assert all(cause.id not in (edge["from"], edge["to"]) for edge in second["trace"])
        assert any({edge["from"], edge["to"]} in (
                       {replacement.id, seeds[0].id}, {replacement.id, seeds[1].id})
                   for edge in second["trace"])
        assert next(atom for atom in second["atoms"] if atom.id == seeds[0].id).summary == "updated evidence"
        assert reader.history("cause") == []
        for edge in writer.storage.get_edges_by_agent(writer.agent_id):
            edge.status = EdgeStatus.STALE
            writer.storage.update_edge(edge)
        third = reader.recall("nebula incident", mode=mode, top_k=10)
        assert replacement.id not in {atom.id for atom in third["atoms"]}
        assert third["trace"] == []
        assert third["failures"] == []


@pytest.mark.parametrize("mode", ["precision", "recall", "budget"])
@pytest.mark.parametrize("other_owner", [("tenant-b", "shared"), ("tenant-a", "other")])
def test_graph_recall_keeps_foreign_owner_records_and_relationships_isolated(tmp_path, mode, other_owner):
    path = str(tmp_path / "owners.db")
    with VibeMemory("shared", path, tenant_id="tenant-a", embedding_backend="tfidf") as memory, \
            VibeMemory(other_owner[1], path, tenant_id=other_owner[0], embedding_backend="tfidf") as other:
        seeds = [
            memory.store(f"nebula incident {word}", auto_build_edges=False, auto_episode=False)
            for word in ("alpha", "beta", "gamma")
        ]
        cause = memory.store("certificate expired", auto_build_edges=False, auto_episode=False)
        assert memory.link(cause.id, seeds[0].id, label=EdgeLabel.CAUSAL)
        foreign = other.store("nebula incident foreign", session_id="foreign",
                              auto_build_edges=False, auto_episode=False)
        foreign_cause = other.store("private credential failure", session_id="foreign",
                                    auto_build_edges=False, auto_episode=False)
        assert other.link(foreign_cause.id, foreign.id, label=EdgeLabel.CAUSAL)
        assert memory.link(seeds[0].id, foreign.id, label=EdgeLabel.CAUSAL) is None
        result = memory.recall("nebula incident", mode=mode, top_k=10)
        assert cause.id in {atom.id for atom in result["atoms"]}
        assert all((atom.tenant_id, atom.agent_id) == ("tenant-a", "shared")
                   for atom in result["atoms"])
        foreign_ids = {foreign.id, foreign_cause.id}
        assert all(foreign_ids.isdisjoint((edge["from"], edge["to"])) for edge in result["trace"])
        assert all(atom.access_count == 0 for atom in other.history("foreign"))
        assert result["failures"] == []
