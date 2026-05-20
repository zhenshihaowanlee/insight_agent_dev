# 预算与模型路由

本文件采用用户提供的预算分析作为第一版工程口径。

## 1. 预算结论

| 阶段 | 月预算 |
|---|---:|
| PoC | 30–80 USD |
| 第一版正式系统 | 150–250 USD |
| 严谨研究运行 | 250–400 USD |
| 旗舰终审场景 | 500–800 USD |

正式版建议：

- 推荐月预算：150–250 USD。
- 软上限：300 USD。
- 硬上限：400 USD。
- 默认处理量：每日 10–15 篇深度资料。
- 简报频率：每 72 小时一次。

## 2. Token 口径

| 档位 | 月 input tokens | 月 output tokens | 总 tokens | 说明 |
|---|---:|---:|---:|---|
| PoC | 8M | 1.8M | 9.8M | 验证可行性 |
| 基准高效 | 33M | 7M | 40M | 推荐生产起步 |
| 基准严谨 | 48M | 10.5M | 58.5M | 高质量研究分析 |
| 重度运行 | 105M | 20M | 125M | 长报告、标准、会议论文 |

计费公式：

```text
月度成本 = Σ(input_tokens × input_price + output_tokens × output_price) × 1.055
```

reasoning tokens 按 output tokens 计费，因此反事实分析、技术判断、critic 和终审环节会显著增加 output 侧成本。

## 3. 推荐模型路由

### 方案 B：均衡质量，正式版默认

| 阶段 | 模型层级 | 任务 | 成本控制 |
|---|---|---|---|
| 来源发现与初筛 | GPT-5.4 Nano 或同级 | 初筛、去重、资料分级 | 批处理、低 reasoning |
| 逐篇深度分析 | Gemini 2.5 Pro 或同级 | 长文本阅读、结构化文献分析 | 限制单篇 token，长文档章节化 |
| 约束与反事实 critic | Claude Sonnet 4.6 或同级 | 工艺约束、网络指标、风险复核 | 只对 High/Medium 资料深度复核 |
| 72h 洞察简报 | GPT-5.4 或同级 | 技术路线判断、简报生成 | 控制简报长度 |
| 重大终审 | GPT-5.5 / GPT-5.5 Pro | 关键文献复核、最终终审 | 手动触发，限频 |

预算目标：

- 基准高效版：约 134 USD/月。
- 基准严谨版：约 198 USD/月。

## 4. OpenClaw 模型配置建议

先使用 OpenClaw onboarding 配置 OpenRouter：

```bash
openclaw onboard --auth-choice openrouter-api-key
openclaw models status --probe
openclaw models list --provider openrouter
```

然后选择 explicit model IDs，不使用自动模型作为生产默认。

建议通过环境变量管理：

```bash
export ZYW_MODEL_DISCOVERY="openrouter/<verified-low-cost-model-id>"
export ZYW_MODEL_ANALYSIS="openrouter/<verified-long-context-model-id>"
export ZYW_MODEL_CRITIC="openrouter/<verified-reasoning-model-id>"
export ZYW_MODEL_BRIEF="openrouter/<verified-brief-model-id>"
export ZYW_MODEL_FINAL_REVIEW="openrouter/<verified-premium-model-id>"
```

## 5. 降级策略

| 触发条件 | 策略 |
|---|---|
| 达到预算 70% | 降低 reasoning，简化逐篇输出，critic 仅 High 资料 |
| 达到预算 90% | 停止 Medium/Low 深读，只处理 A 级来源与人工指定资料 |
| 达到预算 100% | 停止自动深度分析，只保留来源发现与人工触发 |
| 单篇过长 | 按章节分析，再合并 |
| retry 超过 1–2 次 | 标记失败，进入人工队列 |
| 高端模型请求 | 需要人工触发和理由 |

## 6. 成本监控字段

每次模型调用记录：

- timestamp
- task_type
- source_id / analysis_id / brief_id
- model_id
- input_tokens
- output_tokens
- reasoning_level
- estimated_cost_usd
- cache_hit_tokens
- retry_count
- quality_gate_status

## 7. Prompt caching

可缓存：

- system prompt。
- CNI schema。
- 术语表。
- 机构清单。
- 评分说明。

不可高估缓存收益：每日新增论文正文通常无法大量复用，因此主预算不计入缓存折扣。
