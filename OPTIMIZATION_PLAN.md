# VibeMemory 优化计划 — Hindsight 启发

## 优先级矩阵

| 优先级 | 功能 | 工作量 | 风险 | 价值 |
|--------|------|--------|------|------|
| P0 | 多策略并行检索 | 2h | 低 | 极高 |
| P0 | 交叉编码器重排 | 0.5h | 低 | 高 |
| P1 | 一键安装编程 Agent | 0.5h | 低 | 高 |
| P1 | 隐私扫描 | 0.5h | 低 | 中 |
| P2 | 反思（Reflect） | 1h | 中 | 中 |
| P2 | 知识页面 | 1h | 低 | 中 |

---

## P0：多策略并行检索 + 交叉编码器重排

### 可行性分析

**现状**：`recall()` 是一条单路管道——向量预筛 → 种子过滤 → PPR 图游走。只用了一种检索策略。

**目标**：4 路并行检索 + RRF 融合 + 可选重排。

**技术方案**：

```
查询 → 并行分发
  ├─ 语义检索（embedding cosine → top-K seeds）
  ├─ 关键词检索（BM25 → top-K keywords）
  ├─ 图检索（PPR graph walk）
  └─ 时序过滤（time_range → boost recent）
     ↓
  RRF 融合排序（Reciprocal Rank Fusion）
     ↓
  可选：交叉编码器重排（CrossEncoder / LLM score）
     ↓
  最终结果
```

**BM25 实现**：纯 Python，零依赖。约 50 行。公式：`score = IDF(q) * (freq * (k1+1)) / (freq + k1 * (1 - b + b * doc_len / avg_len))`

**RRF 实现**：`score = Σ 1/(k + rank_i)`，k=60。约 10 行。

**交叉编码器重排**：做成可插拔接口。默认用 embedding 相似度，可选 CrossEncoder 或 LLM。先做默认版。

**风险评估**：
- BM25 与 embedding 语义互补，不同场景各有优势：BM25 擅精确匹配（"API timeout"），embedding 擅语义泛化（"接口超时"）
- RRF 不需要调参，直接可用
- 对现有代码改动最小：新增 `RetrievalStrategy` 类，`recall()` 添加 `strategies` 参数

**依赖**：无新增依赖。BM25 纯 numpy，RRF 纯数学。

### 实现步骤

1. 新增 `vibe_memory/retrieval/strategies.py`：BM25 + Semantic + Graph + Temporal 四个策略类
2. 新增 `vibe_memory/retrieval/fusion.py`：RRF 融合 + Reranker 接口
3. 修改 `vibe_memory/retrieval/ppr.py`：`recall()` 集成多策略
4. 新增 `tests/test_retrieval_strategies.py`：多策略 + 融合 + 重排测试

---

## P1：一键安装 + 隐私扫描

### 可行性分析

**一键安装**：检测当前目录是否存在 `.claude`、`.codex`、`.cursor` 等配置目录，自动生成对应的 MCP 配置或 hook 脚本。约 80 行。

**隐私扫描**：正则匹配 20+ 种 PII 模式（API key、密码、邮箱、手机号、身份证、银行卡、IP 地址、JWT token）。在 `store()` 前自动调用，默认脱敏，可配置拦截。约 100 行。

**依赖**：无。纯 Python 标准库。

---

## P2：反思 + 知识页面

### 可行性分析

**反思**：后台任务，定期调用 LLM 对近期记忆做跨记忆推理，生成"洞察"存入新 atom。需要 LLM API，做成可选功能。

**知识页面**：按 session/主题聚合记忆，生成 Markdown 文档。纯模板引擎，约 100 行。

**风险评估**：反思依赖 LLM，成本较高。知识页面是纯文本生成，无风险。

---

## 执行顺序

```
P0.1 多策略检索（BM25 + 并行 + RRF）→ 测试
P0.2 交叉编码器重排（可插拔接口）→ 测试
P1.1 一键安装（vibe-memory init）→ 验证
P1.2 隐私扫描（defense.py）→ 测试
P2.1 知识页面（knowledge_pages.py）→ 测试
P2.2 反思（reflect.py）→ 测试
```

## 预期结果

- 检索质量：BM25 补充精确匹配，RRF 融合提升 Recall@K 10-20%
- 一键安装：`vibe-memory init` 自动配置 Claude Code/Codex/Cursor
- 隐私：`store()` 自动拦截 API key 和密码
- 测试：新增 ~40 个测试，全量保持通过