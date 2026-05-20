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
