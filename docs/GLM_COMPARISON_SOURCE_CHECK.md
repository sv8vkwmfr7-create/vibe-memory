# GLM 综合报告：竞品一手来源口径核验

核验日期：2026-10-01。对象：本地 `vibe-memory-综合评估报告.md` 第六部分及附录。仅查官方文档、源码和原论文；未安装或实测竞品，不验证旧 VibeMemory 实测，不改原报告。网页与 `main` 分支会变化，本页不把当前文档倒推为所有历史版本。

## 可以保留，但必须限定范围

- **Mem0 ADD-only**：官方 2026-04-16 发布、2026-09-28 更新的[算法说明](https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm)确实描述新增单次 ADD-only 抽取，旧流程使用 ADD/UPDATE/DELETE。[当前 OSS v2→v3 迁移说明](https://github.com/mem0ai/mem0/blob/main/docs/migration/oss-v2-to-v3.mdx)和[add 文档](https://github.com/mem0ai/mem0/blob/main/docs/core-concepts/memory-operations/add.mdx)也支持新算法边界。但 ADD-only 指抽取流水线，不等于禁止显式修改或删除：当前[官方 SDK 源码](https://github.com/mem0ai/mem0/blob/main/mem0/memory/main.py)仍有 `update()`、`delete()`。本轮没有逐 tag 确认首次发布包版本，不能泛化为所有 Mem0 版本或所有后端。
- **Mem0 92.5% / 94.4%**：上述算法说明和[官方评测仓库](https://github.com/mem0ai/memory-benchmarks)确认，分别是托管平台 LoCoMo 1425/1540、LongMemEval 472/500，结果表使用 Top 200；评测经过检索、答案生成、LLM judge，是最终回答正确率，不是 hit@5。算法说明明确平台含 OSS 不具备的专有优化，使用一次检索、一次回答，且注明 judge 不一致性约 ±1 点。公开代码可供复跑不等于本轮已独立复跑。新算法和平台能力也需分开：SDK `project.update(decay=True)` 在当前源码直接报不支持。
- **Zep/Graphiti 时序机制**：[官方图概览](https://help.getzep.com/v2/graphiti/getting-started/overview)和[事实字段说明](https://help.getzep.com/facts)确认 bi-temporal：现实有效时间 `valid_at`/`invalid_at`，系统获知时间 `created_at`/`expired_at`。这证明机制存在，不证明每次抽取失效时间或回答都正确；文档明确时间字段不能保证来源或推导事实为真。开源 Graphiti 与托管 Zep 不是同一个部署产品。
- **Hindsight 83.6%**：[原论文 v1 第 7.2–7.4 节、表 3](https://arxiv.org/html/2512.12818v1)为 LongMemEval S、500 问的回答 overall accuracy；主配置 GPT-OSS-20B 负责抽取与反思，GPT-OSS-120B 负责 judge。不是检索 hit@5、不是无 LLM 的存储效果。论文另有更大模型配置和其他基准，本页不混用。
- **MemConflict**：[原论文](https://arxiv.org/html/2605.20926v1)确实评测六种系统的动态、静态、条件冲突，区分最终回答与支持证据检索/排名。六种为 A-Mem、LangMem、Letta、MemOS、Mem0、Memobase，不包含 Zep；不能据此称已统一测过所有报告中的竞品。

## 必须纠正的两处数字解释

1. **Letta 文件 74.0% 不是纯文件检索 hit@5。** [2025-08-12 官方说明](https://www.letta.com/blog/benchmarking-ai-agent-memory/)是 GPT-4o-mini Agent 在 LoCoMo 的 QA accuracy。文件会自动解析、embedding，Agent 使用语义搜索、grep、open/close，并可多轮搜索后回答；不是“一个 markdown 文件无模型”、不是全历史直接塞进上下文。因此旧报告把 VibeMemory 自建换述 hit@5=0.7 与该 74% 做近似，或据此宣判所有配置都不如纯文件，不成立。Letta 也不必把十万条一起装进上下文，旧报告的规模“✗ 上下文装不下”没有对应实测证明。
2. **Zep 63.8% 不应标为时序子项。** [Zep 原论文表 2、3](https://arxiv.org/html/2501.13956v1)的 63.8% 是 LongMemEval S 整体、GPT-4o-mini；时序子项为 54.1%（mini）及 62.4%（GPT-4o）。如果旧报告引用第三方另一配置恰为 63.8%，须补精确报告、版本、问题集和配置，当前域名链接不足以核验。

## 当前不能支持的横向结论

- 附录的 codebridge.tech、zylos.ai、beri.net、arxiv.org 等主页无法唯一定位 29.3%、49%、p95 4.85s/0.632s 的原始运行。它们不能证明新算法平台自报被“独立复现推翻”；本轮未用二手转述证明性能。需具体文章/论文/结果和系统版本。
- VibeMemory 毫秒级检索与竞品检索后生成答案或多轮 Agent 的秒级响应不是同一计时边界。没有同数据、同硬件、同模型、同返回预算和同计时边界，不支持“100× 优势独占”。
- “Mem0 离线/隐私 ✗”过度绝对：[官方评测仓库 Custom Models](https://github.com/mem0ai/memory-benchmarks#custom-models)提供 fully local Ollama 配置；托管方案与本地 OSS 配置应分列。需要模型并不等于必须 API 或数据出本地。
- 架构具有更新机制、图能力、规模支撑，不等于在旧报告全部自建场景必然通过。第 6.2 节的机制推演只能保留为假设，不能作为性能名次或已复现质量证据。

## 对后续开发的可用启示

保留“事实更新、换述、无关查询、规模与成本、接入默认行为”的评测方向；废除跨数据集直接百分比排序。后续基准应同时报告检索支持证据 hit@K、当前/历史事实适用性、无答案拒答、最终回答正确率、端到端延迟、模型/token/安装时间成本，并固定版本、后端和返回预算。本页未关闭任何 VibeMemory 审查项。
