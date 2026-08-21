"""
Graph Module

M2 图分区 + 社区检测。
- GraphPartitionManager: Session/Document/Parametric 三张独立图
- LouvainCommunityDetector: 模块度最优化的社区检测
"""

from vibe_memory.graph.partition import GraphPartitionManager
from vibe_memory.graph.community import LouvainCommunityDetector

__all__ = ["GraphPartitionManager", "LouvainCommunityDetector"]