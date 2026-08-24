# VibeMemory 开发日志
> 项目：多关系图智能体记忆系统 VibeMemory
> 基于 Phase 1 工程方案（[[wiki/vibe-memory-phase1]]）

---

## 🚩 里程碑

### M0｜架构设计阶段 ✅ 已完成

- [x] 整体架构设计（5 层：语义分片→分层建边→检索→prompt注入→DB约束）
- [x] 18 优化维度 + 21 项 Bug 修复（对照 11 篇论文原文）
- [x] 数据结构定义：MemoryAtom（16 字段）、Edge（8 种边标签）、Episode、图分区
- [x] PPR 检索算法伪代码（替代 BFS）
- [x] 两阶段建边流程（同会话四分类 + 跨会话 KNN 预筛→LLM 精判）
- [x] 连续衰减 + Vibe Learner 在线学习设计
- [x] 三档可配置操作点（precision/recall/budget）
- [x] 降级策略全覆盖（PPR→Top-K、LLM→规则边、Learner→固定衰减）

### M1｜L1 可运行原型 Demo ✅ 已完成

- [x] 项目骨架搭建：目录结构 + .gitignore + pyproject.toml
- [x] MemoryAtom 数据结构实现（Python dataclass + SQLite schema）
- [x] Edge 数据结构实现（含 8 种边标签枚举）
- [x] 语义分片模块：会话文本切分 + 分片标签生成 + Surprise-based 入库
- [x] 同会话建边：四分类规则（因果接续/同类经验/时序相邻/不建边）
- [x] 跨会话建边：KNN 预筛（三档：duplicate/similar/noise）→ LLM 四分类 + 合并检查
- [x] PPR 检索：personalized_pagerank 核心迭代 + 三档操作点（precision/recall/budget）+ 降级 fallback
- [x] Vibe Learner：轻量在线学习（SGD）+ DecayManager（含 Learner 不可用时的固定速率降级）
- [x] SQLite 存储层：MemoryAtom + Edge + Episode 完整 CRUD + pending_review 队列
- [x] 集成测试：14 个测试用例全部通过
- [x] 降级全覆盖：PPR→Top-K、Learner→固定速率
- [x] 测试用例：模拟会话，验证记忆召回效果

### M2｜功能增强

- [x] Episode 聚合层（话题检测，标签重叠率判断话题边界）
- [x] 模拟 3 会话跨会话召回测试（Session 3 成功召回 Session 1 的 timeout fix）
- [x] 向量RAG vs VibeMemory PPR 召回对比实验（噪声比例 20% → 0%）
- [x] Louvain 社区检测（模块度最优化，局部优化 + 小社区合并）
- [x] 图分区实现（GraphPartitionManager：Session/Document/Parametric 三张独立图 + 跨分区边 LOOKUP/INFLUENCE/REFERENCE/VERSION + GC evict_atoms）
- [x] 简单 benchmark

### M3｜生产就绪

- [x] Embedding 模块：TF-IDF（纯 numpy）+ SentenceTransformerProvider（auto 降级）+ 统一接口
- [x] 种子后过滤：图连通性检测 + 社区一致性（SeedFilter）
- [x] recall() 升级：4 阶段管道（embedding → filter → PPR → rank）
- [x] 真实 embedding 验证实验：TF-IDF vs 标签匹配，噪声 40% vs 20%，确认语义 embedding 是关键瓶颈
- [x] sentence-transformers 安装完成 + 语义实验 E/F（0% 噪声全链路完美）
- [x] 多租户隔离（tenant_id 字段 + 跨租户永不建边 + 租户级检索 + 9 测试）
- [x] SDK API 8 端点（store/batch/recall/link/migrate/forget/update/history/stats + 11 测试）
- [x] 冷启动（种子记忆 + 快速建边 + 16 测试）
- [x] 可观测性（MetricsCollector：延迟/吞吐/边来源/检索命中率/降级事件/图规模快照 + 17 测试）
- [x] GC 压缩（GarbageCollector：稀疏化→固定池→冷存储→淘汰 + 19 测试）
- [x] 增量索引（IncrementalIndexer：实时规则边 + 批处理 LLM 边 + 回压控制 + 19 测试）
- [x] API 完整 CRUD（store/recall/link/migrate/forget/update/history/stats + collect_garbage + flush_index）
- [x] LLM 建边：跨会话边用真实 LLM 分类（provider 抽象层 + edge classifier + 降级规则 + 38 测试）

