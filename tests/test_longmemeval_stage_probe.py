"""Stage loss classification must include all four routes and final ranking."""

from experiments.longmemeval_stage_probe import loss_stage


def test_loss_stage_distinguishes_route_fusion_and_rerank_losses():
    stages = {name: [] for name in ("semantic", "bm25", "graph", "temporal", "fused", "final")}
    gold = {"evidence"}
    assert loss_stage(gold, stages) == "before_fusion"
    stages["temporal"] = ["evidence"]
    assert loss_stage(gold, stages) == "fusion_top10"
    stages["fused"] = ["noise1", "noise2", "noise3", "noise4", "noise5", "evidence"]
    assert loss_stage(gold, stages) == "final_rerank"
    stages["final"] = ["evidence"]
    assert loss_stage(gold, stages) == "retained"
