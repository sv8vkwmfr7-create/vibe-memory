"""Experiment-only MCP entry point; scoped bridge patch, production entry unchanged."""
from unittest.mock import patch
from vibe_memory import sdk
from vibe_memory.retrieval import fusion
from vibe_memory.models.memory_atom import EdgeLabel
from vibe_memory.mcp_server import main


original_recall = sdk._recall


def experimental_recall(query, agent_id, storage, **kwargs):
    if kwargs.get('mode', 'precision') != 'precision':
        return original_recall(query, agent_id, storage, **kwargs)
    original_fusion = fusion.rrf_fusion
    original_rerank = fusion.rerank_by_similarity
    supported = set()

    def merge(lists, *args, **options):
        if len(lists) >= 2:
            anchors = {key for key, _ in lists[0]} & {
                key for key, score in lists[1] if score > 0}
            primary = lists[0][0][0] if lists[0] else None
            neighbors = {}
            for edge in storage.get_retrieval_edges(agent_id, kwargs.get('tenant_id'),
                                                    atom_ids=list(anchors)):
                if edge.label != EdgeLabel.CAUSAL or edge.weight * edge.confidence < 0.05:
                    continue
                for node, anchor in ((edge.from_atom_id, edge.to_atom_id),
                                     (edge.to_atom_id, edge.from_atom_id)):
                    if anchor in anchors and node not in anchors:
                        neighbors.setdefault(node, set()).add(anchor)
            supported.update(node for node, links in neighbors.items()
                             if len(links) >= 2 and primary in links)
        return original_fusion(lists, *args, **options)

    def rerank(query_vec, candidates, doc_vectors, candidate_indices, top_k=20):
        ranked = original_rerank(query_vec, candidates, doc_vectors, candidate_indices,
                                 top_k=len(candidates))
        ranked.sort(key=lambda item: item[0] not in supported)
        return ranked[:top_k]

    # Sequential experiment server only; not safe as a concurrent production patch.
    with patch.object(fusion, 'rrf_fusion', merge), patch.object(
            fusion, 'rerank_by_similarity', rerank):
        return original_recall(query, agent_id, storage, **kwargs)


if __name__ == '__main__':
    with patch.object(sdk, '_recall', experimental_recall):
        main()
