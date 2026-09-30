# VibeMemory 公开介绍

> 文案核对：2026-10-01。旧版营销模板已替换；以下介绍只描述项目能力，不承诺通用效果、零成本或无需接入。
> 项目地址：[GitHub](https://github.com/sv8vkwmfr7-create/vibe-memory)

## 中文短介绍

VibeMemory 是一个面向 AI Agent 的本地记忆库：用 SQLite 保存事实、会话片段和带标签的关系，通过关键词、向量和图等策略检索上下文。Python SDK、MCP、HTTP 和 CLI 提供不同接入方式；应用需要主动调用写入、召回或会话生命周期接口，并将结果提供给模型，不是安装后就自动记住所有聊天。

基础 TF-IDF 路径无需 GPU 或云模型，但需要 Python 和 numpy（Python 3.10 另需 tomli）。可选语义模型会增加下载、启动、内存和推理成本；云端分类或反思需要调用方提供配置，并承担对应 API 费用。本地保存数据不意味着可选云调用不会发送文本。

## 中文技术介绍

- 数据层：SQLite 中的 MemoryAtom、Edge 和 Episode。
- 检索：TF-IDF/BM25、图关系与时序信息，按模式组合候选并融合排序。
- 关系：SDK 支持规则建边及可选 LLM 复核；标签和置信度不是已证明的因果事实。
- MCP：默认写入不自动建边；可手工使用 vibe_link，已有合法边仍可参与检索。
- 注入：MAC/MAG 生成不同粒度的上下文文本；应用负责注入，不承诺固定压缩比例、模型必然采用或防提示注入。
- 维护：提供衰减、GC、隐私规则及可选 WAL 维护；不是永久保存、完整遗忘或防泄漏保证。
- 适配：LangChain helper 需手动读写接线；OpenAI Agents 返回的普通函数需 function_tool 包装。见[适配器契约](docs/ADAPTER_CONTRACTS.md)。

## 从源码体验

当前说明不依赖 PyPI 发布状态：

```bash
git clone https://github.com/sv8vkwmfr7-create/vibe-memory.git
cd vibe-memory
python -m venv .venv
# 激活该环境后
python -m pip install -e .
python examples/quickstart.py
```

Windows、MCP 配置及实际成功判据见[零基础指南](docs/GETTING_STARTED.zh-CN.md)。SDK 最小示例：

```python
from vibe_memory import VibeMemory

memory = VibeMemory(agent_id="demo", db_path="memory.db", embedding_backend="tfidf")
memory.store("API timeout was changed to 60 seconds", session_id="chat-1")
result = memory.recall("API timeout")
print([atom.content for atom in result["atoms"]])
```

这个示例验证调用方式，不是召回率、噪声率或跨会话答案正确性的统计证据。

## English short introduction

VibeMemory is a local memory library for AI agents. It stores facts, conversation fragments and labeled relationships in SQLite, then retrieves context through lexical, vector and graph-based strategies. Applications explicitly wire storage, retrieval and context injection; installation alone does not enable automatic memory in every chat.

The TF-IDF path needs no cloud model or GPU, but has Python dependencies and local resource costs. Semantic models and optional LLM classification/reflection add their own setup, latency and usage costs. MCP writes do not automatically create edges by default; manual links or other ingestion paths can supply them.

## Evidence and publication rules

- Current test/coverage results and reproduction commands: [TESTING](docs/TESTING.md); review repair state: [REVIEW_REPAIR_PROGRESS](docs/REVIEW_REPAIR_PROGRESS.md).
- Synthetic regression data: [retrieval-ablation-v3 JSON](results/retrieval_ablation.json). Generated queries, relevance labels and edges are not independent evidence of superiority over other systems.
- Public-data retrieval pilots and paired results: [STATUS](STATUS.md). Retrieval evidence is not final-answer accuracy or an independent human quality review.
- There is no version-aligned, same-model, same-budget head-to-head result establishing a general competitor advantage.
- Do not publish historical test/commit counts as current guarantees, extrapolate a few model classifications to model-size requirements, or claim universal noise elimination, permanent memory, zero user effort or zero total cost.
