# Vibe Memory

> 让 AI Agent 在不同会话之间记住事实、决策、修复方案和用户偏好。

## 第一次使用

如果你是第一次接触 Vibe Memory，请从 **[中文零基础指南](docs/GETTING_STARTED.zh-CN.md)** 开始。它包含环境准备、第一次存储与召回、结果验证、MCP 接入、常见问题和下一步选择。

最短体验（无需模型或 API Key）：

```bash
git clone https://github.com/sv8vkwmfr7-create/vibe-memory.git
cd vibe-memory
python -m venv .venv

# Windows PowerShell
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python examples/quickstart.py

# macOS / Linux
.venv/bin/python -m pip install -e .
.venv/bin/python examples/quickstart.py
```

看到 `VibeMemory quickstart succeeded.` 就表示存储、持久化和召回链路已经工作。示例只使用本地 SQLite 与内置 TF-IDF，不联网、不需要大模型。

直接使用 `TfidfProvider` 时，首次 `encode(texts)` 会拟合该批文本；后续编码不自动更新词表，未见词项权重为零。语料变化后应对完整语料调用 `fit()`，并重新编码旧向量；`encode_query()` 从不拟合，未拟合时返回零长度向量。SDK 的 `recall()` 单独管理语料拟合，语料变化后会更新词表，不受直接调用的首批拟合限制。

安装后可进一步验证真实MCP子进程、重启持久化、跨会话召回、scope和清理：

```bash
vibe-doctor --db-path .vibe/memory.db --agent-id my-agent
```

如果MCP配置使用另一个Python解释器，请将同一路径传给 `--python`。全部步骤显示 `[PASS]` 且最后输出 `VibeMemory MCP end-to-end check succeeded.` 才表示端到端验证成功；工具可见或配置文件存在只是中间证据。诊断器会写入带唯一标识的两条测试记忆，并在结束前通过MCP删除。

> [!NOTE]
> 当前推荐从 GitHub 源码安装。`pip install vibe-memory` 是否可从 PyPI 获取取决于发布状态，零基础指南不依赖该前提。

MCP支持显式可选维护：`python -m vibe_memory.mcp_server --db-path /path/to/test.db --vibe-dir /path/to/test-state --wal-maintenance`。此参数明确启用WAL并额外暴露手动工具 `vibe_checkpoint`（可传 `drain_timeout`）；不加参数仍为8个工具、保留原数据库模式，没有定时维护。完整工具操作含短ID解析参与协调，检查点在操作范围外执行。历史30轮两条记忆MCP协议冒烟全部维护及召回成功，不代表大库或真实聊天体验。复跑：`python experiments/mcp_maintenance_smoke.py`，见 [结果](results/mcp_maintenance_smoke.json)。

历史30分钟验证：10万条临时WAL库持续30分钟，8974/8974旧答案命中、174次运行中维护全部截断成功，WAL采样峰值约58MB；SQLite/FTS/CRUD一致性通过。维护最长约501ms、强化仍96.2%调用跳过；默认关闭，不代表真实聊天、硬容量/暂停上限或生产保证。复跑条件与完整结果见 [STATUS.md](STATUS.md) 和 [30分钟JSON](results/disk_soak_sdk_maintenance_30min.json)。

可选WAL维护已接入SDK，默认 `wal_maintenance=None`，不启动后台线程。同一文件库的实例显式共享控制器，应用主动触发：

```python
from vibe_memory import VibeMemory, WALMaintenance

maintenance = WALMaintenance("memory.db")
memory = VibeMemory("my-agent", "memory.db", journal_mode="wal",
                    wal_maintenance=maintenance)
memory.store("Fixed API timeout", session_id="chat-1")
report = maintenance.checkpoint(drain_timeout=1.0)  # 应用自行决定触发时机
```

已有SDK调用会先执行完，新调用在维护期间等待。超时/忙锁会恢复准入，不中断事务或删除日志。`drain_timeout` 只限制等待已有操作结束，不保证总暂停时间。直接使用 `memory.storage`、手动事务或其他组件时须以 `with maintenance.operation():` 覆盖整个操作/事务，同库所有参与者须共享同一控制器；这个维护准入不提供共享连接互斥，多进程和外部未协调连接也不受它控制。状态与限制见 [STATUS.md](STATUS.md)。

