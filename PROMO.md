# VibeMemory 推广文案

> 适用平台：Twitter/X、Reddit、V2EX、掘金、知乎、即刻、LinkedIn
> 项目地址：https://github.com/sv8vkwmfr7-create/vibe-memory

---

## 纯文本介绍 · 通俗版

> 给非技术背景的人看，也要把核心机制说清楚

---

### 一段话

VibeMemory 就是给 AI 装了一个会记事的脑子，核心逻辑是**在一张记忆网里辐射寻找记忆**。只有关键信息才会被存成记忆卡片，每条卡片用 embedding 转成向量，语义相近的自然靠近。卡片之间自动建边——同一轮对话规则拉线零成本，跨会话用 LLM 判断关系（因果、修正、相似等 8 种标签），形成一张有方向有权重的网。检索时，先把你的问题转成向量找到种子卡片，再从种子出发沿关系线双向辐射游走——高权重边优先走，低于阈值就停，噪声自然过滤，三档可调（精准/全面/省钱）。每条记忆有权重，随时间衰减，被用到就强化，衰减速率由 Vibe Learner 在线学习器动态调整，高频记忆等效永久保存，低频自然淘汰。检索结果可按 MAC（全文注入）或 MAG（信号注入，体积减 65%）两种模式喂给 AI。每个模块都有降级兜底，不可用时不崩溃只退化。一个 pip install，三行代码，SQLite 零依赖，MIT 开源。

---

### 一句话说清楚

**VibeMemory 就是给 AI 装了一个会记事的脑子。** 每次你跟 AI 聊完，它自动把重点记住；下次你再找它，它不用你再说一遍，直接想起来。

---

### 为什么需要它？

现在的 AI 有个毛病：**换个会话就失忆。**

你跟它聊了一下午，修了 5 个 bug，换了 3 个方案。关掉窗口，明天再打开——它全忘了。你得从头讲一遍。

这不是 AI 笨，是它没有"长期记忆"。它只能记住当前对话窗口里的东西，窗口一关，记忆就没了。

---

### 它怎么解决？

VibeMemory 做了三件事：

**第一件事：自动记笔记。**

你跟 AI 聊天的过程中，VibeMemory 自动把关键信息拆成一条一条的"记忆卡片"。比如"修好了 API 超时问题，把 30 秒改成了 60 秒"，这就是一张卡片。

**第二件事：给卡片之间拉线。**

光有卡片不够，还要知道卡片之间是什么关系。比如：

- 🟢 卡片 A 导致了卡片 B → 拉一条"因果线"
- 🟡 卡片 A 和卡片 B 是同一类问题 → 拉一条"相似线"
- 🔴 卡片 B 推翻了卡片 A 的结论 → 拉一条"修正线"

这样记忆就不是一盘散沙，而是一张关系网。

**第三件事：顺着线找答案。**

当你下次问"上次那个 timeout 问题后来怎么样了"，VibeMemory 不会像传统搜索那样把所有带"timeout"的卡片都翻出来（包括一堆无关的），而是顺着关系线走——只走有意义的线，噪音自动过滤。

---

### 打个比方

传统 RAG 像一个图书管理员，你问"timeout"，他把所有书名里有"timeout"的书都搬给你，不管内容有没有关系。

VibeMemory 像一个老同事，你问"timeout"，他说："哦，上次那个啊——你先改了 30 到 60 秒，结果连接池崩了，后来发现 60 秒还是不够，最后改成 120 秒才彻底解决。" 他记住的是整个故事，不是关键词。

---

### 实际效果

| | 传统 RAG | VibeMemory |
|--|---------|-----------|
| 噪声（无关结果） | 20% | **0%** |
| 需要你重复背景 | 每次都要 | **不需要** |
| 跨会话记忆 | ❌ 断了 | ✅ 延续 |
| 知道因果关系 | ❌ 不知道 | ✅ 知道 |

---

### 技术门槛

不需要 GPU，不需要云服务，不需要数据库。一个 `pip install`，三行代码，跑在你自己电脑上。SQLite 存数据，Python 做计算，全部 MIT 开源。

---

## 纯文本介绍 · 营销版

> 借鉴优化版，适合公众号、知乎、即刻等社交平台

还在被大模型"金鱼记忆"困扰？每次新开对话就要重复交代项目背景、代码规范、修过的 bug，传统 RAG 只能检索碎片信息，搜"API timeout"给你返回"数据库连接池配置"——因为都有"config"这个词，但根本没关系。噪声比例 20%，跨会话记忆直接断层。

**VibeMemory**——多关系图记忆系统，专为 AI Agent 打造长期记忆基座。核心思路：给记忆之间建边。8 种边标签（因果接续、修正推翻、同类经验、时序相邻……），检索时用 Personalized PageRank 沿着有意义的边游走，噪声自动过滤，**20% → 0%**。

自动沉淀会话、任务、项目全局信息，智能区分"A 导致了 B"还是"A 跟 B 只是碰巧相似"。支持 OpenAI、Anthropic、DeepSeek、Ollama 等所有主流大模型做边分类，SQLite 零依赖私有化部署，MIT 开源，214 测试保障。

