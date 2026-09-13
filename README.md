# Vibe Memory

中文检索更新：TF-IDF/BM25 支持中文双字片段，budget 中文候选走隔离的 LIKE 回退，285 项测试通过。中文大语料扫描成本与独立真实会话效果仍待验证。

最新：PPR 与召回路径解释已按租户、Agent 和活跃/暖记忆过滤图边；283 项本地测试通过。完整当前作用域的图规模仍未设硬上限。

2026-09-13 优化：280 项本地测试通过。严格 v3 合成评测中，默认 budget Recall@5 为 0.808；显式二跳为 0.984，默认仍保持一跳。候选扩展已限制每跳边返回量与前沿大小，不等同完整检索耗时硬上限。当前证据与成本边界见 [STATUS.md](STATUS.md)。

> 多关系图智能体记忆系统 — 让 AI Agent 拥有跨会话的长期记忆

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Tests](https://github.com/sv8vkwmfr7-create/vibe-memory/actions/workflows/test.yml/badge.svg)](https://github.com/sv8vkwmfr7-create/vibe-memory/actions)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.3.0-orange.svg)](vibe_memory/__init__.py)

**Vibe Memory** 是一套带关系标签的语义分片图记忆系统。核心创新：**分层建边（同会话规则 + 跨会话 LLM 复核）+ 边标签过滤 + PPR 图检索**，用于减少 RAG 向量检索的虚假召回。当前仓库已有固定数据生成器的本地检索消融和 SDK 规模基线；外部公开基准仍待接入。

当前测试基线、能力边界和待验证事项见 [Project Status](STATUS.md)。

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
- ✅ **本地消融实验噪声比例 0%**：1,000 条合成记忆、100 个查询的 `PPR + 边标签/种子过滤` 组；不等同于公开基准结论

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

### 可复现检索消融（本地）

运行：

```bash
python experiments/retrieval_benchmark.py --json results/retrieval_ablation.json
```

固定数据集包含 1,000 条记忆、20 个主题、100 个查询和 100 条关系边；TF-IDF 文档矩阵只构建一次，延迟从查询编码开始计时。Windows + Python 3.12.14 的一次运行结果：

| 方法 | Precision@5 | Recall@5 | MRR | 噪声率 | p95 延迟 |
|------|-------------:|----------:|----:|--------:|---------:|
| TF-IDF 向量 Top-K | 0.6000 | 0.6000 | 1.0000 | 40.00% | 0.130 ms |
| PPR（全部边标签） | 0.7260 | 0.7260 | 1.0000 | 27.40% | 1.056 ms |
| PPR + 精确边标签 + 种子过滤 | **1.0000** | **1.0000** | **1.0000** | **0%** | 0.901 ms |

这是合成困难负样本上的回归基线，不是 LOCOMO/LongMemEval，也没有证明生产负载下的吞吐或泛化能力。完整记录见 `results/retrieval_ablation.json` 和 `STATUS.md`。

### SDK 规模与写后可见性（本地）

运行：

```bash
python experiments/scale_visibility_benchmark.py --json results/scale_visibility.json
```

该脚本使用内存 SQLite、TF-IDF、关闭自动建边和 Episode 聚合，以隔离 SDK 核心写入与 `recall()` 路径；每次写入计时，并对均匀采样的刚写入 atom 直接调用 `storage.get_atom()`。TF-IDF/BM25 使用稀疏 posting；`budget` 模式通过持久化 SQLite FTS5 按完整词项取至多 `max(100, top_k * 20)` 个候选，并在总预算内用一跳因果邻居替换低优先级文本候选，无 FTS5 时降级为 `LIKE`。20 个确定性查询用于分别测量首次冷查询和后续热查询。Windows + Python 3.12.14 的一次串行运行结果：

| 记忆量 | 写入 ops/s | 写入 p50/p95/p99 (ms) | 写后读取 p50/p95/p99 (ms) | recall p50/p95/p99 (ms) | 可见性 |
|-------:|-----------:|----------------------:|--------------------------:|------------------------:|:-------|
| 1,000 | 10,734.29 | 0.080 / 0.132 / 0.171 | 0.015 / 0.022 / 0.032 | 1.485 / 1.814 / 4.730 | 280/280 (100%) |
| 10,000 | 11,079.93 | 0.080 / 0.134 / 0.195 | 0.014 / 0.027 / 0.031 | 1.541 / 1.897 / 3.877 | 298/298 (100%) |
| 100,000 | 10,025.46 | 0.079 / 0.181 / 0.290 | 0.014 / 0.030 / 0.041 | 1.566 / 2.198 / 9.730 | 299/299 (100%) |

| 记忆量 | cold recall (ms) | warm recall p50/p95/p99 (ms) |
|-------:|-----------------:|-----------------------------:|
| 1,000 | 5.459 | 1.484 / 1.614 / 1.621 |
| 10,000 | 4.371 | 1.538 / 1.724 / 1.758 |
| 100,000 | 11.613 | 1.560 / 1.688 / 1.700 |

这是单进程、内存数据库且关闭建边/聚合的可复现回归基线；“可见性”指提交后直接 `storage.get_atom()` 可读，不等于异步索引完成或新记忆立即出现在 `recall()` 结果中。固定 1k/100 查询消融中，图邻居候选替换与图加权融合把完整 `budget` 管道的 Precision@5/Recall@5 从 0.720/0.648 提升到 0.796/0.796，噪声率从 28.0% 降至 20.4%，p95 从 5.387 ms 变为 5.679 ms。该结果仍是合成数据，不代表公开基准或生产效果。

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
