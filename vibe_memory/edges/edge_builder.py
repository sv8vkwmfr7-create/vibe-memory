"""
同会话建边模块

L1 原型：四分类规则（Bug 8 修复）
- 因果接续：有因果信号词
- 同类经验：无因果信号词 + 高语义相似度
- 时序相邻：无因果信号词 + 低语义相似度
- 不建边：话题切换

跨会话建边：KNN 预筛（三档）→ LLM 四分类（L1 用规则近似）
"""

from typing import Optional
from datetime import datetime
import uuid

from vibe_memory.models.memory_atom import MemoryAtom, Edge, EdgeLabel, EdgeSource, EdgeStatus


# 因果信号词列表
CAUSAL_SIGNALS = [
    "所以", "因此", "因为", "由于", "导致", "结果",
    "接下来", "然后", "于是", "从而", "故", "因而",
    "修改", "变更", "调整", "更新", "修复", "解决",
    "therefore", "because", "so", "thus", "hence",
    "update", "fix", "change", "modify", "resolve",
]


def build_same_session_edges(
    atoms: list[MemoryAtom],
) -> list[Edge]:
    """
    同会话建边：四分类规则（Bug 8 修复）。

    规则：
    1. 因果信号词检测 → "因果接续"
    2. 无信号词 + 同标签 → "同类经验"
    3. 无信号词 + 不同标签 → "时序相邻"（弱边）
    4. 话题切换（无共享标签）→ 不建边

    Args:
        atoms: 同会话的 MemoryAtom 列表（按时间排序）

    Returns:
        Edge 列表
    """
    edges: list[Edge] = []

    for i in range(len(atoms) - 1):
        a = atoms[i]
        b = atoms[i + 1]

        # 规则 1：因果信号词检测
        if _has_causal_signal(a.content) or _has_causal_signal(b.content):
            label = EdgeLabel.CAUSAL
            confidence = 0.9
        # 规则 2：有共享标签 → 同类经验
        elif _has_shared_tags(a, b):
            label = EdgeLabel.SIMILAR
            confidence = 0.7
        # 规则 3：无共享标签 → 时序相邻（弱边）
        else:
            label = EdgeLabel.ADJACENT
            confidence = 0.3

        edge = Edge(
            id=str(uuid.uuid4()),
            from_atom_id=a.id,
            to_atom_id=b.id,
            label=label,
            weight=1.0,
            confidence=confidence,
            source=EdgeSource.RULE,
            created_at=datetime.now(),
            status=EdgeStatus.ACTIVE,
        )
        edges.append(edge)

    return edges


def build_cross_session_candidates(
    new_atom: MemoryAtom,
    existing_atoms: list[MemoryAtom],
    high_similarity: float = 0.9,
    medium_similarity: float = 0.7,
) -> dict[str, list[MemoryAtom]]:
    """
    跨会话建边：KNN 预筛（Bug 1 修复）。

    三档分类：
    - 疑似重复: cos_sim > 0.9 → 触发合并检查
    - 疑似相似: 0.7 < cos_sim < 0.9 → 需要 LLM 复核
    - 无关噪声: cos_sim < 0.7 → 不建边

    L1 原型：用标签重叠率近似向量相似度（无 embedding 时）。
    后续接入 FAISS 后替换为真实 cos_sim。

    Args:
        new_atom: 新分片
        existing_atoms: 已有分片列表
        high_similarity: 高相似度阈值（默认 0.9）
        medium_similarity: 中相似度阈值（默认 0.7）

    Returns:
        {"duplicate": [...], "similar": [...], "noise": [...]}
    """
    result = {"duplicate": [], "similar": [], "noise": []}

    for existing in existing_atoms:
        if existing.session_id == new_atom.session_id:
            continue

        sim = _tag_overlap_ratio(new_atom, existing)

        if sim >= high_similarity:
            result["duplicate"].append(existing)
        elif sim >= medium_similarity:
            result["similar"].append(existing)
        else:
            result["noise"].append(existing)

    return result


def classify_cross_session_edge(
    atom_a: MemoryAtom,
    atom_b: MemoryAtom,
    llm_classify=None,  # L1 原型：可选 LLM 回调
) -> tuple[EdgeLabel, float]:
    """
    跨会话 LLM 四分类（Bug 1 + Bug 4 修复）。

    L1 原型：用规则近似 LLM 分类。
    后续接入 LLM 时，传入包含上下文（context_before/after）的 prompt。

    Args:
        atom_a: 新分片（含 context）
        atom_b: 已有分片（含 context）
        llm_classify: LLM 分类回调（L1 为 None，用规则）

    Returns:
        (EdgeLabel, confidence)
    """
    if llm_classify:
        return llm_classify(atom_a, atom_b)

    # L1 规则近似：标签重叠率 + 因果信号词
    overlap = _tag_overlap_ratio(atom_a, atom_b)

    if _has_causal_signal(atom_a.content) and _has_causal_signal(atom_b.content):
        return EdgeLabel.CAUSAL, 0.7

    if overlap >= 0.5:
        return EdgeLabel.SIMILAR, 0.6

    return EdgeLabel.SIMILAR, 0.4  # 低置信度，待 LLM 复核


def _has_causal_signal(text: str) -> bool:
    """检测文本中是否包含因果信号词"""
    text_lower = text.lower()
    return any(signal in text_lower for signal in CAUSAL_SIGNALS)


def _has_shared_tags(a: MemoryAtom, b: MemoryAtom) -> bool:
    """判断两个分片是否有共享标签"""
    return bool(set(a.tags) & set(b.tags))


def _tag_overlap_ratio(a: MemoryAtom, b: MemoryAtom) -> float:
    """
    标签重叠率：|A ∩ B| / |A ∪ B|

    无 embedding 时的近似相似度。后续替换为 cos_sim。
    """
    set_a = set(a.tags)
    set_b = set(b.tags)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def merge_atoms(
    atom_a: MemoryAtom,
    atom_b: MemoryAtom,
) -> MemoryAtom:
    """
    合并两个高度相似的分片（Bug 12 压缩优先）。

    合并后的分片继承两者的所有边。
    """
    merged = MemoryAtom(
        id=str(uuid.uuid4()),
        agent_id=atom_a.agent_id,
        session_id=atom_a.session_id,
        content=f"{atom_a.content}\n---\n{atom_b.content}",
        summary=f"{atom_a.summary} | {atom_b.summary}",
        type=atom_a.type,
        tags=list(set(atom_a.tags + atom_b.tags)),
        weight=max(atom_a.weight, atom_b.weight),
        decay_rate=max(atom_a.decay_rate, atom_b.decay_rate),
        access_count=atom_a.access_count + atom_b.access_count,
        adopted_count=atom_a.adopted_count + atom_b.adopted_count,
        ignored_count=atom_a.ignored_count + atom_b.ignored_count,
        created_at=min(atom_a.created_at, atom_b.created_at),
        source=f"merged({atom_a.id}, {atom_b.id})",
        confidence=min(atom_a.confidence, atom_b.confidence),
        context_before=atom_a.context_before,
        context_after=atom_b.context_after,
        version=max(atom_a.version, atom_b.version) + 1,
        previous_version_id=atom_a.id,
    )
    return merged