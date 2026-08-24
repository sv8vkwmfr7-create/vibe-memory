# Vibe Memory

> 多关系图智能体记忆系统 — 让 AI Agent 拥有跨会话的长期记忆

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-181%20passed-brightgreen.svg)](tests/)
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
│ 3. 检索（PPR Graph Walk）                           │
│    Personalized PageRank 替代 BFS                    │
│    三档操作点：precision / recall / budget           │
│    降级：PPR 超时 → 向量 Top-K                       │
├─────────────────────────────────────────────────────┤
│ 4. Prompt 注入（双模式）                             │
│    MAC：全文注入（排错/编码）                         │
│    MAG：门控信号（策略/创意）                         │
├─────────────────────────────────────────────────────┤
│ 5. 存储层（SQLite + 未来 pgvector）                  │
│    MemoryAtom + Edge + Episode 完整 CRUD             │
│    pending_review 异步队列 + 降级全覆盖               │
└─────────────────────────────────────────────────────┘
```

---

## 快速开始

### 安装

```bash
pip install vibe-memory

# 或开发模式
git clone https://github.com/YOUR_USERNAME/vibe-memory.git
cd vibe-memory
pip install -e .

# 可选：语义 embedding
pip install vibe-memory[semantic]
```

### Python SDK

```python
from vibe_memory import VibeMemory

# 初始化
mem = VibeMemory(agent_id="my-agent", db_path="memory.db")

# 写入记忆
mem.store("Fixed API timeout error, changed from 30s to 60s",
          session_id="chat-1", tags=["error", "config"])

# 检索记忆（精确模式）
result = mem.recall("API timeout", mode="precision")
for atom in result["atoms"]:
    print(f"[{atom.summary}]")

# 查看统计
stats = mem.stats()
print(f"Atoms: {stats['total_atoms']}, Edges: {stats['total_edges']}")
```

### CLI 工具（Claude Code 集成）

```bash
# 开始会话（自动召回历史记忆）
vibe-session start --context "排查 API timeout"

# 会话中工作...

# 结束会话（自动存储摘要和亮点）
vibe-session end --summary "修好了 timeout，改成 60s" \
    --highlight "根因是数据库连接池耗尽"

# 查看统计
vibe-session stats
```

环境变量：`VIBE_DIR`、`VIBE_AGENT_ID`。

### LLM 建边（可选）

```python
from vibe_memory.llm import OpenAIProvider, LLMEdgeClassifier

provider = OpenAIProvider(api_key="sk-xxx", model="gpt-4o-mini")
classifier = LLMEdgeClassifier(provider)

mem = VibeMemory(agent_id="agent", llm_classifier=classifier)
mem.store("API timeout", session_id="s1")
mem.store("Fixed timeout to 60s", session_id="s2")
mem.flush_index()  # LLM 自动分类为"因果接续"
```

---

## API 端点

| 方法 | 说明 |
|------|------|
| `store(content, session_id)` | 写入分片（自动建边 + embedding 缓存 + Episode 聚合） |
| `store_batch(messages)` | 批量写入（自动切分+入库+同会话建边） |
| `recall(query, mode)` | 检索记忆（4 阶段管道：embedding→filter→PPR→rank） |
| `link(from_id, to_id, label)` | 手动建边 |
| `migrate(atom_id, to_partition)` | 分区迁移 |
| `forget(atom_id)` | 删除记忆 |
| `update(atom_id, **fields)` | 更新元数据 |
| `history(session_id, limit)` | 会话历史 |
| `stats()` | 统计信息（含 可观测性 + GC + 冷启动 + 索引 + LLM 指标） |
| `collect_garbage()` | GC 压缩（四级管线：稀疏化→固定池→冷存储→淘汰） |
| `flush_index()` | 批量处理增量索引（实时规则边 + 批处理 LLM 边） |

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
    decay_rate: float,    # 衰减速率（Vibe Learner 动态调整）
    # ... 更多字段
)
```

### Edge（关系边）— 8 种标签

| 标签 | 方向 | 含义 | 注入优先级 |
|------|------|------|-----------|
| 因果接续 | A→B | A 导致了 B | 高 |
| 同类经验 | A↔B | 同一类问题/经验 | 中 |
| 修正推翻 | A→B | B 修正/推翻了 A | 高 |
| 时序相邻 | A→B | 同会话相邻但无强因果 | 低 |
| 引用 | A→B | 跨分区引用 | 低 |
| 查阅 | S→D | Agent 检索了文档 | 低 |
| 影响 | D→S | 文档影响了会话 | 中 |
| 版本 | A→B | B 是 A 的新版本 | 高 |

### PPR 图检索（替代 BFS）

```
向量预筛 → 种子后过滤 → PPR 图游走 → 排序注入
```

三档可配置操作点：
- **precision**：高重启 (α=0.3)，只走因果+修正，top-5
- **recall**：低重启 (α=0.1)，走所有边，top-15
- **budget**：极高重启 (α=0.5)，只走因果，top-3

---

## 实验验证

### Phase 0：核心假设

| 场景 | 结果 | 评分 |
|------|------|------|
| Bug 修复延续 | 用户 0 次重复背景，21 项修复一次完成 | ⭐⭐⭐⭐⭐ |
| 项目开发持续 | Day 1 设计 + Day 2 代码，一次会话完成 | ⭐⭐⭐⭐⭐ |
| 用户偏好记忆 | 4 条偏好 3 次会话全部命中，0 次违背 | ⭐⭐⭐⭐⭐ |
| 配置变更追踪 | 3 条约定 4 次查询全部命中，噪声 0% | ⭐⭐⭐⭐⭐ |
| 多任务切换 | 2 个独立任务交替，完美隔离，噪声 0% | ⭐⭐⭐⭐⭐ |

