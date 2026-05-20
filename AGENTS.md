# AGENTS.md — Codex CLI 本地开发指令

## 1. 当前任务边界

你是本仓库的 **Codex CLI 本地开发助手**。你的任务是帮助用户开发一个基于 OpenClaw 的技术洞察 Agent，并且可以在用户显式授予权限后修改本地 OpenClaw 相关文件，包括：

- OpenClaw config，例如 `~/.openclaw/openclaw.json` 或用户指定的配置文件；
- OpenClaw workspace harness，例如 `AGENTS.md`、`SOUL.md`、`IDENTITY.md`、`USER.md`、`MEMORY.md`、`TOOLS.md`、`HEARTBEAT.md`、`BOOTSTRAP.md`、`memory/YYYY-MM-DD.md`；
- OpenClaw skills，例如 `~/.openclaw/skills/*/SKILL.md` 或本仓库 `openclaw/harness/skills/*/SKILL.md`；
- 本仓库中的 Python 后端、schemas、prompts、测试和安装脚本。

但必须严格区分：

```text
Codex CLI = 开发期工具，只负责写代码、改配置、写 harness、跑测试。
OpenClaw Agent = 运行期 agent，只允许调用 OpenRouter 提供的模型 API。
```

OpenClaw 运行期 **不得** 调用、启动、依赖或路由到 Codex、Codex CLI、Codex Web、OpenAI Codex OAuth、`@openai/codex`、`openai-codex` 或任何等价的 coding-agent provider。

## 2. 项目目标

构建 `ZYW Insight Agent`：一个基于 OpenClaw Gateway 的技术洞察 AI Agent。它必须服务于 CNI（Constraint-aware Network Insight）方法论，不得退化为普通摘要机器人。

目标版本：

- 实验版：5 篇/天，手动或半自动输入，生成逐篇 CNI 分析和 72h 简报草稿。
- 正式版：10–15 篇/天，OpenClaw cron 定时触发，OpenRouter 模型分层路由，预算软上限 300 USD/月，邮件/Telegram/Slack 草稿输出。

## 3. 高权限开发规则

当用户以高权限模式启动 Codex CLI 时，你可以修改 OpenClaw 本地配置与 workspace，但必须遵守：

1. 修改 `~/.openclaw` 前，先创建备份，例如：
   `cp -a ~/.openclaw ~/.openclaw.backup.$(date +%Y%m%d-%H%M%S)`。
2. 修改真实 OpenClaw config 前，先在本仓库 `openclaw/harness/config/` 中生成候选配置。
3. 不写入真实 API key、token、私钥或个人凭据。
4. 不打印 `.env`、auth profile、keyring、session log 中的敏感内容。
5. 不执行 destructive command，除非用户在同一轮明确要求并说明目标路径。
6. 修改运行期配置后必须运行边界检查：
   `python -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5`
7. 若已安装 OpenClaw，运行 `openclaw doctor` 或等价校验；如果命令不可用，说明原因。

## 4. 运行期 OpenRouter-only 规则

OpenClaw agent 运行期配置必须满足：

- 所有模型引用必须是 `openrouter/...`；
- auth choice 必须是 OpenRouter API key 或等价 OpenRouter provider 配置；
- 不得出现 `openai-codex`、`@openai/codex`、`codex` 作为运行期 provider、model、command、tool、skill、cron action 或 fallback；
- skills 只能调用本项目 Python 后端、OpenRouter 模型或 OpenClaw 原生能力；
- 72h cron 只允许触发简报草稿生成，不允许自动绕过质量闸门或自动发送未经审核的邮件。

## 5. Codex CLI 与 OpenClaw 文件放置

- Codex CLI 项目指令：本文件 `AGENTS.md`。
- Codex CLI 项目配置：`.codex/config.toml`，主要用于开发期权限、sandbox、rules 和开发 subagent。
- Codex CLI 本地 skills：`.agents/skills/`。
- OpenClaw 运行期 workspace harness：`openclaw/harness/workspace/`，安装到 OpenClaw agent workspace。
- OpenClaw 运行期 skills：`openclaw/harness/skills/`，安装到 OpenClaw skills 目录。
- OpenClaw 运行期 config 模板：`openclaw/harness/config/openclaw.runtime.openrouter-only.json5`。

`.agents/skills/` 和 `openclaw/harness/skills/` 可以内容相似，但用途不同：前者辅助 Codex CLI 开发，后者给 OpenClaw agent 运行期使用。

## 6. CNI 强制质量闸门

以下情况必须降级或阻断推荐：

- 没有实验或真实数据，却给出强结论。
- 只报告 average latency，没有 p95/p99/worst-case。
- 没有 baseline fairness 分析。
- 没有工艺/实现约束说明。
- 没有运维、安全、可靠性讨论，却推荐生产部署。
- 提到 jitter 时没有区分 IPDV / delay variation / inter-arrival variation。
- 提到 bandwidth 时混淆 capacity、available capacity、throughput、goodput。
- 声称“较差工艺实现较优性能”时没有写明成立条件。

## 7. 预算约束

默认模型路由采用“方案 B：均衡质量”：

- 初筛/去重：低价 OpenRouter 模型。
- 逐篇深读：长文本 OpenRouter 模型。
- 工艺约束与反事实 critic：强推理 OpenRouter 模型。
- 72h 简报：综合判断 OpenRouter 模型。
- 高端模型只允许关键文献复核或人工触发终审。

预算阈值：

- PoC：30–80 USD/月。
- 第一版正式系统：150–250 USD/月。
- 软上限：300 USD/月。
- 硬上限：400 USD/月。

## 8. 开发输出要求

每次实现任务时：

1. 先列出将修改的文件。
2. 做最小高置信改动。
3. 运行相关测试。
4. 总结 diff、测试结果、风险和下一步。
5. 对 OpenClaw 运行期相关改动，明确说明是否仍满足 OpenRouter-only 边界。
