"""
Vibe Learner — 轻量级在线学习

Titans 启发：不训练 LLM 参数，而是训练一个微型决策器（几十KB），
在运行时根据反馈信号调整衰减速速率、建边阈值等参数。

反馈信号：
- 正反馈：分片被 Agent 实际采纳 → 确信度 +1
- 负反馈：分片被召回但 Agent 忽略 → 确信度 -1
- 无反馈：Agent 未引用 → 确信度微降

L1 原型：线性特征模型 + 简单 SGD 更新（无梯度框架依赖）。
"""

from typing import Optional
from datetime import datetime
from collections import defaultdict

from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel


class LearnerConfig:
    """Vibe Learner 配置"""

    def __init__(
        self,
        learning_rate: float = 0.01,
        default_decay_rate: float = 0.95,
        min_decay_rate: float = 0.80,
        max_decay_rate: float = 0.99,
        confidence_threshold: float = 0.3,
        window_size: int = 100,  # 滑动窗口大小（最近 N 次反馈）
    ):
        self.learning_rate = learning_rate
        self.default_decay_rate = default_decay_rate
        self.min_decay_rate = min_decay_rate
        self.max_decay_rate = max_decay_rate
        self.confidence_threshold = confidence_threshold
        self.window_size = window_size


class VibeLearner:
    """
    轻量级在线学习决策器。

    维护一个特征→权重的线性映射，根据反馈在线更新。
    不依赖梯度框架，纯 Python 实现。
    """

    def __init__(self, config: Optional[LearnerConfig] = None):
        self.cfg = config or LearnerConfig()

        # 特征权重（线性模型）
        self.weights: dict[str, float] = {
            "access_frequency": 0.0,      # 被检索频率 → 高频率应减速衰减
            "tag_count": 0.0,             # 标签数量 → 多标签可能有噪声
            "content_length": 0.0,        # 内容长度 → 长内容可能信息量大
            "edge_degree": 0.0,           # 边度数 → 高度数节点是枢纽
            "age_days": 0.0,              # 年龄 → 老分片可能过时
            "adopted_ratio": 0.0,         # 采纳率 → 高采纳率应保护
            "bias": 0.0,                  # 偏置项
        }

        # 反馈历史（滑动窗口）
        self.feedback_history: list[dict] = []
        self.total_positive: int = 0
        self.total_negative: int = 0
        self.total_ignored: int = 0

    def extract_features(self, atom: MemoryAtom) -> dict[str, float]:
        """从 MemoryAtom 提取特征"""
        days_since_created = (datetime.now() - atom.created_at).days
        total_feedback = atom.adopted_count + atom.ignored_count
        adopted_ratio = (
            atom.adopted_count / max(total_feedback, 1)
        )

        return {
            "access_frequency": min(atom.access_count / 10, 1.0),
            "tag_count": min(len(atom.tags) / 5, 1.0),
            "content_length": min(len(atom.content) / 2000, 1.0),
            "edge_degree": 0.0,  # 需要外部传入
            "age_days": min(days_since_created / 30, 1.0),
            "adopted_ratio": adopted_ratio,
            "bias": 1.0,
        }

    def predict_decay_rate(
        self,
        atom: MemoryAtom,
        edge_degree: float = 0.0,
    ) -> float:
        """
        预测该分片的最优衰减速速率。

        输出范围 [min_decay_rate, max_decay_rate]。
        高采纳率、高访问频率 → 高 decay_rate（慢衰减）。
        低采纳率、高年龄 → 低 decay_rate（快衰减）。
        """
        features = self.extract_features(atom)
        features["edge_degree"] = min(edge_degree / 10, 1.0)

        # 线性组合
        score = sum(
            self.weights.get(k, 0.0) * v
            for k, v in features.items()
        )
        # Sigmoid 映射到 [min, max]
        import math
        sigmoid = 1.0 / (1.0 + math.exp(-score))
        decay = (
            self.cfg.min_decay_rate
            + sigmoid * (self.cfg.max_decay_rate - self.cfg.min_decay_rate)
        )
        return decay

    def predict_edge_confidence(
        self,
        atom_a: MemoryAtom,
        atom_b: MemoryAtom,
        base_confidence: float,
    ) -> float:
        """
        预测建边置信度是否应调整。

        如果两个分片特征相似（高访问频率、高采纳率），增加置信度。
        如果一方低采纳率，降低置信度。
        """
        feats_a = self.extract_features(atom_a)
        feats_b = self.extract_features(atom_b)

        # 特征相似度
        common_keys = ["access_frequency", "tag_count", "adopted_ratio"]
        similarity = 0.0
        for k in common_keys:
            similarity += 1.0 - abs(feats_a[k] - feats_b[k])
        similarity /= len(common_keys)

        # 调整：相似度高 → 略微提升置信度
        adjustment = (similarity - 0.5) * 0.2
        return max(0.0, min(1.0, base_confidence + adjustment))

    def record_feedback(
        self,
        atom: MemoryAtom,
        was_adopted: bool,
        was_ignored: bool = False,
    ) -> None:
        """
        记录反馈信号。

        Args:
            atom: 被召回的分片
            was_adopted: Agent 是否实际采纳
            was_ignored: 被召回但 Agent 忽略了
        """
        # 更新分片本身的统计
        if was_adopted:
            atom.learn_from_feedback(was_adopted=True)
            self.total_positive += 1
        elif was_ignored:
            atom.learn_from_feedback(was_adopted=False)
            self.total_negative += 1
        else:
            self.total_ignored += 1

        # 记录到滑动窗口
        features = self.extract_features(atom)
        self.feedback_history.append({
            "features": features,
            "was_adopted": was_adopted,
            "was_ignored": was_ignored,
            "timestamp": datetime.now(),
        })

        # 滑动窗口截断
        if len(self.feedback_history) > self.cfg.window_size:
            self.feedback_history = self.feedback_history[-self.cfg.window_size:]

        # 在线更新权重
        self._update_weights()

    def _update_weights(self) -> None:
        """
        基于滑动窗口内的反馈，在线更新特征权重。

        简单的 SGD 更新：
        - 正反馈：增加特征权重（该特征利于采纳）
        - 负反馈：降低特征权重（该特征导致误召回）
        """
        if len(self.feedback_history) < 10:
            return  # 样本不足，不更新

        lr = self.cfg.learning_rate

        for entry in self.feedback_history[-20:]:  # 只用最近 20 条
            features = entry["features"]
            target = 1.0 if entry["was_adopted"] else -0.5

            # 对每个特征做 SGD 更新
            for feat_name, feat_val in features.items():
                if feat_name not in self.weights:
                    continue
                # 预测值
                pred = self.weights[feat_name] * feat_val
                # 误差
                error = target - pred
                # 更新
                self.weights[feat_name] += lr * error * feat_val

    def get_stats(self) -> dict:
        """获取学习器统计（可观测性）"""
        return {
            "total_positive": self.total_positive,
            "total_negative": self.total_negative,
            "total_ignored": self.total_ignored,
            "feedback_window_size": len(self.feedback_history),
            "weights": dict(self.weights),
            "adoption_rate": (
                self.total_positive
                / max(self.total_positive + self.total_negative + self.total_ignored, 1)
            ),
        }


