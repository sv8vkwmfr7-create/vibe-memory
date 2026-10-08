# Vibe Memory 中文零基础指南

这份指南面向第一次接触 Vibe Memory 的用户。完成后，你会拥有一个本地记忆库，并能完成“写入一条记忆 → 关闭程序 → 重新打开 → 找回记忆”的完整闭环。

## 1. 先理解它是什么

Vibe Memory 是 AI Agent 的长期记忆层。它不是聊天模型，也不会替你生成答案；它负责把值得长期保留的信息存入 SQLite，并在后续会话中找回相关内容，交给 Agent 继续使用。

适合保存：

- 已确认的技术决策，例如“订单服务超时从 30 秒改为 60 秒”；
- 故障原因和修复办法；
- 用户长期偏好；
- 跨会话仍有价值的项目约束和经验。

不应保存：密码、API Key、访问令牌、身份证号等敏感信息，也不要把所有聊天原文无差别写入。

最小工作流是：

```text
重要信息 → store 写入 → SQLite 持久化 → recall 检索 → Agent 使用结果
```

## 2. 准备环境

你需要：

- Python 3.10 或更高版本；
- Git；
- Windows PowerShell、macOS Terminal 或 Linux Shell。

检查版本：

```bash
python --version
git --version
```

Windows 如果没有 `python` 命令，可尝试 `py -3 --version`，并把后续命令中的 `python` 替换为 `py -3`。

## 3. 安装项目

```bash
git clone https://github.com/sv8vkwmfr7-create/vibe-memory.git
cd vibe-memory
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\python -m pip install -e .
```

macOS / Linux：

```bash
.venv/bin/python -m pip install -e .
```

基础安装只依赖 NumPy 和 Python 自带的 SQLite，不需要 API Key，也不需要下载本地大模型。

## 4. 跑通第一个闭环

Windows PowerShell：

```powershell
.venv\Scripts\python examples/quickstart.py
```

macOS / Linux：

```bash
.venv/bin/python examples/quickstart.py
```

脚本会在临时目录中创建数据库，写入两条记忆，关闭后重新打开数据库，再召回订单服务的修复记录。成功时最后一行是：

```text
VibeMemory quickstart succeeded.
```

这同时验证了：

1. Python 包能够导入；
2. 记忆能够写入 SQLite；
3. 程序重启后数据仍存在；
4. 查询能够召回相关记忆；
5. 显式 `scope` 默认只提升匹配作用域的候选；可选 `strict_scope=True` 才严格过滤。

### 可选：严格作用域

Python SDK 的 `recall` 与 MCP 的 `vibe_recall` 都支持 `strict_scope`，默认 `false`。

```python
result = mem.recall(
    "支付服务生产环境重试次数是多少？",
    scope={"service": "payment", "environment": "production"},
    strict_scope=True,
)
```

开启后，指定的每个 scope 键都必须存在且匹配（值忽略首尾空白和大小写）；冲突或缺失元数据的记录不进入候选、图扩展或冷启动补充。过滤先于排序与 top_k 截断，不通过其他环境的图节点桥接。没有提供 scope 或提供空对象时不做过滤；不会自动从问句推断环境。

这只限制记录元数据，不验证正文中的声明是否真实、已生效或与元数据一致，也不代替租户权限隔离。初版严格模式读取当前用户的完整记忆池，再筛选 active/warm，包含 budget 模式；大库成本可能高于原有有界 budget 路径。开关关闭时保持原行为。MCP 调用请将 `strict_scope: true` 和 `scope` 一起放入 `vibe_recall` 参数；现有配置无需修改。此参数按次调用生效，不是全局面板开关；`inject` 与 `vibe_session_start` 未新增该参数，不能视为已获得同样的严格过滤保证。

## 5. 在自己的代码中使用

创建 `my_memory.py`：

```python
from vibe_memory import VibeMemory

memory = VibeMemory(
    agent_id="my-assistant",
    db_path="memory.db",
    embedding_backend="tfidf",
)

saved = memory.store(
    "订单服务导出超时已从 30 秒调整为 60 秒",
    session_id="issue-2026-001",
    tags=["订单", "超时", "修复"],
    scope={"service": "orders", "environment": "production"},
)
print("已保存：", saved.id)

result = memory.recall(
    "订单导出超时怎么解决？",
    mode="precision",
    top_k=5,
    scope={"service": "orders", "environment": "production"},
)

for atom in result["atoms"]:
    print("召回：", atom.content)

print("scope 是否改变排序：", result["scope_boosted"])
```

运行：

```bash
python my_memory.py
```

