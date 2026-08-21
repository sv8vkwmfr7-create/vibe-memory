"""
语义分片模块

将会话文本切分为语义独立的 MemoryAtom，生成分片标签。
L1 原型：基于会话轮次切分 + LLM 生成标签。
"""

import uuid
from typing import Optional
from datetime import datetime

from vibe_memory.models.memory_atom import MemoryAtom, GraphPartition, Lifecycle


class ChunkingConfig:
    """分片配置"""
    def __init__(
        self,
        max_chunk_chars: int = 2000,
        context_window: int = 2,  # 前后保留轮次数（Bug 4: LLM 复核附上下文）
    ):
        self.max_chunk_chars = max_chunk_chars
        self.context_window = context_window


def chunk_session(
    messages: list[dict],
    agent_id: str,
    session_id: str,
    config: Optional[ChunkingConfig] = None,
) -> list[MemoryAtom]:
    """
    将会话消息列表切分为 MemoryAtom 列表。

    L1 策略：按会话轮次切分，每轮一组 user+assistant 为一个分片。
    后续可升级为语义漂移检测（embedding 相邻帧余弦相似度突降点）。

    Args:
        messages: [{"role": "user"/"assistant", "content": "..."}, ...]
        agent_id: Agent 标识
        session_id: 会话 ID
        config: 分片配置

    Returns:
        MemoryAtom 列表
    """
    cfg = config or ChunkingConfig()
    atoms: list[MemoryAtom] = []
    cw = cfg.context_window

    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            continue  # 以 assistant 回复为分片中心

        # 截取上下文
        ctx_before = _extract_context(messages, i, -cw, -1)
        ctx_after = _extract_context(messages, i, 1, cw)

        # 生成标签（L1：占位，实际由 LLM 生成）
        tags = _generate_tags(msg["content"])

        atom = MemoryAtom(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            session_id=session_id,
            content=msg["content"],
            summary=_truncate(msg["content"], 200),
            type=GraphPartition.SESSION,
            tags=tags,
            lifecycle=Lifecycle.ACTIVE,
            weight=1.0,
            created_at=datetime.now(),
            source=session_id,
            context_before=ctx_before,
            context_after=ctx_after,
            episode_position=i,
        )
        atoms.append(atom)

    return atoms


def _extract_context(
    messages: list[dict],
    center_idx: int,
    start_offset: int,
    end_offset: int,
) -> str:
    """提取中心消息前后 N 轮对话上下文"""
    parts: list[str] = []
    for j in range(center_idx + start_offset, center_idx + end_offset + 1):
        if 0 <= j < len(messages):
            role = messages[j].get("role", "unknown")
            parts.append(f"[{role}]: {messages[j]['content']}")
    return "\n".join(parts)


def _generate_tags(content: str) -> list[str]:
    """
    Generate chunk tags. L1: keyword matching, later upgrade to LLM auto-tagging.

    Tag categories:
    - error: error/exception/fail/timeout/bug
    - task: task/done/start/continue
    - query: search/query/lookup/find
    - config: config/setting/param/change/modify
    - decision: decision/choice/plan/solution
    """
    tags: list[str] = []
    content_lower = content.lower()

    # error
    if any(kw in content_lower for kw in ["error", "exception", "fail", "timeout", "bug"]):
        tags.append("error")
    # task
    if any(kw in content_lower for kw in ["task", "done", "start", "continue", "complete"]):
        tags.append("task")
    # query
    if any(kw in content_lower for kw in ["search", "query", "lookup", "find", "look"]):
        tags.append("query")
    # config
    if any(kw in content_lower for kw in ["config", "setting", "param", "change", "modify", "suggest"]):
        tags.append("config")
    # decision
    if any(kw in content_lower for kw in ["decision", "choice", "plan", "solution", "decide"]):
        tags.append("decision")

    if not tags:
        tags.append("routine")

    return tags


def _truncate(text: str, max_chars: int) -> str:
    """截断文本为摘要"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def should_ingest(
    message: str,
    previous_atom: Optional[MemoryAtom],
    threshold: float = 0.3,
) -> bool:
    """
    Surprise-based 分片入库决策（Bug 19 Titans 启发）。

    只存"意外"分片，常规进展不新建分片。

    "意外"的定义：
    - 报错/异常
    - 用户纠正
    - 与已有记忆矛盾
    - 话题突变（embedding 距离 > 阈值，L1 用关键词近似）

    Returns:
        True 如果应该入库
    """
    content_lower = message.lower()

    # 报错 → 意外
    if any(kw in content_lower for kw in ["error", "exception", "报错", "失败", "fail", "bug"]):
        return True

    # 用户纠正 → 意外
    if any(kw in content_lower for kw in ["不对", "错了", "不是", "修正", "更正"]):
        return True

    # 常规进展 → 不意外
    if any(kw in content_lower for kw in ["好的", "收到", "继续", "ok", "已"]):
        return False

    # 默认入库
    return True