# Vibe Memory

> 多关系图智能体记忆系统 — 让 AI Agent 拥有跨会话的长期记忆

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-265%20passed-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.3.0-orange.svg)](vibe_memory/__init__.py)

**Vibe Memory** 是一套带关系标签的语义分片图记忆系统。核心创新：**分层建边（同会话规则 + 跨会话 LLM 复核）+ 边标签过滤 + PPR 图检索**，解决 RAG 向量检索的虚假召回问题。**实验验证：噪声比例从 20% → 0%。**

---

## 为什么需要 Vibe Memory？

传统 RAG 向量检索的问题：
- ❌ 返回"看起来相关但实际无关"的噪声结果（20% 噪声比例）
- ❌ 不知道分片之间的因果关系（A 导致了 B）
- ❌ 无法区分"同类经验"和"修正推翻"

Vibe Memory 的答案：
- ✅ **边标签过滤**：只沿着有意义的边游走（因果接续/修正推翻/同类经验）
- ✅ **PPR 图检索**：按边权重概率游走，高权重优先，低权重自然抑制
- ✅ **多策略检索**：BM25 + 语义 + 图 + 时序，4 路并行 + RRF 融合
- ✅ **噪声比例 0%**：不是靠 prompt engineering，而是架构层面的图结构

---

## 5 层架构

```
┌─────────────────────────────────────────────────────┐
│                  Vibe Memory 5 层架构                 │
├─────────────────────────────────────────────────────┤
│ 1. 语义分片（Chunking）                              │
│    会话 → 拆解为语义独立分片 → 打标签 → 入库          │
│    + Surprise-based 选择性入库（Titans 启发）         │
├─────────────────────────────────────────────────────┤
│ 2. 分层建边（Edge Building）                         │
│    同会话：四分类规则（因果/同类/时序相邻/不建边）     │
│    跨会话：KNN 预筛 → LLM 四分类 + 合并检查           │
│    8 种边标签 + 连续衰减 + 时间戳                    │
├─────────────────────────────────────────────────────┤
│ 3. 多策略检索（Multi-Strategy Retrieval）            │
│    BM25 关键词 + 语义向量 + PPR 图游走 + 时序过滤     │
│    RRF 融合 + 相似度重排，三档操作点                  │
│    降级：PPR 超时 → 向量 Top-K                       │
├─────────────────────────────────────────────────────┤
│ 4. Prompt 注入（双模式）                             │
│    MAC：全文注入（排错/编码）                         │
│    MAG：门控信号（策略/创意）                         │
├─────────────────────────────────────────────────────┤
│ 5. 存储层（SQLite）                                  │
│    MemoryAtom + Edge + Episode 完整 CRUD             │
│    多租户隔离 + 隐私扫描 + 降级全覆盖                 │
└─────────────────────────────────────────────────────┘
```

---

## 快速开始

### 安装

```bash
pip install vibe-memory

# 开发模式
git clone https://github.com/sv8vkwmfr7-create/vibe-memory.git
cd vibe-memory
pip install -e .

# 可选：语义 embedding
pip install vibe-memory[semantic]
```

### Python SDK

```python
from vibe_memory import VibeMemory

mem = VibeMemory(agent_id="my-agent", db_path="memory.db")
mem.store("Fixed API timeout error, changed from 30s to 60s", session_id="chat-1", tags=["error", "config"])
result = mem.recall("API timeout", mode="precision")
for atom in result["atoms"]:
    print(atom.summary)
```

### 一键配置编程 Agent

```bash
vibe-init              # 自动检测 Claude Code / Codex / Cursor
vibe-init --dry-run    # 预览不改动
```

### 6 种接入方式

| 方式 | 适用 | 命令 |
|------|------|------|
| MCP Server | Claude Code / Codex / Cursor | `vibe-mcp` |
| HTTP API | 任何语言 | `vibe-http --port 8420` |
| Python SDK | 自定义 Agent | `from vibe_memory import VibeMemory` |
| LangChain | LangChain/LangGraph | `from vibe_memory.langchain import VibeMemoryLC` |
| OpenAI SDK | OpenAI Agents | `from vibe_memory.openai_agents import create_vibe_tools` |
| CLI | 脚本/手动 | `vibe-session start/end` |

### LLM 建边（可选）

```python
from vibe_memory.llm import OpenAIProvider, LLMEdgeClassifier
provider = OpenAIProvider(api_key="sk-xxx", model="gpt-4o-mini")
mem = VibeMemory(agent_id="agent", llm_classifier=LLMEdgeClassifier(provider))
mem.store("API timeout", session_id="s1")
mem.store("Fixed timeout to 60s", session_id="s2")
mem.flush_index()  # LLM 自动分类为"因果接续"
```

### 反思推理（可选，用户自备 API Key）

```python
from vibe_memory.reflect import Reflector
from vibe_memory.llm import OpenAIProvider

reflector = Reflector(mem, OpenAIProvider(api_key="sk-xxx"))
mem = VibeMemory(agent_id="agent", reflector=reflector)
mem.reflect("What patterns in recent bugs?")  # → 生成跨记忆洞察
```

