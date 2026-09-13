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
