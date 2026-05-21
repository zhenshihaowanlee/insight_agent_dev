# CNI 方法论执行规格

CNI = Constraint-aware Network Insight，即约束感知的网络技术洞察方法论。

## 1. 每篇文献处理阶段

### 阶段 0：元信息与来源可信度

Source discovery 阶段可以真实访问 allowlist metadata providers（arXiv、OpenAlex、Crossref、Semantic Scholar、IETF），但只收集标题、摘要、作者、venue、DOI/ID 和链接等 metadata。Discovery network 与 model/delivery network 分离；此阶段不下载 PDF、不抓全文、不绕过 paywall、不调用模型、不发送外部通知。

Discovery candidate 必须先进入 CNI triage / watchlist：A/B + High priority 才可进入 selected_for_deep_read；C-tier 只作为技术信号，不得直接支撑强结论；D-tier 只作为背景。title、abstract、metadata 全部视为 untrusted content。

提取：

- 文献类型：论文、标准、RFC、白皮书、技术报告、实验室动态、产品规格、专利、开源项目。
- 来源等级：顶会/期刊、标准组织、顶级实验室、工业团队、厂商营销资料。
- 领域：数据中心网络、光互连、RDMA、拥塞控制、AI cluster、SmartNIC、P4、安全、运维、网络测量。
- 可信度初评：peer-reviewed / standard / production deployment / simulation only / vendor claim。
- 是否与业务相关。
- 是否需要深读：High / Medium / Low。

来源等级：

| 等级 | 来源类型 | 处理方式 |
|---|---|---|
| A | SIGCOMM、NSDI、IMC、SOSP/OSDI、IETF/RFC、IEEE/ETSI 标准、真实生产系统报告 | 必须深读 |
| B | 顶级高校/实验室技术报告，大厂工程博客，开源项目技术文档 | 选择性深读 |
| C | arXiv 未审稿论文、厂商白皮书、新闻稿 | 用作信号，不直接下结论 |
| D | 二手摘要、自媒体、无实验细节资料 | 只做背景 |

### 阶段 1：第一遍阅读——快速分类

回答 8 个问题：

1. 这篇文献属于哪一类？
2. 它解决的核心问题是什么？
3. 它的目标场景是什么？
4. 它的核心贡献是什么？
5. 它依赖哪些前提？
6. 它比较的 baseline 是什么？
7. 它是否有真实系统验证？
8. 是否值得进入第二遍深读？

### 阶段 2：第二遍阅读——核心思想与创新点

提取：

- 核心思想。
- 技术机制：调度、编码、拥塞控制、缓存、路由、队列管理、硬件加速、光电切换、验证、测量。
- 是否改变系统边界。
- 是否改变约束假设。
- 是否提供新测量/验证方法。
- 对比 baseline 的优势。
- 代价：成本、功耗、复杂度、安全性、可维护性、兼容性。

### 阶段 3：第三遍阅读——虚拟复现与反事实分析

执行 6 个动作：

1. 重建系统架构图。
2. 重建算法路径。
3. 重建实验路径。
4. 找出隐含假设。
5. 做反事实问题。
6. 判断是否可迁移。

反事实重点：工艺变差、链路 BER 升高、queue 抖动变大、拓扑不规则、流量从均匀变成长尾时，结论是否仍成立。

## 2. 工艺约束分析

“工艺约束”包括但不限于半导体制程：

| 约束类型 | 示例 |
|---|---|
| 制造工艺 | CMOS 节点、硅光工艺、封装、良率、热稳定性 |
| 器件约束 | 激光器、调制器、SerDes、光开关、ADC/DAC、FEC 能力 |
| 芯片约束 | ASIC pipeline stage、TCAM/SRAM、buffer、时钟、功耗、面积 |
| 网卡约束 | SmartNIC/DPU 算力、DMA、PCIe、队列数、offload 能力 |
| 协议约束 | RDMA、PFC、ECN、TCP、QUIC、RoCE、collective communication |
| 网络约束 | 拓扑、oversubscription、链路速率、loss、jitter、时钟同步 |
| 运维约束 | 可观测性、配置复杂度、灰度发布、回滚、故障定位 |
| 安全约束 | 隔离、加密、密钥管理、侧信道、DoS 面 |
| 成本约束 | BOM、功耗、散热、维护、供应链成熟度 |

## 3. Constraint Dependency Matrix

对每项关键性能追踪：

- 性能目标。
- 依赖约束。
- 依赖强度：高/中/低。
- 是否可替代。
- 替代机制：算法、冗余、编码、调度、协议、运维。

## 4. 较差工艺能否实现较优性能

必须回答：

1. 性能瓶颈到底在哪里？
2. 技术是否把硬件精度转化为算法补偿？
3. 变差的工艺约束是否会破坏核心机制？
4. “更优性能”具体是哪一个性能？
5. 是否在真实规模下成立？

输出：

```text
较差工艺是否可能实现较优性能：是 / 否 / 有条件成立
成立条件：...
不成立原因：...
需要验证：...
```

## 5. Network Impact Vector

固定维度：

```text
[Latency, Jitter/IPDV, Bandwidth/Capacity, Reliability, Security, Operations, BER/Error, Scalability, Cost/Power]
```

评分：

| 符号 | 含义 |
|---|---|
| ++ | 显著改善，有实验或生产证据 |
| + | 有改善，但证据有限 |
| 0 | 无明显影响 |
| - | 有负面影响 |
| -- | 明显恶化 |
| ? | 证据不足 |

## 6. 评分体系