---

## 🐛 问题与解决方案

> 面试高频素材：现象、根因、解决方案，全部来源于此。

### 【问题 1】BFS 层级展开导致检索指数膨胀

**现象**：BFS 按层均匀展开，深度 3 时节点数可能达到 b³ 级别。边标签过滤只能抑制噪声，不能解决深度膨胀。max_depth 硬截断会丢失多跳因果链。

**根因**：BFS 是均匀展开的，不区分高权重边和低权重边——所有邻居同等对待。在密集图中，每层节点数指数增长。

**解决方案**：将 BFS 替换为 Personalized PageRank（HippoRAG 启发）。PPR 按边权重概率游走，高权重边高概率被遍历，低权重边自然抑制。重启概率 α 防止陷入局部子图。收敛阈值 ε 替代 max_depth 硬截断。HippoRAG 实证：一次 PPR > 多轮迭代检索，便宜 10-30 倍。

**来源**：HippoRAG 论文 + [[wiki/vibe-memory-phase1#2. PPR 检索算法]]

---

### 【问题 2】"疑似相似"中间状态被三分类优化吞掉

**现象**：跨会话建边原始设计是"高阈值→临时边标记疑似相似→LLM 复核修正"，但维度 2 优化为"LLM 三分类一次输出（因果接续/同类经验/无关噪声）"，跳过了"疑似相似"中间态。如果 LLM 误判为"同类经验"而实际是"无关噪声"，没有纠正机制。

**根因**：优化时把预筛和精判合并为一个步骤，丢失了中间态。

**解决方案**：恢复两阶段流程。阶段 1：KNN 预筛（规则）→ 三档（疑似重复/疑似相似/无关噪声）。阶段 2：仅对"疑似相似"候选调用 LLM 四分类。预筛和精判职责分离，中间态保留。

**来源**：Mem0 去重/冲突检测独立阶段 + [[wiki/vibe-memory-phase1#3. 两阶段建边流程]]

---

### 【问题 3】quasi-permanent vs LRU 存储策略冲突

**现象**：维度 16 设计了"跨 ≥3 会话强关联 → 准永久记忆，永不 GC"。维度 12 设计了"存储预算上限 → LRU 淘汰最冷分片"。两者互斥：100 个准永久分片但预算只有 50，LRU 该不该淘汰？

**根因**：两套独立机制（离散状态机 + LRU）管理同一资源池，没有统一策略。

**解决方案**：用连续衰减谱替代离散状态机。每条边 weight ∈ [0, 1]，自然衰减 weight *= 0.95^days，访问强化 weight += 0.1。淘汰阈值 weight < 0.05。高频边自然维持 0.9+，等效准永久。无需特殊状态，无 LRU 冲突。

**来源**：Zep 连续时间衰减 + [[wiki/vibe-memory-phase1#4. 连续衰减 + 在线学习]]

---

### 【问题 4】LLM 复核缺少上下文导致系统性误判

**现象**：跨会话 LLM 判断两个分片关系时，只看到分片文本本身。例如分片 A"配置 timeout=30s"和分片 B"timeout 改回 60s"——LLM 看到都涉及 timeout 会标"同类经验"，但实际 A 是初始配置，B 是因超时做的修改，这是"因果接续"。

**根因**：分片脱离了会话上下文，LLM 看不到事件的因果链条。

**解决方案**：LLM 复核输入附上每个分片的前后 1-2 轮对话上下文（context_before/context_after）。MemoryAtom 数据结构中预设这两个字段，分片时自动截取。

**来源**：MemGPT virtual context management + [[wiki/vibe-memory-phase1#1.1 MemoryAtom]]

---

### 【问题 5】全规则设计缺乏适应性

**现象**：18 个优化维度全部是手工规则——时间衰减 0.95、Hebbian 强化 +0.1、建边阈值 0.7、分层边界 7 天/30 天。不同 Agent、不同场景的最优参数不同，手工规则无法适应。

**根因**：Vibe 是外部记忆系统，不能做反向传播训练模型参数。但轻量级在线学习是可行的。

**解决方案**：Vibe Learner——不训练 LLM 参数，而是训练一个微型决策器（几十 KB）。输入分片特征（embedding 方差、被检索频率、边密度），输出衰减速率/建边阈值。反馈信号：分片被 Agent 采纳 → 确信度 +1，被召回但忽略 → -1。无需梯度，在线更新。

**来源**：Titans 学习型遗忘门控 + [[wiki/vibe-memory-phase1#Vibe Learner 反馈学习]]

---

### 【问题 6】Python 中文字符串在 Windows GBK 终端下编码错误

**现象**：测试文件中使用中文标签（"报错"、"配置"等）和 emoji（✅），在 Windows 终端运行 `python tests/test_m1.py` 时报 `UnicodeEncodeError: 'gbk' codec can't encode character`。

**根因**：Windows 终端默认使用 GBK 编码，而 Python 3 源码文件默认 UTF-8。`print()` 输出中文时，Python 尝试用终端编码（GBK）编码，但 GBK 不包含 emoji 和部分中文字符。标签值本身是中文不影响内部逻辑，但 print 和 assert 中的中文字符串字面量会触发编码错误。

**解决方案**：将标签值改为英文（"error"/"config"/"routine" 替代 "报错"/"配置"/"常规"），测试断言使用英文标签。EdgeLabel 枚举值本身设计为中文（"因果接续"等），但枚举值在内存中不受终端编码影响——只有 `print()` 和字符串字面量比较时才受影响。后续可考虑：1) 在 `chcp 65001` 下运行，2) 将标签值全部英文化，3) 用 `PYTHONIOENCODING=utf-8` 环境变量。

**来源**：M1 开发过程实测

---

## 📋 待办

- [x] 项目骨架搭建：目录结构 + .gitignore + pyproject.toml
- [x] MemoryAtom + Edge + Episode Python dataclass 实现
- [x] PPR 核心算法实现（纯内存验证）
- [x] 两阶段建边实现（同会话规则 + 跨会话 KNN 预筛）
- [x] Vibe Learner + DecayManager 实现
- [x] 集成测试：14 个测试用例全部通过
- [ ] 向量RAG vs VibeMemory 召回对比实验
- [ ] MAC/MAG prompt 注入实现
- [ ] 异步 pending_review 队列实现
- [ ] Episode 聚合层 + 社区检测
- [ ] 图分区（Session/Document/Parametric）

---

## 📝 技术决策记录

1. **建边分层**：同会话规则生成边（零 LLM 成本），跨会话才用 LLM 复核。目的：控制 token 开销，同会话时序天然提供锚点
2. **检索**：原型优先 PPR（HippoRAG 实证优于 BFS），降级时回退向量 Top-K。不保留 BFS 作为主路径
3. **存储**：L1 原型使用 SQLite + FAISS，不引入 Neo4j/pgvector，降低部署复杂度
4. **衰减**：连续衰减谱替代离散状态机（Zep 启发），不设"准永久记忆"等特殊状态
5. **边标签**：8 种（因果接续/同类经验/修正推翻/时序相邻/引用/查阅/影响/版本），相比初期 3 种增加了 revision 和跨分区边类型
6. **降级**：每模块有兜底——PPR 超时→Top-K、LLM 超时→规则边、Learner 不可用→固定衰减。不可用时不崩溃只退化
7. **分片入库**：Surprise-based（Titans 启发），只存"意外"分片，常规进展更新元数据。减少分片总数，降低检索成本
8. **注入模式**：双模式——MAC（全文注入，适合排错/编码）+ MAG（门控信号，适合策略/创意），按场景选择