class DecayManager:
    """
    衰减管理器：统一管理分片和边的衰减。

    整合 Vibe Learner 的预测衰减速速率。
    如果 Learner 不可用，降级为固定衰减速率 0.95。
    """

    def __init__(self, learner: Optional[VibeLearner] = None):
        self.learner = learner
        self.default_decay_rate = 0.95

    def decay_atom(self, atom: MemoryAtom) -> None:
        """衰减一个分片"""
        if self.learner:
            # 用 Learner 预测的衰减速速率
            atom.decay_rate = self.learner.predict_decay_rate(atom)
        else:
            # 降级：固定速率
            atom.decay_rate = self.default_decay_rate

        atom.decay()

    def decay_edge(self, edge: Edge) -> None:
        """衰减一条边"""
        if edge.last_accessed is None:
            return
        days = (datetime.now() - edge.last_accessed).days
        if days > 0:
            edge.weight *= edge.decay_rate ** days
            edge.weight = max(0.0, min(1.0, edge.weight))

    def decay_all(
        self,
        atoms: list[MemoryAtom],
        edges: list[Edge],
    ) -> None:
        """批量衰减所有分片和边"""
        for atom in atoms:
            self.decay_atom(atom)
        for edge in edges:
            self.decay_edge(edge)

    def reinforce_atom(self, atom: MemoryAtom) -> None:
        """强化一个被检索命中的分片"""
        atom.reinforce()

    def reinforce_edge(self, edge: Edge) -> None:
        """强化一条被遍历的边"""
        edge.reinforce()