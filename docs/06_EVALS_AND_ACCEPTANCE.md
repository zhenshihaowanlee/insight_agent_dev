# Evals 与验收标准

## 1. Golden Set

准备 20 篇样例资料：

| 类型 | 数量 |
|---|---:|
| 顶会论文 | 5 |
| RFC/标准 | 3 |
| 大厂工程博客 | 4 |
| 实验室报告 | 3 |
| 厂商白皮书 | 3 |
| 新闻/二手材料 | 2 |

每篇人工标注：

- 来源等级。
- 是否应深读。
- 关键约束。
- 网络指标影响。
- 证据质量。
- 建议动作。

## 2. 自动 eval

| Eval | 目标 |
|---|---|
| Schema validity | 输出符合 JSON Schema |
| Hard rule compliance | 不违反质量闸门 |
| Evidence discipline | 强结论必须有实验/真实数据 |
| Constraint coverage | 至少覆盖工艺/器件/芯片/网络/运维/安全中相关项 |
| Network metric coverage | Latency、IPDV、capacity/goodput、reliability、security、ops、BER |
| Cost bound | 单篇成本不超过配置阈值 |
| Prompt injection resistance | 外部文本无法覆盖系统规则 |

## 3. 人工 eval

评分 1–5：

- 是否抓住核心问题。
- 工艺约束是否具体。
- 反事实分析是否有价值。
- 网络指标是否严谨。
- 证据质量判断是否可靠。
- 建议动作是否可执行。
- 简报是否能用于技术决策。

## 4. 上线验收

实验版上线：

- 5 篇/天可跑通。
- 72h 简报可生成。
- schema 通过率 ≥ 95%。
- 强结论违规为 0。
- 月成本预测 < 80 USD。

正式版上线：

- 10–15 篇/天稳定运行 2 周。
- schema 通过率 ≥ 98%。
- 简报人工可用率 ≥ 80%。
- 成本处于 150–250 USD/月区间。
- 预算告警和降级机制有效。
- 所有正式发送均经过人工确认。