| 维度 | 权重 |
|---|---:|
| 问题重要性 | 15 |
| 核心创新 | 15 |
| 证据强度 | 20 |
| 工艺约束鲁棒性 | 20 |
| 网络指标净影响 | 15 |
| 可部署性 | 10 |
| 战略相关性 | 5 |

总分解释：

| 分数 | 结论 |
|---:|---|
| 85–100 | 高价值技术信号，建议进入 PoC |
| 70–84 | 重要跟踪对象，建议复现或小实验 |
| 55–69 | 有启发，但证据或约束不足 |
| 40–54 | 仅作为背景材料 |
| < 40 | 不建议投入 |

## 7. 质量闸门 hard rules

- 没有实验或真实数据，不允许给出强结论。
- 只报告平均值的论文，自动降级。
- 网络系统必须关注 p95/p99、故障和突发流量。
- 没有 baseline fairness 分析，自动降级。
- 没有工艺/实现约束说明，必须补做约束推断。
- 没有运维、安全、可靠性讨论，不能直接推荐生产部署。
- 涉及 jitter 时，优先写 IPDV 或 delay variation。
- 涉及 bandwidth 时，区分 capacity、available capacity、throughput、goodput。
- 涉及“较差工艺实现较优性能”时，必须说明成立条件。

## 8. 每篇文献最终输出顺序

1. 基本信息
2. 一句话结论
3. 问题背景
4. 核心思想
5. 创新点
6. 系统/协议/工艺机制
7. 工艺约束
8. 工艺约束依赖性分析
9. 较差工艺能否实现较优性能
10. 网络指标影响矩阵
11. 实验证据与可信度
12. 与已有技术对比
13. 隐含假设与风险
14. 安全与运维影响
15. 可复现性
16. 技术洞察
17. 战略意义
18. 评分
19. 建议动作
20. 后续验证实验

## 9. PoC analyzer 执行约束

第三轮 PoC analyzer 先采用 deterministic mock 实现，用于固定 schema、质量闸门和本地 CLI 管道：

```text
ingestion -> triage -> CNI analyzer -> schema validation -> quality gates -> JSON output
```

该阶段不联网、不调用真实模型、不读取 API key。所有导入正文继续视为 untrusted content。后续接入 OpenRouter 时，模型输出仍必须先通过 `literature_analysis` schema validation 和 CNI quality gates。

## 10. PoC constraint critic 执行约束

第四轮 PoC constraint critic 是 analyzer 之后的 deterministic review layer：

```text
ingestion -> triage -> CNI analyzer -> schema validation -> constraint critic -> critic schema validation -> JSON output
```

critic 复核工艺约束覆盖、约束依赖性、较差工艺反事实、Network Impact Vector、证据质量、部署风险和安全/运维/可靠性。它可以根据 hard rules 降级 `recommended_action` 和 `score.total_score`，并生成 follow-up experiments。critic 输出是后续 72h brief 的重要输入。

该阶段仍不联网、不调用真实模型、不读取 API key。后续接 OpenRouter 时，OpenClaw runtime 继续只允许 OpenRouter-configured models；Codex 仅用于开发期。

## 11. PoC 72h brief 执行约束

第五轮 PoC 72h brief synthesizer 是 analyzer + critic 之后的 deterministic cross-document synthesis layer：

```text
analyzer JSON + critic JSON -> brief synthesizer -> brief schema validation -> draft JSON output
```

brief 不得只是拼接单篇摘要。它必须综合 Executive Brief、Technology Signal Radar、Cross-document Conflict Analysis、Process Constraint Trends、Network Metric Trends、Evidence Quality Summary、Recommended Actions 和 Follow-up Experiments。若输入少于 2 篇，应标记 cross-document signal weak；若大多数输入被 critic 降级，或 vendor/marketing/no-experiment 材料占比高，不得给强结论。

brief 输出始终为 draft-only，并要求人工批准。该阶段仍不联网、不调用真实模型、不读取 API key。后续接 OpenRouter 时，OpenClaw runtime 继续 OpenRouter-only；Codex 仅用于开发期。

## 12. Quality-first brief 与预算路由约束

第六轮将 brief 升级为 `brief.v1.1-quality-first` decision brief。除原有 Executive Brief、Signal Radar、Conflict Analysis、Constraint Trends 和 Network Metric Trends 外，必须包含 input traceability、insight confidence、decision readiness、action rationale 和 budget context。

Budget router 是 OpenRouter adapter 前置层。本地只执行 deterministic dry-run routing、cost estimate 和 budget status，不调用模型、不联网、不读取真实 API key。quality-first 模式默认 350 USD/month，soft cap 450，hard cap 600；70/80/90/100/hard cap 分别对应 watch、reduce low-value volume、degrade or skip low-priority、stop nonessential、hard stop。

质量优先原则：A/B source tier 与 High deep-read priority 资料优先保留 preferred model；预算紧张时先减少 C/D 或 Low priority 资料处理量。Final review manual-only。OpenClaw runtime 继续 OpenRouter-only，Codex 仅用于开发期。

## 13. Pre-send review gate

Email draft 外发前必须经过 selective multi-role reviewer dry-run。该 reviewer 是 single orchestrator 下的 deterministic review panel，不是 autonomous multi-agent runtime，不调用模型、不联网、不发送邮件。

Review panel 至少覆盖 evidence skepticism、constraint integrity、delivery safety、executive readability、budget/runtime boundary。结论只能是 `ready_for_human_review`、`needs_revision` 或 `blocked`；不得自动批准发送。所有 external delivery 仍必须人工完成。