---

## API 端点

| 方法 | 说明 |
|------|------|
| `store(content, session_id)` | 写入分片（自动建边 + embedding 缓存 + 隐私扫描） |
| `store_batch(messages)` | 批量写入（自动切分+入库+同会话建边） |
| `recall(query, mode)` | 多策略检索（BM25+语义+图+时序，RRF 融合） |
| `inject(query, mode)` | 检索 + 注入一步完成 |
| `reflect(prompt)` | 跨记忆推理（需 reflector） |
| `link(from_id, to_id, label)` | 手动建边 |
| `migrate(atom_id, to_partition)` | 分区迁移 |
| `forget(atom_id)` | 删除记忆 |
| `update(atom_id, **fields)` | 更新元数据 |
| `history(session_id, limit)` | 会话历史 |
| `stats()` | 统计信息（含可观测性+GC+冷启动+索引+LLM） |
| `collect_garbage()` | GC 压缩（四级管线） |
| `flush_index()` | 批量处理增量索引 |

---

## 核心概念

### MemoryAtom（记忆单元）

```python
MemoryAtom(
    id: str,              # UUID
    agent_id: str,        # 所属 Agent
    session_id: str,      # 创建会话
    content: str,         # 分片文本
    type: GraphPartition, # session / document / parametric
    tags: list[str],      # 内容标签
    weight: float,        # 连续衰减 [0, 1]
    decay_rate: float,    # Vibe Learner 动态调整
)
```

### Edge（关系边）— 8 种标签

| 标签 | 方向 | 含义 | 优先级 |
|------|------|------|--------|
| 因果接续 | A→B | A 导致了 B | 高 |
| 修正推翻 | A→B | B 修正/推翻了 A | 高 |
| 版本 | A→B | B 是 A 的新版本 | 高 |
| 同类经验 | A↔B | 同一类问题/经验 | 中 |
| 影响 | D→S | 文档影响了会话 | 中 |
| 时序相邻 | A→B | 同会话相邻但无强因果 | 低 |
| 引用 | A→B | 跨分区引用 | 低 |
| 查阅 | S→D | Agent 检索了文档 | 低 |

### 多策略检索

```
查询 → 并行分发
  ├─ BM25 关键词检索
  ├─ 语义向量检索
  ├─ PPR 图游走检索
  └─ 时序过滤
     ↓
  RRF 融合排序
     ↓
  相似度重排
```

---

## 实验验证

### RAG vs VibeMemory 召回对比

| 指标 | RAG (Top-K) | Vibe (precision) |
|------|-------------|-----------------|
| 相关分片 | 3 | 3 |
| 噪声分片 | 1 | **0** |
| 噪声比例 | 20% | **0%** |

### Phase 0：5/5 场景满分

| 场景 | 评分 |
|------|------|
| Bug 修复延续 | ⭐⭐⭐⭐⭐ |
| 项目开发持续 | ⭐⭐⭐⭐⭐ |
| 用户偏好记忆 | ⭐⭐⭐⭐⭐ |
| 配置变更追踪 | ⭐⭐⭐⭐⭐ |
| 多任务切换 | ⭐⭐⭐⭐⭐ |

### LLM 边分类验证

| 模型 | 分类准确率 | 合并准确率 | 延迟 |
|------|----------|----------|------|
| DeepSeek-v4-flash | 80% | 100% | 2.3s |
| Qwen2.5-0.5B (本地) | 33% | 33% | 53s |
| 结论 | <2B 不可用 | 需 7B+ 或 API | — |

---

## 竞品定位

| 方案 | 记忆机制 | Vibe 差异 |
|------|---------|----------|
| MemGPT | OS 式分页 | 无显式图结构；Vibe 确定性检索 |
| Mem0 | 向量 + 图增强 | 偏用户画像；Vibe 侧重任务上下文 |
| Zep | 时序知识图谱 | 偏事件链；Vibe 侧重因果 + 边标签过滤 |
| HippoRAG | 海马体索引 | 文档级；Vibe 会话级 + 多策略 |
| Hindsight | 生物模拟 + 反思 | 企业级；Vibe 轻量零依赖 + 可解释 |

**差异化定位：Vibe Memory = 轻量 + 图结构 + 边标签过滤 + 多策略检索，零依赖离线可用。**

---

## 依赖

- **Python 3.10+**
- **numpy** — TF-IDF 向量化 + BM25
- **sentence-transformers**（可选）— 语义 embedding
- **SQLite** — 内置，无需额外安装

---

## 理论基础

- **HippoRAG** (2024) — 海马体索引 + PPR 检索
- **Titans** (2024) — 学习型遗忘门控 + Surprise-based 记忆
- **MemGPT** (2023) — OS 式分页记忆管理
- **Zep** (2024) — 时序知识图谱 + 连续时间衰减
- **Hindsight** (2025) — 反思推理 + 心智模型

---

## License

MIT © 2026