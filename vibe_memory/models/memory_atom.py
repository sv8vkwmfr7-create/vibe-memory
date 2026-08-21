"""
VibeMemory 核心数据结构

MemoryAtom: 标准化记忆单元（MemOS MemCube 启发）
Edge: 关系边（8 种边标签 + 连续衰减 + 时间戳）
Episode: 分片聚合层（话题检测 + 社区检测）
EdgeLabel: 边标签枚举
GraphPartition: 图分区枚举
TenantIsolation: 多租户隔离（M3）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class EdgeLabel(str, Enum):
    """边标签枚举（8 种）"""
    CAUSAL = "因果接续"       # A 导致了 B
    SIMILAR = "同类经验"       # A 和 B 是同一类问题/经验
    REVISION = "修正推翻"       # B 修正/推翻了 A 的结论
    ADJACENT = "时序相邻"       # A 和 B 在同一会话中相邻但无强因果
    REFERENCE = "引用"         # A 引用了 B（跨分区）
    LOOKUP = "查阅"            # session→document：Agent 检索了此文档
    INFLUENCE = "影响"         # document→session：文档影响了后续会话
    VERSION = "版本"           # B 是 A 的新版本


class GraphPartition(str, Enum):
    """图分区类型"""
    SESSION = "session"        # 会话记忆，高频读写
    DOCUMENT = "document"      # 文档记忆，低频读写
    PARAMETRIC = "parametric"  # Agent 画像，只读为主


class Lifecycle(str, Enum):
    """生命周期状态"""
    ACTIVE = "active"          # 热：7 天内访问
    WARM = "warm"              # 温：30 天内访问
    COLD = "cold"              # 冷：归档，按需加载
    ARCHIVED = "archived"      # 已归档，不参与检索


class EdgeSource(str, Enum):
    """边来源"""
    RULE = "rule"              # 规则生成
    LLM = "llm"                # LLM 复核
    LEARNER = "learner"        # Vibe Learner 学习


class EdgeStatus(str, Enum):
    """边状态"""
    ACTIVE = "active"          # 正常
    PENDING_REVIEW = "pending_review"  # 待 LLM 复核（降级边）
    STALE = "stale"            # 已过期


# 默认租户 ID（向后兼容）
DEFAULT_TENANT = "default"


@dataclass
class MemoryAtom:
    """
    标准化记忆单元

    整合 Bug 修复：
    - Bug 4: context_before/after 供 LLM 复核附上下文
    - Bug 8: episode_id 聚合
    - Bug 9: type 图分区
    - Bug 16: version 版本追踪
    - M3: tenant_id 多租户隔离
    """
    id: str
    agent_id: str
    session_id: str
    content: str
    summary: str
    embedding: Optional[list[float]] = None

    # 多租户（M3）
    tenant_id: str = "default"

    # 类型与分区
    type: GraphPartition = GraphPartition.SESSION
    tags: list[str] = field(default_factory=list)

    # 生命周期（连续衰减谱）
    lifecycle: Lifecycle = Lifecycle.ACTIVE
    weight: float = 1.0
    decay_rate: float = 0.95

    # 访问统计
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    adopted_count: int = 0
    ignored_count: int = 0

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    source: str = ""
    confidence: float = 1.0

    # 上下文（Bug 4）
    context_before: str = ""
    context_after: str = ""

    # Episode（Bug 8/14）
    episode_id: Optional[str] = None
    episode_position: int = 0

    # 版本（Bug 16）
    version: int = 1
    previous_version_id: Optional[str] = None

    def decay(self) -> None:
        """自然衰减：weight *= decay_rate ^ days_since_access"""
        if self.last_accessed is None:
            return
        days = (datetime.now() - self.last_accessed).days
        if days > 0:
            self.weight *= self.decay_rate ** days
            self.weight = max(0.0, min(1.0, self.weight))

    def reinforce(self) -> None:
        """Hebbian 强化：被检索命中"""
        self.weight = min(1.0, self.weight + 0.1)
        self.access_count += 1
        self.last_accessed = datetime.now()

    def learn_from_feedback(self, was_adopted: bool) -> None:
        """Vibe Learner 反馈（Bug 18）"""
        if was_adopted:
            self.adopted_count += 1
            self.decay_rate = min(0.99, self.decay_rate + 0.01)
        else:
            self.ignored_count += 1
            self.decay_rate = max(0.80, self.decay_rate - 0.01)

    def should_evict(self) -> bool:
        """是否应被淘汰（weight < 0.05）"""
        return self.weight < 0.05

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "content": self.content,
            "summary": self.summary,
            "type": self.type.value,
            "tags": self.tags,
            "lifecycle": self.lifecycle.value,
            "weight": self.weight,
            "decay_rate": self.decay_rate,
            "access_count": self.access_count,
            "adopted_count": self.adopted_count,
            "ignored_count": self.ignored_count,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "confidence": self.confidence,
            "episode_id": self.episode_id,
            "episode_position": self.episode_position,
            "version": self.version,
            "previous_version_id": self.previous_version_id,
        }


@dataclass
class Edge:
    """
    关系边

    整合 Bug 修复：
    - Bug 2: 双向可遍历，标签指示语义方向
    - Bug 3: 连续衰减 weight
    - Bug 5: pending_review 状态
    - Bug 6: created_at 时间戳
    - Bug 9: cross_partition 跨分区标记
    - Bug 17: REVISION 边类型
    - M3: tenant_id 多租户隔离
    """
    id: str
    from_atom_id: str
    to_atom_id: str
    label: EdgeLabel
    tenant_id: str = "default"
    weight: float = 1.0
    decay_rate: float = 0.95
    confidence: float = 0.9
    source: EdgeSource = EdgeSource.RULE
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: Optional[datetime] = None
    status: EdgeStatus = EdgeStatus.ACTIVE
    cross_partition: bool = False
    version: int = 1

    def decay(self) -> None:
        """自然衰减"""
        if self.last_accessed is None:
            return
        days = (datetime.now() - self.last_accessed).days
        if days > 0:
            self.weight *= self.decay_rate ** days
            self.weight = max(0.0, min(1.0, self.weight))

    def reinforce(self) -> None:
        """访问强化"""
        self.weight = min(1.0, self.weight + 0.1)
        self.last_accessed = datetime.now()

    def should_evict(self) -> bool:
        """是否应被淘汰"""
        return self.weight < 0.05

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_atom_id": self.from_atom_id,
            "to_atom_id": self.to_atom_id,
            "tenant_id": self.tenant_id,
            "label": self.label.value,
            "weight": self.weight,
            "decay_rate": self.decay_rate,
            "confidence": self.confidence,
            "source": self.source.value,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "cross_partition": self.cross_partition,
            "version": self.version,
        }


@dataclass
class Episode:
    """
    分片聚合层

    Bug 8/14: 分片→Episode→图，减少检索展开节点
    社区检测使用 Louvain/Leiden
    M3: tenant_id 多租户隔离
    """
    id: str
    agent_id: str
    session_id: str
    summary: str
    topic: str
    tenant_id: str = "default"
    atom_ids: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    community_id: Optional[str] = None
    weight: float = 1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def add_atom(self, atom_id: str, timestamp: datetime) -> None:
        """添加分片到 Episode"""
        self.atom_ids.append(atom_id)
        if self.started_at is None or timestamp < self.started_at:
            self.started_at = timestamp
        if self.ended_at is None or timestamp > self.ended_at:
            self.ended_at = timestamp

    def reinforce(self) -> None:
        self.weight = min(1.0, self.weight + 0.1)
        self.access_count += 1
        self.last_accessed = datetime.now()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "summary": self.summary,
            "topic": self.topic,
            "atom_ids": self.atom_ids,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "community_id": self.community_id,
            "weight": self.weight,
            "access_count": self.access_count,
        }