### RAG vs VibeMemory 召回对比

| 指标 | RAG (Top-K) | Vibe (precision) |
|------|-------------|-----------------|
| 相关分片 | 3 | 3 |
| 噪声分片 | 1 | **0** |
| 噪声比例 | 20% | **0%** |

### 真实使用验证

SessionManager 在知识库 vault 实测：2 次会话，跨会话召回 5/5 (100%)，注入 747 字符。

---

## 模块索引

```
VibeMemory/
├── vibe_memory/
│   ├── sdk.py                    ← 统一入口（11 个端点）
│   ├── coldstart.py              ← 冷启动三阶段 + 种子记忆
│   ├── metrics.py                ← 可观测性（延迟/吞吐/命中率/降级）
│   ├── gc.py                     ← GC 压缩（四级管线）
│   ├── indexer.py                ← 增量索引（双速 + 回压）
│   ├── models/
│   │   └── memory_atom.py        ← 核心数据结构
│   ├── chunking/
│   │   ├── chunker.py            ← 语义分片
│   │   └── episode.py            ← Episode 聚合
│   ├── edges/
│   │   └── edge_builder.py       ← 分层建边
│   ├── retrieval/
│   │   ├── ppr.py                ← PPR 检索 + 4 阶段管道
│   │   └── seed_filter.py        ← 种子后过滤
│   ├── learner/
│   │   └── learner.py            ← Vibe Learner 在线学习
│   ├── embedding/
│   │   ├── tfidf.py              ← TF-IDF 向量化
│   │   └── provider.py           ← 统一接口（auto/TF-IDF/semantic）
│   ├── llm/
│   │   ├── provider.py           ← LLM Provider 抽象（零依赖）
│   │   └── edge_classifier.py    ← LLM 边分类器（prompt+解析+降级）
│   ├── cli/
│   │   ├── session_manager.py    ← SessionManager（会话生命周期）
│   │   └── main.py               ← CLI 工具（vibe-session 6 命令）
│   ├── graph/
│   │   ├── partition.py          ← 图分区管理
│   │   └── community.py          ← Louvain 社区检测
│   └── storage/
│       └── sqlite_store.py       ← SQLite 存储层（多租户）
├── tests/
│   ├── test_m1.py                ← 14 核心功能测试
│   ├── test_m2.py                ← 14 图分区 + 社区检测测试
│   ├── test_m3_tenant.py         ← 9 多租户测试
│   ├── test_m3_sdk.py            ← 11 SDK API 测试
│   ├── test_m3_coldstart.py      ← 16 冷启动测试
│   ├── test_m3_metrics.py        ← 17 可观测性测试
│   ├── test_m3_gc.py             ← 19 GC 压缩测试
│   ├── test_m3_indexer.py        ← 19 增量索引测试
│   ├── test_llm.py               ← 38 LLM 建边测试
│   ├── test_session_manager.py   ← 24 Session 管理测试
│   ├── test_simulation.py        ← 3 会话跨会话模拟
│   └── test_comparison.py        ← RAG vs Vibe 对比
├── experiments/
│   ├── embedding_validation.py   ← 6 组 embedding 对比实验
│   ├── phase0_scenario3.py       ← 配置变更追踪验证
│   ├── phase0_scenario5.py       ← 多任务切换验证
│   └── benchmark.py              ← 全链路性能基准（6 维度）
├── DEV_shturl.md                  ← 开发日志（6 问题 + 8 决策）
├── experiment.md                  ← 实验记录（13 实验）
├── README.md
├── pyproject.toml
└── LICENSE
```

**181 测试通过，25 次 commit。**

---

## 竞品定位

| 方案 | 记忆机制 | Vibe 差异 |
|------|---------|----------|
| MemGPT | OS 式分页，LLM 自主管理 | 无显式图结构；Vibe 确定性检索 |
| Mem0 | 向量 + 图增强，10 行集成 | 偏用户画像；Vibe 侧重任务上下文 |
| Zep | 时序知识图谱，时间衰减 | 偏事件链；Vibe 侧重因果 + 边标签过滤 |
| HippoRAG | 海马体索引，PPR 检索 | 文档级问答；Vibe 会话级记忆 |
| MemOS | 类 OS 架构，MemCube 抽象 | 调度层；Vibe 存储和检索层——互补 |

**差异化定位：Vibe Memory = 会话级 + 图结构 + 边标签过滤，竞品均未覆盖此组合。**

---

## 依赖

- **Python 3.10+**
- **numpy** — TF-IDF 向量化
- **sentence-transformers**（可选）— 语义 embedding（all-MiniLM-L6-v2）
- **SQLite** — 内置，无需额外安装

---

## 理论基础

Vibe Memory 的设计受以下论文启发：

- **HippoRAG** (2024) — 海马体索引 + PPR 检索
- **Titans** (2024) — 学习型遗忘门控 + Surprise-based 记忆
- **MemGPT** (2023) — OS 式分页记忆管理
- **Mem0** (2024) — 向量 + 图增强记忆
- **Zep** (2024) — 时序知识图谱 + 连续时间衰减
- **MemOS** (2025) — 类 OS 架构 + MemCube 抽象
- **WISE** (2024) — 图分区（Session/Document/Parametric）

---

## License

MIT © 2026