"""
Episode 聚合层

分片→Episode→图，减少检索展开节点。
Episode = 同一话题的连续分片组。

话题检测（L1 原型）：
- 基于标签重叠 + 相邻分片相似度判断话题边界
- 后续升级为 Louvain/Leiden 社区检测
"""

import uuid
from typing import Optional
from datetime import datetime

from vibe_memory.models.memory_atom import MemoryAtom, Edge, Episode, EdgeLabel, EdgeSource, EdgeStatus


class EpisodeBuilder:
    """Episode 构建器"""

    def __init__(
        self,
        topic_switch_threshold: float = 0.3,  # 标签重叠率低于此值 → 话题切换
        min_episode_size: int = 2,              # 最小 Episode 大小（少于 N 个分片则不建 Episode）
    ):
        self.topic_switch_threshold = topic_switch_threshold
        self.min_episode_size = min_episode_size

    def build_episodes(
        self,
        atoms: list[MemoryAtom],
    ) -> list[Episode]:
        """
        将分片列表聚合为 Episode。

        算法：
        1. 按时间排序分片
        2. 滑动窗口检测话题边界：相邻分片标签重叠率 < 阈值 → 新 Episode
        3. 每个 Episode 生成摘要（取首个分片摘要 + 分片数量）
        """
        if not atoms:
            return []

        sorted_atoms = sorted(atoms, key=lambda a: a.created_at)
        episodes: list[Episode] = []
        current_atoms: list[MemoryAtom] = []

        for i, atom in enumerate(sorted_atoms):
            if i == 0:
                current_atoms.append(atom)
                continue

            prev = sorted_atoms[i - 1]
            overlap = _tag_overlap_ratio(atom, prev)

            if overlap < self.topic_switch_threshold:
                # 话题切换：保存当前 Episode
                if len(current_atoms) >= self.min_episode_size:
                    episodes.append(self._make_episode(current_atoms, atom.agent_id))
                current_atoms = [atom]
            else:
                current_atoms.append(atom)

        # 最后一个 Episode
        if len(current_atoms) >= self.min_episode_size:
            episodes.append(self._make_episode(current_atoms, atoms[0].agent_id))

        return episodes

    def _make_episode(
        self,
        atoms: list[MemoryAtom],
        agent_id: str,
    ) -> Episode:
        """从分片列表创建 Episode"""
        topic = _infer_topic(atoms)
        summary = f"[{topic}] {atoms[0].summary} ... ({len(atoms)} chunks)"

        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            session_id=atoms[0].session_id,
            summary=summary,
            topic=topic,
            atom_ids=[a.id for a in atoms],
            started_at=atoms[0].created_at,
            ended_at=atoms[-1].created_at,
            weight=1.0,
        )

        # 更新分片的 episode_id
        for pos, atom in enumerate(atoms):
            atom.episode_id = episode.id
            atom.episode_position = pos

        return episode


def build_episode_edges(
    episodes: list[Episode],
    atoms: list[MemoryAtom],
) -> list[Edge]:
    """
    在 Episode 之间建边。

    规则：
    - 同一会话内相邻 Episode → 时序相邻边
    - 跨会话 Episode 共享话题 → 同类经验边
    """
    edges: list[Edge] = []
    atom_map = {a.id: a for a in atoms}

    for i in range(len(episodes)):
        for j in range(i + 1, len(episodes)):
            ep_a = episodes[i]
            ep_b = episodes[j]

            # 同一会话：相邻 Episode 建时序边
            if ep_a.session_id == ep_b.session_id:
                # 检查是否相邻
                edge = Edge(
                    id=str(uuid.uuid4()),
                    from_atom_id=ep_a.atom_ids[-1],  # 上一个 Episode 的最后一个分片
                    to_atom_id=ep_b.atom_ids[0],     # 下一个 Episode 的第一个分片
                    label=EdgeLabel.ADJACENT,
                    confidence=0.3,
                    source=EdgeSource.RULE,
                    created_at=datetime.now(),
                    status=EdgeStatus.ACTIVE,
                )
                edges.append(edge)
                break  # 同会话只建相邻

            # 跨会话：共享话题 → 同类经验
            if ep_a.topic == ep_b.topic:
                edge = Edge(
                    id=str(uuid.uuid4()),
                    from_atom_id=ep_a.atom_ids[0],
                    to_atom_id=ep_b.atom_ids[0],
                    label=EdgeLabel.SIMILAR,
                    confidence=0.6,
                    source=EdgeSource.RULE,
                    created_at=datetime.now(),
                    status=EdgeStatus.ACTIVE,
                )
                edges.append(edge)

    return edges


def _tag_overlap_ratio(a: MemoryAtom, b: MemoryAtom) -> float:
    """标签重叠率"""
    set_a = set(a.tags)
    set_b = set(b.tags)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _infer_topic(atoms: list[MemoryAtom]) -> str:
    """
    从分片列表推断话题标签。

    统计所有分片标签中出现频率最高的标签作为话题。
    """
    from collections import Counter
    all_tags = []
    for atom in atoms:
        all_tags.extend(atom.tags)
    if not all_tags:
        return "general"
    counter = Counter(all_tags)
    return counter.most_common(1)[0][0]