`agent_id` 用于隔离不同 Agent 的记忆；同一个 Agent 后续应继续使用同一个值。`db_path` 是本地 SQLite 文件路径，应放在可持久保存且会备份的位置。入门阶段显式使用 `embedding_backend="tfidf"`，避免环境中已有语义模型依赖时意外联网下载模型。

## 6. 如何判断真的成功

不要只看“程序没有报错”。至少检查：

- `store()` 返回了非空 ID；
- 磁盘上生成了数据库文件；
- 用同一 `agent_id` 和 `db_path` 新建实例后仍能召回；
- `result["atoms"]` 中确实包含目标内容；
- 使用scope时，`scope_boosted`只代表排序是否变化，不代表质量一定提升。

如果召回为空，先确认写入与查询使用了相同的 `agent_id`、数据库路径和租户；再尝试用记忆中实际出现的关键词查询。

## 7. 接入 Claude Code、Codex 或 Cursor

先进入你希望启用记忆的项目目录，然后预览配置：

```bash
vibe-init --dry-run
```

确认检测结果正确后再执行：

```bash
vibe-init
```

它会为检测到的编程 Agent 写入 MCP 配置和使用说明。重新启动对应客户端后，应能看到这些工具：

- `vibe_store`：保存重要事实、决策或修复记录；
- `vibe_recall`：按问题找回记忆；
- `vibe_session_start`：会话开始时召回上下文；
- `vibe_session_end`：会话结束时保存总结；
- `vibe_stats`：查看记忆库状态；
- `vibe_settings`：查看或切换 MCP 增强模式；
- `vibe_link`、`vibe_forget`、`vibe_flush`：进阶管理工具。

### 首次使用：增强模式与终端面板

MCP 增强模式默认开启。它不是另一个聊天模型：VibeMemory 先检索记忆，再返回候选原文和选择说明，由宿主当前对话模型判断哪些证据适用并回答。换对话模型后仍由当前模型处理，不需要在 VibeMemory 中重复选择模型或填写单独的模型 API Key。宿主仍须实际调用记忆工具；默认开启增强不等于客户端会自动调用 MCP，也不保证模型遵守所有选择说明。

第一次使用，建议主动打开终端设置面板；目前不会保证每个客户端都自动弹出首次设置。先找到 MCP 启动参数中的 `--vibe-dir`，面板必须使用同一个目录，不能只凭数据库路径判断配置位置。以下假设 MCP 的目录是当前项目下的 `.vibe`：

Windows PowerShell：

```powershell
.venv\Scripts\python -m vibe_memory.settings --vibe-dir .vibe
```

macOS / Linux：

```bash
.venv/bin/python -m vibe_memory.settings --vibe-dir .vibe
```

安装后的等价入口是 `vibe-settings --vibe-dir .vibe`。面板显示实际配置路径和隐私说明后：

- 按回车：确认说明，保留当前开关；首次未配置时即保持开启。
- 输入 `off`：确认说明并关闭增强；输入 `on`：确认说明并开启。
- 输入 `cancel` 或取消输入：不保存、不确认说明。

注意：`cancel` 不等于 `off`。首次取消仍保留默认开启；若要关闭增强，请明确输入 `off`。隐私说明确认目前只是记录已读状态，不会阻止未确认时交付记忆，也不保证客户端自动弹出面板。关闭增强仍可能把两条原文交给宿主，并非禁止外发；有数据外发顾虑时，先确认宿主的数据处理方式，再决定是否调用召回。

设置保存到该目录的 `settings.json`，重启后保留。共享同一 `vibe_dir` 的所有 Agent 共用这个偏好；需要独立偏好时使用不同目录。MCP 每次调用会读取设置，切换后下次召回即可生效。面板目前只提供增强开关及首次隐私说明确认，尚无自动建边、摘要或所有功能的统一开关；安全保护不能关闭。

也可让 Agent 调用 `vibe_settings`：参数 `{}` 查看状态，`{"enhanced": false}` 关闭，`{"enhanced": true}` 开启。这只改变增强偏好，不能代替用户在终端面板确认隐私说明。这里的开关作用于 MCP 候选交付，不会改变直接调用 Python SDK `recall()` 的默认行为。

### 增强模式、向量模型与费用的区别

- **记忆检索**：当前 MCP 服务使用本地 TF-IDF，不需要下载模型或调用付费 API。Python SDK 可另行配置可选语义向量模型；这和增强开关是不同的设置。
- **证据选择和回答**：增强开启时交给当前对话模型，不在 VibeMemory 内新增独立模型请求。但宿主可能进行多次模型请求，仍会消耗对话额度或产生供应商费用。
- **关闭增强**：MCP 每次最多交付两条记忆，不再附加增强选择说明；开启时 precision／recall／budget 模式的交付上限分别为 5／15／3 条。实际还受检索命中、`top_k` 和原文预算限制。关闭不是“离线模式”，返回原文仍可能发送给宿主的模型服务商。

