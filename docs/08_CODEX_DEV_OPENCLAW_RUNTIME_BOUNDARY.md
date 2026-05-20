# Codex CLI 开发期与 OpenClaw 运行期边界

## 1. 核心边界

本项目采用两层架构：

```text
开发期：Codex CLI
  - 高权限本地 coding agent
  - 修改仓库代码、OpenClaw config、skills、SOUL/MEMORY/AGENTS 等 harness 文件
  - 运行测试、生成配置、审查 diff

运行期：OpenClaw + OpenRouter
  - OpenClaw Gateway / Agent 负责接收触发、读取 workspace、调用 skills、生成简报草稿
  - 模型调用只走 OpenRouter API
  - 不调用 Codex CLI，不使用 Codex OAuth，不启动 coding-agent provider
```

因此，Codex CLI 可以“开发 OpenClaw agent”，但 OpenClaw agent 不可以“运行 Codex”。

## 2. 推荐本地启动方式

推荐优先使用 scoped high-permission，而不是完全取消 sandbox：

```bash
codex \
  --sandbox workspace-write \
  --add-dir "$HOME/.openclaw" \
  --ask-for-approval on-request
```

这会允许 Codex 修改当前仓库和 `~/.openclaw`，适合编写 OpenClaw config、skills、SOUL/MEMORY 等 harness 文件。

仅当你在专用 VM、容器或隔离开发用户中操作，并且已备份 `~/.openclaw`，才使用：

```bash
codex --sandbox danger-full-access --ask-for-approval on-request
```

## 3. Codex 可以做什么

Codex CLI 可以：

- 修改本仓库源代码、测试、schemas、prompts；
- 编写或更新 OpenClaw skills；
- 编写 `SOUL.md`、`MEMORY.md`、`USER.md`、`TOOLS.md`、`HEARTBEAT.md`、`BOOTSTRAP.md`；
- 生成 OpenClaw config 模板；
- 在用户确认后安装 harness 到 `~/.openclaw`；
- 运行测试、OpenClaw doctor、runtime guard。

## 4. Codex 不应该做什么

即使在高权限模式，Codex CLI 也不应：

- 把真实密钥写入仓库或 OpenClaw workspace；
- 把 Codex CLI 配置成 OpenClaw 运行期模型或 provider；
- 自动发送邮件、消息或外部通知；
- 删除 `~/.openclaw`、auth profile、session logs；
- 打印密钥、token、cookie 或私有聊天记录。

## 5. OpenClaw 运行期必须满足的检查

运行期配置必须通过：

```bash
python -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5
```

检查目标：

- 配置中至少有一个 `openrouter/` 模型引用；
- 运行期 config 不包含 Codex provider、Codex OAuth、Codex CLI command；
- 运行期 config 不包含真实 API key；
- 运行期 cron 不会自动绕过人工审核。
