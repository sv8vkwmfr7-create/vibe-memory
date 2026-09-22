# 外部会话检索评测

运行：`python experiments/session_evaluation.py /absolute/path/corpus.json --top-k 5`

输入仅本地读取，不调用外部模型，不自动保存或上传原文。输出包含数据集 ID、问题 ID 和记忆 ID：这些 ID 也应脱敏。私有数据放仓库外，勿提交到 GitHub。

输入 JSON 必填字段：

- `dataset_id`：匿名数据集版本。
- `atoms`：MemoryAtom 字段；至少显式填写 id、agent_id、tenant_id、session_id、content、summary、created_at。
- `edges`：可选 Edge 字段；至少显式填写 id、from_atom_id、to_atom_id、tenant_id、label、created_at。人工建边应与实际自动建边评测区分。
- `queries`：id、text、agent_id、tenant_id、cutoff（ISO 日期时间）、relevant_ids（人工标注非空 ID 列表）。所有时间使用相同的时区约定。

每个问题只装载 cutoff 之前、相同租户/Agent 的 active/warm 记忆与历史边，避免未来答案泄漏。语料必须保留当时的快照：仅靠 created_at 无法还原后续修改的内容与生命周期。

对比无记忆、BM25、TF-IDF 和二跳 budget。计时包含首次检索索引构建，不含数据导入；各方法没有跨问题缓存。输出逐问题 Precision/Recall 和延迟，无记忆是空检索基线，不是 LLM 回答质量基线。

建议先选脱敏故障、配置修改和历史决策。按完整会话划分调试集和独立测试集，标注者核对原始证据；不要用独立测试集反复调参。当前尚未提供真实语料，不宣称真实会话效果已验证。

## LoCoMo 公开文本证据试跑（2026-09-22）

从 [LoCoMo 官方数据](https://github.com/snap-research/locomo/blob/main/data/locomo10.json)下载 `locomo10.json` 到仓库外，运行：

```text
python -m experiments.locomo_retrieval /absolute/path/locomo10.json --sample-index 0 --top-k 5 --json results/locomo_text_dialogue_pilot.json
```

适配器复用本页评测器：一条文本对话轮次对应一个 Atom，官方 `dia_id` 是证据 ID，会话时间保留为 `created_at`，不生成摘要或图边。只纳入证据 ID 存在、非图片证据的题；缺失证据、图片证据、无证据分别计数。问题取官方顺序，不按答案挑选。对所有会话 `--sample-index` 分别运行前，不应称为完整 LoCoMo 评测。`--max-queries N` 仅用于固定顺序的试跑，默认 0 代表该样本全部合格问题。

首次试跑锁定原始文件 SHA-256 `79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4`。`conv-26` 的 199 题中，131 题合格，排除缺失证据 1、图片证据 65、无证据 2；Top-5 的宏证据召回：BM25 **0.445**、TF-IDF **0.368**、现有 budget **0.176**，无记忆 **0**。budget 在无图边输入上明显弱于两个单路基线；这里仅记录现象，未定位为哪一级候选或排序造成，也未调参。

这些数值是**官方证据对话 ID 的检索试跑**，不是官方 LoCoMo 最终问答分数、跨产品比较、全数据集成绩或生产效果。官方 evidence 不保证列出所有相关对话，所以不把未标注返回项算作可靠的 Precision。图片题被系统性排除，样本仅一个会话；首次结果也不能作为未触碰的调参后测试集。完整原始数据不入库，报告只存哈希、计数和聚合，不存原文。

### budget 候选池阶段诊断

同一 `conv-26`、131题、Top-5、输入哈希下，报告新增 `budget_candidate_diagnostic`：100条候选上限内至少有一条官方证据的仅 **36/131**；BM25能命中而budget漏掉的 **43** 题中，**42** 题的证据在候选池已缺席，**1** 题入池后仍未进Top-5。该统计重放当前 `get_recall_candidates` 的上限、图邻居配额和两跳参数，不改变SDK/MCP。

最小公开复现是官方首题 `conv-26-qa-0`：前100条对话时budget命中证据 `D1:3`，前110条时漏掉，而BM25仍命中。前110条中，FTS全部查询词的AND匹配为0、OR匹配为103；当前英文FTS候选按 `rowid DESC` 截前100，`D1:3` 位于第101。仅将这103条按FTS BM25分数查看时，它位于第1。这解释该题的损失阶段，不证明将存储排序改为BM25能改善所有题，也未测此改动的耗时、中文行为、图邻居预算或负例风险。下一步必须做同输入受控对照与回归后才能考虑生产变更。
