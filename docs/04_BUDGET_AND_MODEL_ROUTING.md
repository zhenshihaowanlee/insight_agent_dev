# 预算与模型路由

本文件采用用户提供的预算分析作为第一版工程口径。

## 1. 预算结论

| 阶段 | 月预算 |
|---|---:|
| PoC | 30–80 USD |
| 第一版正式系统 | 150–250 USD |
| Quality-first production | 350 USD，软上限 450，硬上限 600 |
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
| 达到 soft cap 70% | watch / warning |
| 达到 soft cap 80% | 优先减少低价值资料处理量，不立即牺牲高价值资料模型质量 |
| 达到 soft cap 90% | C/D 或 Low priority 资料降级或跳过；A/B + High priority 尽量保留 preferred model，并标记预算告警 |
| 达到 soft cap 100% | 停止非必要处理；仅允许人工触发少量高价值资料 |
| 达到 hard cap | hard stop，除非显式人工 override policy |
| 单篇过长 | 按章节分析，再合并 |
| retry 超过 1–2 次 | 标记失败，进入人工队列 |
| 高端模型请求 / final review | manual-only，需要人工触发和理由 |

## 8. Quality-first budget router

第六轮引入本地 deterministic budget router，作为 OpenRouter adapter 前置层。本轮只做 dry-run routing 和 cost estimate，不调用真实 API、不读取真实 API key。

预算配置位于 `configs/budget.*.json`。所有模型 ID 都必须是 `openrouter/` placeholder；provider policy 只允许 OpenRouter，并显式禁止 Codex、coding-agent、OAuth 和 `@openai/codex` 作为运行期 provider。

Quality-first 模式目标是提升技术洞察质量，而不是最低成本。默认预算为 350 USD/month，软上限 450，硬上限 600。策略是先减少低价值资料处理量，再考虑降低高价值资料模型质量。final review 始终 manual-only。

72h brief schema 升级为 quality-first decision brief，新增 traceability、confidence、decision_readiness、action_rationale 和 budget_context。外部交付仍保持 draft-only，需要人工批准。

## 9. OpenRouter adapter dry-run

第七轮引入 OpenRouter adapter dry-run contract。adapter 只生成 `model_request`、`model_response` 和 `adapter_run` JSON，不发真实网络请求、不读取真实 API key、不调用模型。

adapter 使用 quality-first budget router 的 routing decision：A/B + High priority 在预算 warning 下尽量保留 preferred model；C/D + Low priority 在预算 warning 下 fallback 或 denied；hard cap 后 denied，除非显式 manual override。Final review 继续 manual-only。

Ledger 只允许 redacted JSONL：记录 stage、source_id、model_id、budget environment、quality priority、token/cost estimate、budget status、processing_allowed、manual_required、quality_preserved、request_id 和 response_id。不得记录正文、messages 全文、API key、token、secret、authorization 或 env。

后续真实 OpenRouter canary 必须通过人工审批，并且继续满足 OpenRouter-only、draft-only、redacted ledger 和 runtime guard。

## 10. Manual OpenRouter canary

第八轮引入人工批准的单次 OpenRouter canary harness。默认仍是 dry-run，不读取 API key、不联网、不收费。

真实调用必须同时满足：

- 用户显式传入 `--real-call`。
- 用户显式传入 `--allow-network`。
- 用户显式传入 `--confirm-openrouter-charge`。
- 用户显式传入 `--max-cost-usd`，且估算成本不超过该值。
- 环境变量 `OPENROUTER_API_KEY` 存在。
- 用户提供 verified internal model id，格式为 `openrouter/<verified-model-slug>`。

内部模型 ID 保留 `openrouter/` 前缀用于 OpenRouter-only 边界检查；发送给 OpenRouter API 的 `model` 字段使用去掉前缀后的 slug。Final review 真实 canary 还必须 `--manual-override`。

Canary ledger 必须 redacted：不记录正文、messages 全文、API key、token、secret、authorization 或 env。不允许 cron、email、Webhook 或任何外部通知自动触发 real canary。

第十四轮固化了已完成的人工单次 real canary 回归要求：canary 成功结果只用于验证 OpenRouter 单次调用链路，不代表允许批量真实 pipeline。Canary response 中的 `content`、provider-specific `reasoning`、`reasoning_details` 和 messages 全文必须 redacted，只保留 hash、length、usage、cost、finish reason、response id 和 model。Ledger 只记录审计字段，不记录正文或模型输出全文；actual cost 缺失时审计使用 estimated cost fallback。

第十五轮新增 small real pipeline canary harness。它默认 dry-run，真实调用只能人工触发，最多 1–2 篇资料，默认只允许 `literature_analysis` stage 使用真实 OpenRouter canary。`brief_synthesis` 与 `final_review` 不允许真实调用；deterministic pipeline 仍是正式 draft artifact 的主产物，real stage canary 只作为 redacted validation artifact 和成本审计输入。

## 11. OpenClaw cron dry-run pipeline

第九轮引入 OpenClaw cron dry-run integration。cron 当前只能触发本地 `run-72h-dry-run` pipeline：ingestion、triage、deterministic analyzer、constraint critic、quality-first brief、budget router、adapter dry-run 和 redacted ledger。

cron 生成 draft-only 72h brief artifacts，包含 `brief.json`、`brief.md`、adapter dry-run JSON、run manifest 和 redacted ledger。`brief.md` 必须人工审核后才允许外发。

cron dry-run 不得执行真实 OpenRouter call，不得触发 real canary，不得读取 provider key，不得联网，不得发送邮件/Webhook。Final review 继续 manual-only，Codex 只用于开发期，OpenClaw runtime 继续 OpenRouter-only。

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
