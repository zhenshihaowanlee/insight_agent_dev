# OpenClaw Runtime Harness 设计

## 1. Harness 文件组成

OpenClaw 运行期 workspace 文件位于：

```text
openclaw/harness/workspace/
├── AGENTS.md
├── SOUL.md
├── IDENTITY.md
├── USER.md
├── MEMORY.md
├── TOOLS.md
├── HEARTBEAT.md
├── BOOTSTRAP.md
└── memory/2026-05-20.md
```

这些文件是运行期 agent 的身份、边界、长期记忆、工具规则和启动上下文。

## 2. OpenRouter-only 运行期原则

OpenClaw 运行期只允许使用 OpenRouter provider：

```text
openrouter/<verified-low-cost-model-id>
openrouter/<verified-long-context-model-id>
openrouter/<verified-reasoning-model-id>
openrouter/<verified-brief-model-id>
openrouter/<verified-premium-review-model-id>
```

模型 ID 必须在部署前用当前 OpenRouter 模型列表确认。不要把 Codex、ChatGPT subscription、OpenAI Codex OAuth 或本地 Codex CLI 配进运行期。

## 3. Skills

运行期 skills 位于：

```text
openclaw/harness/skills/
├── cni-source-triage/
├── cni-literature-analysis/
├── cni-constraint-critic/
└── cni-72h-brief/
```

职责分工：

- `cni-source-triage`：来源可信度、相关性、是否深读。
- `cni-literature-analysis`：逐篇 20 段 CNI 分析。
- `cni-constraint-critic`：工艺约束、反事实、Network Impact Vector、证据质量复核。
- `cni-72h-brief`：72h 跨文献趋势、矛盾点、技术信号雷达、建议动作。

PoC 本地输入层由仓库 Python 后端提供：

```bash
PYTHONPATH=src python3 -m zyw_insight.cli ingest <local-md-or-txt>
PYTHONPATH=src python3 -m zyw_insight.cli triage <local-md-or-txt-or-source-json>
PYTHONPATH=src python3 -m zyw_insight.cli analyze <local-md-or-txt> --pretty
PYTHONPATH=src python3 -m zyw_insight.cli critique <local-md-or-txt-or-analysis-json> --pretty
```

该输入层只读取本地文件；Markdown/TXT 正文一律标记为 `body_is_untrusted: true`。PDF 暂不抽取正文，只保留接口 TODO。triage 当前为 deterministic rule-based 初筛，不调用模型、不联网。

单篇 analyzer 当前也是 deterministic mock first：它生成符合 `schemas/literature_analysis.schema.json` 的 20 段 CNI JSON，输出前执行 schema validation，并接入 quality gates。OpenRouter adapter 当前只提供 `openrouter/...` placeholder 路由接口，不读取真实 API key、不调用网络。Codex 仍仅用于开发期，不得进入 OpenClaw runtime provider、skill action、cron 或 memory。

Constraint critic 当前也是 deterministic review layer：它读取 analyzer 输出，复核工艺约束、较差工艺反事实、Network Impact Vector、证据质量、部署风险和安全/运维/可靠性，并可降级 action/score。critic JSON 是后续 72h brief 的质量输入。后续才接 OpenRouter；运行期仍保持 OpenRouter-only，外部交付仍保持 draft-only。

72h brief synthesizer 当前也是 deterministic first：它读取 analyzer + critic JSON，生成跨文献 Executive Brief、Technology Signal Radar、Conflict Analysis、Process Constraint Trends、Network Metric Trends、Evidence Quality Summary、Recommended Actions 和 Follow-up Experiments。brief 不是单篇摘要拼接；大多数输入被降级或 vendor/marketing/no-experiment 占比高时不得给强结论。输出仍是 `draft_only` 且 `requires_human_approval: true`，后续才接 OpenRouter。

Brief schema 已升级为 quality-first decision brief：输出必须包含 traceability、confidence、decision_readiness、action_rationale 和 budget_context。Budget router 是 OpenRouter adapter 前置层；本地只做 deterministic dry-run routing 和 cost estimate，不调用真实模型。

Quality-first production 目标 350 USD/month，soft cap 450，hard cap 600。70/80/90/100/hard cap 分别为 watch / reduce volume / degrade low-priority / stop / hard stop。预算紧张时优先减少低价值资料处理量，而不是降低 A/B + High priority 资料分析质量。Final review manual-only；外部交付仍 draft-only。

