"""
Cold Start Manager (M3)

处理新 Agent 无历史记忆的启动问题。

三阶段：
- cold: atoms < 10 → 种子记忆注入 + 激进建边
- warmup: 10 <= atoms < 50 → 宽松阈值建边
- normal: atoms >= 50 → 标准操作

特性：
- 冷启动检测（分片数）
- 种子记忆：预定义知识分片，给新 Agent 一个起点
- 快速建边：冷启动阶段降低相似度阈值
- 召回增强：图稀疏时用种子记忆补充
- 自动退出：分片数达标后自动切换回正常模式
"""

import json
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime
from enum import Enum

from vibe_memory.models.memory_atom import MemoryAtom, GraphPartition, Lifecycle, DEFAULT_TENANT


class ColdPhase(str, Enum):
    """冷启动阶段"""
    COLD = "cold"        # atoms < 10: 种子 + 激进
    WARMUP = "warmup"    # 10 <= atoms < 50: 宽松
    NORMAL = "normal"    # atoms >= 50: 标准


class ColdStartManager:
    """
    冷启动管理器。

    绑定到特定 agent + tenant。检测当前阶段，调整建边阈值，
    管理种子记忆，增强冷启动期间的召回。

    Args:
        storage: VibeStorage 实例
        agent_id: Agent 标识
        tenant_id: 租户 ID
        embedding_provider: Embedding 提供者（用于种子记忆匹配）
        seed_memory_path: 种子记忆 JSON 文件路径（可选）
    """

    COLD_THRESHOLD = 10
    WARMUP_THRESHOLD = 50

    # Cold: 激进建边
    COLD_EDGE_SIMILARITY = 0.5   # normal: 0.7
    COLD_MERGE_SIMILARITY = 0.75  # normal: 0.9

    # Warmup: 宽松
    WARMUP_EDGE_SIMILARITY = 0.6
    WARMUP_MERGE_SIMILARITY = 0.8

    def __init__(
        self,
        storage,
        agent_id: str,
        tenant_id: str = DEFAULT_TENANT,
        embedding_provider=None,
        seed_memory_path: Optional[str] = None,
    ):
        self.storage = storage
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.embedding = embedding_provider
        self.seed_memory_path = seed_memory_path

        self._seed_atoms: list[MemoryAtom] = []
        self._bootstrapped = False
        self._cached_atom_count: Optional[int] = None

    # ── 阶段检测 ──

    @property
    def atom_count(self) -> int:
        """当前分片数（缓存友好的查询）"""
        if self._cached_atom_count is None:
            atoms = self.storage.get_atoms_by_agent(
                self.agent_id, tenant_id=self.tenant_id
            )
            self._cached_atom_count = len(atoms)
        return self._cached_atom_count

    def invalidate_cache(self) -> None:
        """使缓存失效（store/forget 后调用）"""
        self._cached_atom_count = None

    @property
    def phase(self) -> ColdPhase:
        """检测当前冷启动阶段"""
        count = self.atom_count
        if count < self.COLD_THRESHOLD:
            return ColdPhase.COLD
        elif count < self.WARMUP_THRESHOLD:
            return ColdPhase.WARMUP
        return ColdPhase.NORMAL

    @property
    def is_cold(self) -> bool:
        return self.phase == ColdPhase.COLD

    @property
    def is_warmup(self) -> bool:
        return self.phase == ColdPhase.WARMUP

    @property
    def is_normal(self) -> bool:
        return self.phase == ColdPhase.NORMAL

    # ── 阈值调整 ──

    def get_edge_similarity_threshold(self) -> float:
        """获取当前阶段调整后的建边相似度阈值"""
        phase = self.phase
        if phase == ColdPhase.COLD:
            return self.COLD_EDGE_SIMILARITY
        elif phase == ColdPhase.WARMUP:
            return self.WARMUP_EDGE_SIMILARITY
        return 0.7  # normal

    def get_merge_similarity_threshold(self) -> float:
        """获取当前阶段调整后的合并相似度阈值"""
        phase = self.phase
        if phase == ColdPhase.COLD:
            return self.COLD_MERGE_SIMILARITY
        elif phase == ColdPhase.WARMUP:
            return self.WARMUP_MERGE_SIMILARITY
        return 0.9  # normal

    # ── 种子记忆 ──

    def load_seed_memory(self) -> list[MemoryAtom]:
        """
        从 JSON 文件加载种子记忆。

        种子记忆 JSON 格式：
        {
            "version": "1.0",
            "domain": "general",
            "atoms": [
                {
                    "content": "...",
                    "summary": "...",
                    "tags": ["...", "..."],
                    "type": "session"
                }
            ]
        }

        Returns:
            加载的 MemoryAtom 列表（未持久化，仅内存）
        """
        if not self.seed_memory_path:
            return []

        path = Path(self.seed_memory_path)
        if not path.exists():
            return []

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        atoms = []
        for item in data.get("atoms", []):
            atom_type = item.get("type", "session")
            atom = MemoryAtom(
                id=str(uuid.uuid4()),
                agent_id="__seed__",
                session_id="__seed__",
                content=item["content"],
                summary=item.get("summary", item["content"][:200]),
                tags=item.get("tags", []),
                type=GraphPartition(atom_type) if atom_type in ["session", "document", "parametric"] else GraphPartition.SESSION,
                lifecycle=Lifecycle.ACTIVE,
                weight=0.5,
                decay_rate=0.95,
                confidence=0.8,
                source="seed_memory",
            )
            atoms.append(atom)

        self._seed_atoms = atoms
        return atoms

    def bootstrap(self) -> list[MemoryAtom]:
        """
        注入种子记忆到当前 agent。

        幂等：多次调用只注入一次。
        仅在 cold 阶段有实际效果。

        Returns:
            持久化后的 MemoryAtom 列表
        """
        if self._bootstrapped:
            return []

        atoms = self.load_seed_memory()
        if not atoms:
            self._bootstrapped = True
            return []

        stored = []
        for atom in atoms:
            cloned = MemoryAtom(
                id=str(uuid.uuid4()),
                agent_id=self.agent_id,
                session_id="__seed__",
                tenant_id=self.tenant_id,
                content=atom.content,
                summary=atom.summary,
                tags=list(atom.tags),
                type=atom.type,
                lifecycle=atom.lifecycle,
                weight=atom.weight,
                decay_rate=atom.decay_rate,
                confidence=atom.confidence,
                source="seed_memory",
            )
            self.storage.insert_atom(cloned)
            stored.append(cloned)

        self._bootstrapped = True
        self.invalidate_cache()
        return stored

    def get_seed_atoms(self) -> list[MemoryAtom]:
        """返回已加载的种子记忆（内存中的模板）"""
        if not self._seed_atoms:
            self.load_seed_memory()
        return self._seed_atoms

    # ── 召回增强 ──

    def augment_recall(self, query: str, ppr_result: dict) -> dict:
        """
        冷启动期间用种子记忆增强召回结果。

        只在 PPR 返回结果不足时触发增强。
        cold 阶段最少需要 5 条，warmup 阶段最少需要 3 条。

        Args:
            query: 查询文本
            ppr_result: PPR 检索结果 dict

        Returns:
            增强后的结果（可能包含 augmented/seed_count 字段）
        """
        phase = self.phase
        if phase == ColdPhase.NORMAL:
            return ppr_result

        atoms = ppr_result.get("atoms", [])
        min_results = 5 if phase == ColdPhase.COLD else 3

        if len(atoms) >= min_results:
            return ppr_result

        seed_atoms = self.get_seed_atoms()
        if not seed_atoms:
            return ppr_result

        # 用标签重叠率评分种子记忆
        query_lower = query.lower()
        scored = []
        for seed in seed_atoms:
            score = 0
            # 标签匹配
            for tag in seed.tags:
                if tag.lower() in query_lower:
                    score += 2
            # 内容关键词匹配
            seed_words = set(seed.content.lower().split())
            query_words = set(query_lower.split())
            common = seed_words & query_words
            score += len(common)
            if score > 0:
                scored.append((score, seed))

        scored.sort(key=lambda x: x[0], reverse=True)

        needed = min_results - len(atoms)
        augmented = [s[1] for s in scored[:needed]]

        if augmented:
            ppr_result["atoms"] = atoms + augmented
            ppr_result["augmented"] = True
            ppr_result["seed_count"] = len(augmented)

        return ppr_result

    # ── 统计 ──

    def stats(self) -> dict:
        """冷启动统计信息"""
        phase = self.phase
        seed_count = len(self._seed_atoms)

        return {
            "cold_start_phase": phase.value,
            "cold_start_atom_count": self.atom_count,
            "cold_threshold": self.COLD_THRESHOLD,
            "warmup_threshold": self.WARMUP_THRESHOLD,
            "seed_memory_loaded": seed_count > 0,
            "seed_memory_count": seed_count,
            "bootstrapped": self._bootstrapped,
            "edge_similarity_threshold": self.get_edge_similarity_threshold(),
            "merge_similarity_threshold": self.get_merge_similarity_threshold(),
        }