记忆保存在本地不等于原文不会离开电脑。若不允许云端处理，应同时核对宿主模型与网络策略，不要仅关闭增强。普通聊天模型也不应直接当作向量模型替换：向量检索需要稳定的 embedding 输出及兼容索引。

增强响应中的 `selection_status=pending_host_selection` 表示候选已交付、等待宿主选择；`selection_verified=false` 不代表已经验证选择正确。关闭时状态为 `disabled`。遇到歧义应澄清，证据不足应说明当前证据无法确认；空结果不等于整个库没有相关记录。

首次验证建议让 Agent 执行：

```text
请用 vibe_store 记住：本项目正式环境订单服务超时为 60 秒。
```

新开一个会话后再问：

```text
请用 vibe_recall 查找订单服务的超时配置。
```

只有跨会话召回到了刚才的信息，才算 MCP 端到端接入成功。配置文件写入成功或工具列表可见，都只是中间证据。

### 自动执行MCP端到端检查

完成安装后运行：

```bash
vibe-doctor --db-path .vibe/memory.db --agent-id my-agent
```

如果客户端配置中写的是特定Python路径，应使用同一个解释器：

```bash
vibe-doctor --python /path/to/python --db-path .vibe/memory.db --agent-id my-agent
```

Windows示例：

```powershell
vibe-doctor --python .venv\Scripts\python.exe --db-path .vibe\memory.db --agent-id my-agent
```

检查器通过真实MCP stdio协议完成初始化、工具发现、写入、关闭进程、重新启动、召回、scope改序和清理。成功输出：

```text
[PASS] Environment
[PASS] MCP startup
[PASS] Tool discovery
[PASS] Store
[PASS] Process restart
[PASS] Cross-session recall
[PASS] Scope
[PASS] Cleanup

VibeMemory MCP end-to-end check succeeded.
```

任何 `[FAIL]` 都表示端到端链路尚未完成，应先按错误信息检查Python解释器、数据库目录、MCP启动或召回配置。

## 8. scope 怎么用

`scope` 是调用方明确提供的上下文，目前支持三个字符串字段：

| 字段 | 示例 | 含义 |
|------|------|------|
| `service` | `orders` | 服务或模块 |
| `environment` | `production` | 环境 |
| `operation` | `export` | 操作或场景 |

默认 `strict_scope=False` 时，scope只对已经召回的候选做稳定提升，不会删除不匹配项，也不会自动从自然语言推断。未传scope时保持原排序。需要按元数据严格过滤时，使用第 4 节介绍的 `strict_scope=True`，并明确提供非空 scope。

## 9. 常见问题

### 必须下载模型吗？

不必须。默认 TF-IDF 路径可离线运行。只有明确需要语义向量检索时，才安装 `.[semantic]` 并配置模型；应先用自己的标注集评估质量、内存和启动成本。

### 数据存在哪里？

存放在你传入的 `db_path` 对应 SQLite 文件中。删除数据库文件会丢失记忆。运行中不要手工删除 SQLite 的 `-wal` 或 `-shm` 文件。

### 为什么刚写入却搜不到？

先用原文关键词查询，并检查 `agent_id`、`db_path` 和租户是否一致。语义相近但没有共同词面的查询，默认 TF-IDF 不一定命中；这时才考虑语义 embedding。

### 可以存密钥吗？

不可以。Vibe Memory 有基础隐私扫描，但不能代替你自己的数据分类、权限、加密和密钥管理。

### scope 是过滤器吗？

默认不是：`strict_scope=False` 时只提升匹配候选，保证候选集合不变。显式开启 `strict_scope=True` 并提供非空 scope 时才严格过滤；这仍不等于核实正文事实。

## 10. 下一步

完成基础闭环后，按需求选择：

- 想了解完整 API：阅读项目 [README](../README.md#api-端点)；
- 想了解当前能力和限制：阅读 [STATUS.md](../STATUS.md)；
- 想接入 Agent：先使用 `vibe-init --dry-run`；
- 想提升中文语义召回：安装可选 semantic 依赖，并在自己的标注集上对照测试；
- 想长期运行文件库：再阅读 README 中的 WAL 维护说明，不要在第一次体验时提前开启复杂选项。

建议先把最小闭环跑通，再逐步加入 MCP、语义模型、LLM 建边和 WAL 维护。
