# 开发计划：实验版本与正式上线版本

## 0. 产品定义

`ZYW Insight Agent` 是一个面向数据通信、材料/工艺、网络系统和产业技术资料的研究型 agent。它不只做摘要，而是按 CNI 方法论完成：来源可信度判断、三遍阅读、工艺约束建模、约束依赖性分析、反事实判断、网络指标影响分析、证据质量评估、技术洞察和 72 小时跨文献综合。

核心输出：

1. 单篇文献 CNI 深度分析。
2. 每 72 小时技术洞察简报。
3. 技术信号雷达、矛盾分析、工艺约束趋势和行动建议。
4. 可追踪的成本、质量和人工审核记录。

---

## 1. 实验版本 PoC

### 1.1 目标

验证系统能在低成本下完成端到端闭环：

- 每天 5 篇资料。
- 每 72 小时生成一次简报草稿。
- 输入来源先以手动 URL、PDF、Markdown、RSS 样例为主。
- 输出保存到本地 `outputs/`，并可通过 OpenClaw WebChat/Telegram 返回草稿。
- 邮件只生成 draft，不自动发送。
- 月预算控制在 30–80 USD。

### 1.2 范围

| 模块 | 实验版实现 |
|---|---|
| 来源发现 | 手动输入 + RSS allowlist |
| 文档抽取 | Markdown/网页文本/PDF 文本基础抽取 |
| 初筛 | 可信度等级、相关性、是否深读 |
| 单篇分析 | CNI 标准结构，允许部分字段为 unknown |
| critic | 规则化质量闸门 + 一次模型 critic |
| 简报 | 72h batch 聚合，输出草稿 |
| 存储 | SQLite + 文件归档 |
| 渠道 | OpenClaw WebChat/Telegram 或本地文件 |
| 人工审核 | 必须保留 |
| 预算 | 本地 token/cost 估算 + 手动账单核对 |

### 1.3 实验版里程碑

#### M0：开发环境与仓库初始化

交付：

- Codex 可读取的 `AGENTS.md`。
- Python 项目骨架。
- OpenClaw 实验配置模板。
- CNI schemas 与 prompts。
- `make test` 通过。

验收：Codex 能按任务单修改代码，且不触碰密钥或生产配置。

#### M1：资料输入与初筛

交付：

- `source_item` schema。
- URL/PDF/Markdown 输入适配器。
- 来源等级 A/B/C/D 初筛。
- 去重逻辑：URL、标题、hash。

验收：对 10 条样例资料输出筛选结果，并正确标注 High/Medium/Low 深读优先级。

#### M2：单篇 CNI 分析

交付：

- `literature_analysis` schema。
- `cni-literature-analysis` OpenClaw skill。
- prompts：快速分类、深度分析、约束分析、网络指标矩阵、评分。
- 输出包括 20 个最终总结字段。

验收：对 3 篇资料输出结构化 JSON 和 Markdown 报告；质量闸门能识别“无实验强结论”“只报告平均值”等问题。

#### M3：critic 与预算控制

交付：

- critic prompt。
- 规则质量闸门。
- token/cost 估算模块。
- 模型路由配置。

验收：对样例输出给出质量问题列表和推荐降级动作；估算成本与预算档位一致。

#### M4：72h 简报草稿

交付：

- `brief` schema。
- `cni-72h-brief` OpenClaw skill。
- 简报包含 Executive Brief、技术信号雷达、跨文献矛盾分析、工艺约束趋势、网络指标趋势、建议动作。

验收：用 5–15 篇样例分析生成一份可人工审核的简报草稿。

#### M5：OpenClaw 集成试运行

交付：

- OpenClaw cron 触发模板。
- WebChat 或 Telegram 输出。
- draft-only 发送策略。
- 运行日志和失败重试策略。

验收：OpenClaw 能按需触发分析和简报；任何自动发送前必须人工确认。

---

## 2. 正式上线版本 V1

### 2.1 目标

将 PoC 扩展为可稳定运行的第一版正式系统：

- 每日 10–15 篇深度资料。
- 每月约 450 篇资料。
- 每 72 小时自动生成技术洞察简报。
- 月预算 150–250 USD，软上限 300 USD，硬上限 400 USD。
- 支持可观测、可回滚、可审计、可人工确认。

### 2.2 正式版范围