OpenRouter adapter 当前只实现 dry-run：它固定 request/response/adapter_run contract，接入 budget router，并生成 redacted ledger event。它不得发真实网络请求、不得读取 API key、不得调用模型。Runtime guard 会检查 adapter schema 存在、dry_run const true、adapter 不包含启用的网络调用路径。后续真实 canary 必须人工批准。

Manual OpenRouter canary harness 当前只允许单次人工批准调用。默认 dry-run；真实调用必须同时提供 `--real-call`、`--allow-network`、`--confirm-openrouter-charge`、`--max-cost-usd`、verified `openrouter/<slug>`，并且运行环境中存在 `OPENROUTER_API_KEY`。API payload 的 `model` 使用去掉 `openrouter/` 前缀后的 slug。Canary 不允许 cron 自动触发，不允许外部发送，ledger 必须 redacted。Final review 继续 manual-only。

人工 real canary 已验证单次 OpenRouter 调用链路，但这不是批量真实 pipeline 授权。Canary 结果必须继续 redacted：不保留 response content、reasoning、reasoning_details、messages 全文、source body 或任何 key/secret；只保留 hash、length、usage、cost、finish reason 和审计字段。真实 canary ledger 不应提交到 git。

Small real pipeline canary harness 当前也是 manual-only：默认 dry-run，最多 1–2 篇资料，默认只允许 `literature_analysis` stage 做真实 canary。它会先生成 deterministic pipeline draft artifacts，再把真实 stage canary 作为 redacted validation artifact 附加保存；真实输出不得替换最终 brief。OpenClaw cron 模板只提供 dry-run 参考，不得自动触发真实 pipeline canary。

Source discovery runtime 入口已加入：OpenClaw 可通过 `cni-source-discovery` skill 和 discovery cron 模板触发真实 metadata discovery。Discovery 只访问 allowlist metadata providers，不读取 provider/model key，不调用 OpenRouter，不下载 PDF，不抓全文，不绕过 paywall，不发送邮件/Webhook。Discovery candidate 必须进入 CNI triage/watchlist，A/B + High 才能成为深读候选，C/D 只作 signal/background。

OpenClaw cron 当前只允许 dry-run pipeline。模板位于 `openclaw/harness/cron/`，目标是本地 CLI `run-72h-dry-run`，产出 draft-only 72h brief artifact。cron 不执行真实 OpenRouter call，不执行 real canary，不读取 provider key，不联网，不发送邮件或 Webhook；运行必须经过 budget router、adapter dry-run、runtime guard 和 redacted ledger。`brief.md` 需要人工审核后才允许外发。

Email draft workflow 当前也只生成本地草稿 artifact。`email-draft` 命令读取 pipeline run directory 或 brief 文件，生成 `email_draft.eml`、`email_draft.md`、`approval_checklist.md` 和 `email_draft_manifest.json`。它不发送邮件，不使用 SMTP/sendmail/Webhook，不联网，不读取 provider key。Human approval checklist 默认 pending；`brief.md` 和 `.eml` 外发前必须人工确认。

Pre-send review workflow 当前只生成本地 review artifact。`pre-send-review` 命令读取 email draft directory 或 manifest，由 deterministic review panel 检查 evidence、constraint、delivery safety、readability、budget/runtime boundary。它不是 autonomous multi-agent runtime，不调用模型、不联网、不发送。结果最多是 `ready_for_human_review`，不会自动批准外发。

## 4. Memory

`MEMORY.md` 只保存稳定事实：预算、CNI 方法论、运行期边界、人工审核要求。每日上下文写入 `memory/YYYY-MM-DD.md`。不要把 API key、token、cookie、内部账户信息写入 memory。

## 5. 安装方式

可先 dry-run：

```bash
bash scripts/install_openclaw_harness.sh --dry-run
```

确认后安装：

```bash
bash scripts/install_openclaw_harness.sh
```

安装脚本默认目标：

```text
~/.openclaw/workspace/zyw-insight/
~/.openclaw/skills/
~/.openclaw/openclaw.zyw-insight.openrouter-only.json5
```

正式上线前，请用 OpenClaw 自身 schema/doctor 校验真实配置。