同一SDK实例的公共操作（store/recall/history/inject等）由实例级可重入锁串行执行，包括未启用WAL维护时；召回临时设置的`busy_timeout=0`不会被另一个公共调用借用。同线程嵌套调用可重入，异常会释放锁；启用维护时先准入再取实例锁，允许已准入操作完成并退出。锁覆盖完整调用，耗时embedding/LLM回调也会让其他调用排队，不保证等待时间或并行吞吐。不要在回调中等待另一个线程调用同一实例。直接操作storage/cold_start/indexer、跨多个调用的手动事务、修改共享组件或返回对象不受此锁保护，须由应用自行协调；独立实例不共享此互斥锁，也不代表同库多实例/多进程写入无需协调。

上一轮实验检查点对照 `--checkpoint-strategy passive|truncate|coordinated`（默认仍passive）：100k/60秒单次负载中，直接TRUNCATE负载内0/5成功；实验内协同暂停后5/5成功，WAL采样峰值约265→47MB，但暂停约171–323ms、写周期约少2%，强化仍大量跳过。这些是实验控制器的历史指标，不能代替新SDK控制器的测量或证明硬空间上限；完整条件/结果见 [STATUS.md](STATUS.md) 与 [JSON](results/disk_checkpoint_comparison.json)。

强化写放大优化：分片命中强化改为作用域隔离的原子元数据批次，不重写正文/摘要FTS索引，不覆盖并发正文修改或丢失访问增量。专项100轮五分片对照WAL约36.6→0.41MB；不等于整体CRUD负载的WAL峰值已解决。忙锁仍快速跳过，不新增补写队列。

混合负载复跑：`python experiments/disk_soak_benchmark.py --scale 100000 --seconds 300`。仅新建临时WAL库，两个独立SDK读线程与一个CRUD写线程，记录命中、延迟、强化跳过与检查点。`recall()` 返回的 `reinforcement_skipped` 为true表示跳过了部分或全部非关键强化，不表示召回失败，也不保证已成功强化的条目回滚。

SDK 强化忙锁降级已修复：仅命中后的非关键强化临时采用零忙锁等待，遇 BUSY/LOCKED 跳过剩余强化并返回召回；其他数据库错误仍抛出。历史6秒竞争写锁基准约0.6ms返回命中（修复前约5.5秒后报错）。复跑：`python experiments/disk_pressure_benchmark.py`；不是统一延迟SLA或共享SDK线程安全保证。

WAL 恢复验证：`python experiments/wal_recovery_validation.py` 仅创建临时库，检查事务快照、检查点阻塞/释放及测试子进程被杀后的恢复。不是长期负载、断电或磁盘故障验证，详见 [STATUS.md](STATUS.md)。

SQLite 日志模式可显式配置：`VibeMemory(agent_id="my-agent", db_path="memory.db", journal_mode="wal")`。默认 `None` 不改变数据库现有模式；新文件库保持 SQLite 默认行为，已有 WAL 库重开仍保留 WAL。支持小写 `"wal"`、`"delete"`；内存库无法启用 WAL 时明确报错。未修改 synchronous/超时默认值。

WAL 用于本机文件库，不代表单个 SDK 实例可被多线程安全共享。备份应使用 SQLite 备份接口，不能在运行中只复制主数据库而遗漏 WAL；不要手动删除 `-wal` / `-shm` 文件。

高命中率边界：中文候选先相关性、同分再近期排序。历史固定10万条全匹配基准旧答案 10/10 命中，但 warm p95 约324 ms；此前6.4 ms仅适用于选择性查询，不是统一 SLA。

中文规模优化：三字及以上中文查询使用原生 trigram 索引，近期候选补齐使用复合索引；短查询保留 LIKE。历史单次 10万条内存库基准 warm p95 6.4 ms、旧答案 20/20 命中；索引空间和生产边界见 [STATUS.md](STATUS.md)。