| 模块 | 正式版实现 |
|---|---|
| 来源发现 | RSS、会议页、机构页、arXiv/ACM/USENIX/IETF allowlist、手动补充 |
| 文档抽取 | 网页/PDF/Markdown/HTML，长文档章节化 |
| 初筛 | 低价模型批处理，去重、来源等级、业务相关性 |
| 深度分析 | 每篇完整 CNI 分析 |
| critic | 工艺约束、反事实、证据质量、网络指标复核 |
| 简报 | 72h 跨文献综合 + 风险/矛盾分析 |
| 存储 | Postgres 或 SQLite+对象存储，保留 provenance |
| 搜索 | 关键词 + embedding 检索，可选向量库 |
| 渠道 | OpenClaw WebChat、Telegram/Slack、Email draft |
| 审核 | 人工审批后发送 |
| 监控 | 成本、token、失败率、质量闸门、重试次数 |

### 2.3 正式版多 agent 设计

| Agent | 职责 | 默认模型层级 | 工具权限 |
|---|---|---|---|
| `source-scout` | 来源发现、去重、初筛 | 低价模型 | web/RSS/read-only |
| `cni-analyzer` | 单篇深度分析 | 长文本模型 | read/write workspace |
| `constraint-critic` | 工艺约束、反事实、网络指标 critic | 强推理模型 | read/write outputs |
| `brief-synthesizer` | 72h 简报综合 | 综合判断模型 | read analyses, write briefs |
| `ops-guardian` | 预算、质量、安全闸门 | 低/中价模型 + rules | read logs, no send |

### 2.4 正式版模型路由

默认采用预算分析中的“方案 B：均衡质量”：

| 阶段 | 任务 | 模型层级 |
|---|---|---|
| 来源发现与初筛 | 初筛、去重、资料分级 | GPT-5.4 Nano 或同级低价模型 |
| 逐篇深度分析 | 长文本阅读、结构化文献分析 | Gemini 2.5 Pro 或同级长上下文模型 |
| 约束与反事实 critic | 工艺约束、网络指标、风险复核 | Claude Sonnet 4.6 或同级推理模型 |
| 72h 洞察简报 | 技术路线判断、简报生成 | GPT-5.4 或同级综合模型 |
| 重大终审 | 关键文献或管理层简报 | GPT-5.5 / GPT-5.5 Pro，手动触发 |

### 2.5 正式版质量指标

| 指标 | 目标 |
|---|---|
| schema 通过率 | ≥ 98% |
| 初筛误杀率 | 人工抽样 < 10% |
| 强结论证据违规 | 0 |
| 简报人工可用率 | ≥ 80% 初稿可直接编辑发送 |
| 成本 | 150–250 USD/月，软上限 300 USD |
| 单篇分析失败率 | < 5% |
| 重试次数 | 同任务最多 1–2 次 |
| 人工发送确认 | 100% |

### 2.6 上线前检查清单

- [ ] OpenClaw `openclaw doctor` 通过。
- [ ] OpenClaw `openclaw security audit --deep` 已执行。
- [ ] `dmPolicy` 不为 open，除非仅限测试环境。
- [ ] 群聊 require mention。
- [ ] Webhook 使用专用 token，且 query-string token 被禁用。
- [ ] 非 main session sandbox 已启用。
- [ ] 预算 70/90/100% 告警已配置。
- [ ] 邮件发送为 draft-only。
- [ ] 高端模型只允许手动触发。
- [ ] 所有 prompt injection 测试样例通过。
- [ ] 10 篇 golden set 分析通过人工验收。

---

## 3. 建议开发节奏

### 第 1 阶段：本地可跑

- 建仓库、schema、prompts、CLI、测试。
- 不急于接真实外部渠道。
- 目标是用样例文档跑出结构化分析。

### 第 2 阶段：OpenClaw PoC

- 配置一个 `zyw-insight` agent。
- 安装 `cni-literature-analysis` 和 `cni-72h-brief` skills。
- 用 WebChat 或 Telegram 手动触发。

### 第 3 阶段：半自动 72h 简报

- 配置 cron，但输出 draft。
- 每 72h 人工审核后发送。
- 统计 token/cost/质量问题。

### 第 4 阶段：正式运行

- 多 agent 拆分。
- 加入来源 allowlist、预算告警、失败重试。
- 扩展到 10–15 篇/天。

---

## 4. 不建议一开始做的事

- 不建议一开始做复杂 OpenClaw 插件。
- 不建议一开始自动发邮件到正式收件人。
- 不建议用 GPT-5.5 Pro 跑全流程。
- 不建议让 agent 自由浏览所有网站。
- 不建议把所有资料直接塞进一个超长 prompt；长文档应章节化。
- 不建议先做 UI，再做质量闸门。
