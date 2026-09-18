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
5. 显式 `scope` 可以提升匹配作用域的候选，但不会过滤其他候选。

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
- `vibe_link`、`vibe_forget`、`vibe_flush`：进阶管理工具。

首次验证建议让 Agent 执行：

```text
请用 vibe_store 记住：本项目正式环境订单服务超时为 60 秒。
```

新开一个会话后再问：

```text
请用 vibe_recall 查找订单服务的超时配置。
```

只有跨会话召回到了刚才的信息，才算 MCP 端到端接入成功。配置文件写入成功或工具列表可见，都只是中间证据。

## 8. scope 怎么用

`scope` 是调用方明确提供的上下文，目前支持三个字符串字段：

| 字段 | 示例 | 含义 |
|------|------|------|
| `service` | `orders` | 服务或模块 |
| `environment` | `production` | 环境 |
| `operation` | `export` | 操作或场景 |

scope只对已经召回的候选做稳定提升，不会删除不匹配项，也不会自动从自然语言推断。未传scope时保持原排序。

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

不是。当前scope只提升匹配候选，保证候选集合不变。

## 10. 下一步

完成基础闭环后，按需求选择：

- 想了解完整 API：阅读项目 [README](../README.md#api-端点)；
- 想了解当前能力和限制：阅读 [STATUS.md](../STATUS.md)；
- 想接入 Agent：先使用 `vibe-init --dry-run`；
- 想提升中文语义召回：安装可选 semantic 依赖，并在自己的标注集上对照测试；
- 想长期运行文件库：再阅读 README 中的 WAL 维护说明，不要在第一次体验时提前开启复杂选项。

建议先把最小闭环跑通，再逐步加入 MCP、语义模型、LLM 建边和 WAL 维护。