一次沉淀，永久复用。Agent 不再失忆，你不再重复。

三行代码接入：
```bash
pip install vibe-memory
```
```python
from vibe_memory import VibeMemory
mem = VibeMemory(agent_id="my-agent")
mem.store("修好了 API timeout", session_id="chat-1")
mem.recall("API timeout")  # 噪声 0%
```

GitHub：https://github.com/sv8vkwmfr7-create/vibe-memory

---

## 纯文本介绍 · 技术版

> 技术向，适合发 GitHub、Reddit、技术社区

VibeMemory — 多关系图智能体记忆系统

传统 RAG 的问题：向量检索只看"文字像不像"，不知道"A 导致了 B"还是"A 跟 B 只是碰巧都有 timeout 这个词"。搜"API timeout"，给你返回"DB pool config"——因为都有"config"这个词，但根本没关系。噪声比例 20%。

VibeMemory 的做法：给记忆之间建边。8 种边标签——因果接续（A 导致了 B）、修正推翻（B 推翻了 A）、同类经验（同一类问题）、时序相邻、引用、查阅、影响、版本。检索时用 Personalized PageRank 沿着边游走，高权重边优先，噪声自动抑制。噪声从 20% 降到 0%。

实验验证：DeepSeek-v4-flash 边分类准确率 80%，合并判断 100%，平均延迟 2.3 秒。本地小模型（小于 2B）不可用，需要 7B 以上或 API。

双模式注入：MAC 全文上下文 + 关系图谱，适合排错和编码；MAG 门控信号，只注入关键信息，体积减少 65%，适合策略和创意。

技术栈：Python 3.10+，numpy + SQLite，零重型依赖。sentence-transformers 可选。支持 OpenAI、Anthropic、DeepSeek 或本地模型做边分类。214 测试，29 commits，15 模块，MIT 开源。

三行代码接入：
pip install vibe-memory
from vibe_memory import VibeMemory
mem = VibeMemory(agent_id="my-agent")
mem.store("修好了 API timeout", session_id="chat-1")
mem.recall("API timeout")  # 噪声 0%

GitHub：https://github.com/sv8vkwmfr7-create/vibe-memory

---

## 中文 · 知乎/掘金/V2EX 长文

### 标题

**我花了 5 天，从零写了一个让 AI Agent 拥有长期记忆的开源项目**

### 正文

你有没有遇到过这些问题：

- 跟 Claude 聊了三轮，换个会话它完全不记得你刚才修了什么 bug
- RAG 检索返回一堆"看起来相关但其实无关"的噪声，模型被误导
- 每次新会话都要重新喂一遍背景，烦死了

我花了 5 天时间，从方案设计到代码实现，写了一个开源项目：**VibeMemory**——多关系图智能体记忆系统。

**它怎么解决问题？**

传统 RAG 的向量检索只看"文字像不像"，不知道"A 导致了 B"还是"A 跟 B 只是碰巧都有 timeout 这个词"。VibeMemory 的做法是：

1. **给记忆之间建边**——同会话自动建边（规则），跨会话用 LLM 判断关系（因果/修正/相似/无关）
2. **检索时沿着边游走**——用 Personalized PageRank 替代暴力向量搜索，高权重边走，噪声自动抑制
3. **注入时按优先级分组**——MAG 门控模式只注入关键信号，不灌满上下文

**数据说话**

| 指标 | 传统 RAG | VibeMemory |
|------|---------|-----------|
| 噪声比例 | 20% | **0%** |
| 用户重复背景 | 每轮都要 | **0 次** |
| 跨会话召回 | ❌ | ✅ 100% |

**技术栈**

- Python 3.10+，纯 numpy + SQLite，零重型依赖
- sentence-transformers 可选（语义 embedding）
- 支持 OpenAI / Anthropic / DeepSeek / 本地模型做边分类
- 214 测试，29 commits，MIT 开源

**5 分钟上手**

```bash
pip install vibe-memory
```

```python
from vibe_memory import VibeMemory

mem = VibeMemory(agent_id="my-agent")
mem.store("修好了 API timeout，从 30s 改成 60s", session_id="chat-1")
result = mem.recall("API timeout", mode="precision")
# 自动召回相关记忆，噪声 0%
```

**GitHub**: https://github.com/sv8vkwmfr7-create/vibe-memory

欢迎 Star，欢迎提 Issue，更欢迎一起讨论 Agent 记忆这个方向。

---

## 中文 · 即刻/朋友圈 短文案

🆕 开源了一个 AI Agent 记忆系统：VibeMemory

❌ 传统 RAG：噪声 20%，张冠李戴
✅ VibeMemory：图结构 + 边标签过滤，噪声 0%

5 天从零到 29 commits，214 测试，已发布 GitHub

👉 https://github.com/sv8vkwmfr7-create/vibe-memory

---

## English · Twitter/X Thread

**1/6** I built an open-source memory system for AI agents: VibeMemory 🧠

The problem: RAG vector search returns 20% noise. It finds "similar" text but doesn't know WHY two things are related.