中文检索更新：TF-IDF/BM25 支持中文双字片段，budget 中文候选走隔离的 LIKE 回退。中文大语料扫描成本与独立真实会话效果仍待验证。

PPR 与召回路径解释已按租户、Agent 和活跃/暖记忆过滤图边。完整当前作用域的图规模仍未设硬上限。

历史2026-09-13 v3 合成评测中，默认 budget Recall@5 为 0.808；显式二跳为 0.984，默认仍保持一跳。候选扩展已限制每跳边返回量与前沿大小，不等同完整检索耗时硬上限。证据与成本边界见 [STATUS.md](STATUS.md)。

> 多关系图智能体记忆系统 — 让 AI Agent 拥有跨会话的长期记忆

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Tests](https://github.com/sv8vkwmfr7-create/vibe-memory/actions/workflows/test.yml/badge.svg)](https://github.com/sv8vkwmfr7-create/vibe-memory/actions)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.3.0-orange.svg)](vibe_memory/__init__.py)

**Vibe Memory** 是一套带关系标签的分片图记忆系统。它探索**分层建边（同会话规则 + 可选跨会话 LLM 复核）+ 边标签过滤 + PPR 图检索**，用于改善记忆召回。仓库已有合成消融、SDK规模实验及公开数据检索试跑；这些证据不等于最终回答正确性或独立人工评估。

当前测试基线、能力边界和待验证事项见 [Project Status](STATUS.md)。

测试命令、行/分支覆盖率、真实MCP子进程统计和CI报告保存方式见 [测试与覆盖率](docs/TESTING.md)；本地回归通过不等于GitHub多版本CI已通过，也不等于独立记忆质量评估。

---

## 为什么需要 Vibe Memory？

传统 RAG 向量检索的问题：
- 可能返回“看起来相关但实际无关”的结果；噪声比例依语料、模型和检索协议变化，不存在本项目已证明的通用20%基线
- ❌ 不知道分片之间的因果关系（A 导致了 B）
- ❌ 无法区分"同类经验"和"修正推翻"

Vibe Memory 的答案：
- ✅ **边标签过滤**：只沿着有意义的边游走（因果接续/修正推翻/同类经验）
- ✅ **PPR 图检索**：按边权重概率游走，高权重优先，低权重自然抑制
- ✅ **多策略检索**：组合BM25、向量、图与时序策略的结果，并使用RRF融合；不承诺并发执行
- 合成消融用于检查已构造语料上的行为；没有同协议竞品实验，不能证明通用“噪声归零”或优于其他记忆系统

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
│    作用域隔离 + 规则隐私扫描 + 有界降级诊断           │
└─────────────────────────────────────────────────────┘
```

---

## 快速开始

### 安装

```bash
# 从源码安装，不依赖PyPI发布状态
git clone https://github.com/sv8vkwmfr7-create/vibe-memory.git
cd vibe-memory
pip install -e .

# 可选：语义 embedding
pip install -e ".[semantic]"
```

如需离线中文语义向量，可将已下载的 `BAAI/bge-small-zh-v1.5` 指定给 SDK；模型目录属于本地文件，已由 `.gitignore` 排除，不会随提交上传：

```python
from vibe_memory import VibeMemory

mem = VibeMemory(
    agent_id="my-agent",
    db_path="memory.db",
    embedding_backend="st",
    embedding_model="models/bge-small-zh-v1.5",
)
```

`embedding_model` 也可以填写绝对路径。当前默认值和生产 SDK/MCP 行为不变；启用前请用自己的标注集比较召回、精度、内存和启动成本。

### Python SDK

```python
from vibe_memory import VibeMemory

mem = VibeMemory(agent_id="my-agent", db_path="memory.db")
mem.store(
    "Fixed API timeout error, changed from 30s to 60s",
    session_id="chat-1",
    tags=["error", "config"],
    scope={"service": "orders", "environment": "production",
           "operation": "export"},
)
result = mem.recall("API timeout", mode="precision")
for atom in result["atoms"]:
    print(atom.summary)
```

需要显式作用域时可选择稳定提升匹配项；它不删除候选，默认关闭：

```python
result = mem.recall(
    "request hangs",
    mode="precision",
    scope={"service": "orders", "environment": "production"},
)
print(result["scope_boosted"])
```

MCP `vibe_recall` 接受同样的 `scope` 对象。当前只支持精确匹配提升，不支持过滤。

### 可选因果桥保留

默认排序保持不变。排障时可显式开启：

```python
result = mem.recall("API timeout", mode="precision", top_k=5, causal_bridge=True)
```

MCP `vibe_recall` 同样接受 `"causal_bridge": true`。参数必须为布尔值，开启时仅支持 `precision`；`session_start` 和 `inject` 暂不暴露此开关。

它只提升已融合候选中，以有效因果边连接至少两个语义/BM25共同锚点、且包含首位语义锚点的非锚点节点。边强度 `weight * confidence >= 0.05`，遵守 Agent、租户和存活节点范围；不按会话过滤，边方向不用于判断。无合格桥时保持原相似度排序，不能保证主锚点正确或所有原因均被保留。

本地助手调试集10题、真实MCP回放开启后的Recall为1.00，关闭为0.85；不是独立人工/生产质量证明。匿名报告见 `results/causal_bridge_opt_in_mcp.json`。专项测试覆盖默认保持、跨会话原因、标签/弱边、空图、参数校验和同库双租户4客户端并发；不等同于同一SDK实例跨线程安全或大图性能验证。

### 一键配置编程 Agent

```bash
vibe-init              # 自动检测 Claude Code / Codex / Cursor
vibe-init --dry-run    # 预览不改动
```

### 6 种接入方式

| 方式 | 适用 | 命令 |
|------|------|------|
| MCP Server | Claude Code / Codex / Cursor | `vibe-mcp` |
| HTTP API | 任何语言 | 先设置私有 `VIBE_HTTP_TOKEN`，再 `vibe-http --port 8420` |
| Python SDK | 自定义 Agent | `from vibe_memory import VibeMemory` |
| LangChain-style helper | Manual load/save wiring; not BaseMemory or LangGraph state | `from vibe_memory.langchain import VibeMemoryLC` |
| OpenAI Agents functions | Wrap returned functions with `agents.function_tool` | `from vibe_memory.openai_agents import create_vibe_tools` |
| CLI | 脚本/手动 | `vibe-session start/end` |
| MCP诊断 | 安装与跨会话验证 | `vibe-doctor` |

LangChain helper的手动读写方式、OpenAI函数的包装步骤、已验证框架版本及离线冒烟边界见 [适配器与重排契约](docs/ADAPTER_CONTRACTS.md)。不承诺BaseMemory/LangGraph直接替换或尚未实现的cross-encoder/LLM重排类。

接入行为有区别：MCP默认写入关闭自动建边，已有合法边或手工`vibe_link`仍可用于图检索；SDK的规则建边和可选LLM复核须按调用方式启用。安装本库本身不会自动读取所有聊天，也不会自动把检索结果注入任意模型。

HTTP 数据请求须带 `Authorization: Bearer <token>`；默认仅监听本机，禁止跨源访问。会话开始返回完整 `session_id`，后续写入和结束必须显式传入，不再共享隐式会话。详见 [HTTP 安全与接入](docs/HTTP_SECURITY.md)。

默认隐私扫描不是完整防泄漏保证：普通长串/银行卡号需要明确上下文才触发低置信度规则；重叠命中统一替换。扫描路径、误报与漏报边界见 [隐私扫描说明](docs/PRIVACY_SCANNER.md)。

删除与合并通过存储事务维护关系边；这不等于清除所有派生记忆，历史孤儿与Episode/队列引用仍需治理。详见 [记忆与边生命周期](docs/ATOM_EDGE_LIFECYCLE.md)。

### LLM 建边（可选）

```python
from vibe_memory.llm import OpenAIProvider, LLMEdgeClassifier
provider = OpenAIProvider(api_key="sk-xxx", model="gpt-4o-mini")
mem = VibeMemory(agent_id="agent", llm_classifier=LLMEdgeClassifier(provider))
mem.store("API timeout", session_id="s1")
mem.store("Fixed timeout to 60s", session_id="s2")
mem.flush_index()  # 处理候选；输出标签由模型/降级规则决定，不保证因果关系
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
| `store(content, session_id, scope)` | 写入分片；可选显式 `service/environment/operation` 作用域元数据（当前只持久化，不参与排序） |
| `store_batch(messages)` | 批量写入（自动切分+入库+同会话建边） |
| `recall(query, mode, scope)` | 多策略检索；可选显式scope稳定提升匹配项，不过滤候选 |
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

表中的“因果接续”是目标语义；当前同会话规则按时间顺序连边，并以宽泛信号词判断标签，不能保证 `A→B` 已经过真实因果方向验证。实验性定向重排也只验证给定边方向，不应将其结果解读为真实因果推理能力。术语边界见 [领域词汇](CONTEXT.md)，方向对照见 [审计记录](docs/CAUSAL_DIRECTION_AUDIT.md)。

### 多策略检索

```
查询 → 按启用策略执行
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

### 历史观察与证据等级

[Phase 0手工记录](experiment.md)是设计期观察，不是独立评测。没有完整提交的样本、运行协议、模型版本与原始输出支撑场景星级或LLM分类百分比，因此不再把它们列为产品成绩，也不据此推导模型大小要求。模型选择需在目标任务及成本约束下验证；本地模型能加载不等于记忆分类质量已验证。

### 合成检索消融存档（retrieval-ablation-v3）

运行：

```bash
python experiments/retrieval_benchmark.py --json /path/to/new-report.json
```

存档JSON包含1,000条记忆、20个主题、100个查询和100条关系边，top_k=5；生成的查询、相关标签及边不是独立评审。表格逐项来自[结果文件](results/retrieval_ablation.json)，不是本轮重测：

| 方法 | Precision@5 | Recall@5 | MRR | 噪声率 | p95 延迟 |
|------|-------------:|----------:|----:|--------:|---------:|
| TF-IDF 向量 Top-K | 0.6000 | 0.6000 | 1.0000 | 40.00% | 0.160 ms |
| PPR（全部边标签） | 0.7800 | 0.7800 | 1.0000 | 22.00% | 1.080 ms |
| PPR + 精确边标签 + 种子过滤 | 1.0000 | 1.0000 | 1.0000 | 0.00% | 0.990 ms |
| 完整budget管道 | 0.8080 | 0.8080 | 1.0000 | 19.20% | 4.872 ms |

artifact最后提交为`6a8ad0606dbb5d6d850ffa8c1776c1e86b070430`，文件SHA256为`c1da44768623ab055f8768af0b0f7124c64631a0888a761e5821ade4db38d65f`。这是结果文件的版本绑定，不是已记录的运行源码提交；JSON未保存运行commit，不能保证用现有代码重跑数值相同。噪声率0.22按百分比为22%，不是0.22%。完整协议/后续试跑见[STATUS](STATUS.md)，不得外推为竞品优势、回答正确率、生产吞吐或延迟SLA。

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

## 与其他系统比较的边界

尚无锁版本、同模型、同语料与同预算的端到端竞品对照，不作胜负排名或以合成结果证明通用优势。资料层级与核对日期见[官方资料摘录](docs/MAINSTREAM_MEMORY_COMPARISON_SOURCES.md)；旧Hindsight对比的失效结论及后续协议见[对比边界](HINDSIGHT_COMPARISON.md)。

本项目定位是本地SQLite、带关系标签、可组合检索策略的记忆库。基础路径可不调用云模型，但有Python依赖及本地资源/用户接入成本；可选语义模型、分类或反思另计，不是零成本保证。

---

## 依赖

- **Python 3.10+**
- **numpy** — TF-IDF 向量化 + BM25
- **tomli**（仅 Python 3.10）— 初始化时校验 TOML；Python 3.11+ 使用标准库
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