**2/6** VibeMemory's approach:

Instead of flat vector search, it builds a **graph** between memories:
- causal edges (A caused B)
- revision edges (B corrected A)
- similar edges (same type of experience)

**3/6** Retrieval uses Personalized PageRank — walk along meaningful edges, ignore noise.

Result: **noise drops from 20% → 0%**. Not prompt engineering. Architecture-level.

**4/6** Real LLM validation:
- DeepSeek-v4-flash: 80% classification accuracy, 2.3s latency
- Local models <2B: unusable (always predicts "causal")

**5/6** Dual-mode injection:
- MAC: full context + relationship map (debugging)
- MAG: gated signals only (strategy/creative) — 65% smaller

**6/6** Python. SQLite. MIT license. 214 tests. 5-minute quickstart.

GitHub: https://github.com/sv8vkwmfr7-create/vibe-memory

---

## English · Reddit r/MachineLearning / r/LocalLLaMA

**Title**: [P] VibeMemory — Graph-based memory for AI agents, noise 20%→0% vs RAG

**Body**:

I built a multi-relationship graph memory system for AI agents that solves the false recall problem in vector RAG.

**The Problem**: Vector search retrieves "DB pool config" when querying "API timeout" because both share the word "config". That's 20% noise ratio.

**The Solution**: Instead of flat embeddings, VibeMemory builds a graph with 8 edge labels (causal, revision, similar, adjacent, etc.) and uses Personalized PageRank for retrieval. PPR only walks along meaningful edges, naturally suppressing noise.

**Key Results**:
- Noise: 20% → 0% (validated across 14 experiments)
- Cross-session recall: 100% (5/5 in real vault usage)
- LLM edge classification: 80% accuracy with DeepSeek-v4-flash
- 214 tests, 29 commits, MIT license

**Architecture**:
- Semantic chunking with Surprise-based filtering
- Two-tier edge building (rule-based intra-session + LLM inter-session)
- PPR graph walk with 3 configurable modes (precision/recall/budget)
- MAC/MAG dual-mode prompt injection
- SQLite + optional sentence-transformers

**Quick Start**:
```python
from vibe_memory import VibeMemory
mem = VibeMemory(agent_id="agent")
mem.store("Fixed API timeout", session_id="chat-1")
mem.recall("API timeout")  # 0% noise
```

GitHub: https://github.com/sv8vkwmfr7-create/vibe-memory

Would love feedback from the community — especially on the edge classification approach and whether graph-based retrieval is the right direction for agent memory.

---

## English · LinkedIn

🚀 Just open-sourced VibeMemory — a graph-based memory system for AI agents.

After 5 days of intensive development (29 commits, 214 tests, 15 modules), here's what came out of it:

The core insight: **Vector search alone can't tell WHY two memories are related.** It sees "API timeout" and "DB pool config" as similar just because they share the word "config." That's 20% noise.

VibeMemory solves this by building a **relationship graph** between memories:
- Causal edges (A caused B)
- Revision edges (B corrected A)
- Similar edges (same type of experience)

Retrieval uses Personalized PageRank to walk along meaningful edges — noise drops from 20% to 0%.

Built with Python, SQLite, and MIT license. Works with OpenAI, Anthropic, DeepSeek, or local models.

🔗 https://github.com/sv8vkwmfr7-create/vibe-memory

#OpenSource #AIAgent #RAG #Memory #MachineLearning

---

## 抖音 · 图文文案

> 抖音支持图文模式，以下可直接复制发布

---

### 封面图

纯黑底 + 大字三行：

```
RAG 检索
噪声 20%
↓
VibeMemory
噪声 0%
```

---

### 正文（复制到抖音）

你有没有遇到过：

跟 AI 聊了三轮，换个会话它完全不记得你刚才修了什么 bug 😤

传统 RAG 的问题：搜"API timeout"，给你返回"DB pool config"——因为都有"config"这个词，但它俩根本没关系。噪声比例 20%。

我写了一个开源项目解决这个问题 👇

**VibeMemory**：给 AI 的记忆之间建边

🔗 因果边：A 导致了 B
✏️ 修正边：B 推翻了 A
📎 相似边：同类经验

检索时沿着边游走，噪声自动过滤——**20% → 0%**

🐍 Python 一行安装
📦 SQLite 零依赖
✅ 214 测试，MIT 开源
🤖 支持 OpenAI / Claude / DeepSeek

GitHub 搜：VibeMemory

---

### 配图建议（6 张）

1. 封面：RAG 噪声 20% → VibeMemory 0%
2. 痛点截图：AI 说"我不记得了"
3. 架构图：5 层架构（从 README 截）
4. 对比表：RAG vs VibeMemory 召回对比
5. 代码截图：三行代码接入
6. GitHub 页面截图

### 话题标签

`#AI #开源 #程序员 #Python #RAG #Agent #GitHub`

### 评论区置顶

> 项目叫 VibeMemory，MIT 开源，三行代码接入 👇
> https://github.com/sv8vkwmfr7-create/vibe-memory