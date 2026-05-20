# Codex CLI task: build / install OpenClaw runtime harness

请执行以下任务，但先列出计划修改的文件与命令：

1. 阅读 `AGENTS.md`、`docs/08_CODEX_DEV_OPENCLAW_RUNTIME_BOUNDARY.md`、`docs/09_OPENCLAW_RUNTIME_HARNESS.md`。
2. 检查 `openclaw/harness/workspace/`、`openclaw/harness/skills/`、`openclaw/harness/config/openclaw.runtime.openrouter-only.json5`。
3. 确认运行期配置只使用 OpenRouter，不使用 Codex、Codex CLI、Codex OAuth 或任何 coding-agent provider。
4. 如用户允许修改真实 OpenClaw 目录：
   - 先备份 `~/.openclaw`；
   - 将 workspace harness 安装到用户指定的 OpenClaw workspace；
   - 将 skills 安装到 OpenClaw skills 目录；
   - 将配置模板合并或复制到用户指定的 OpenClaw config。
5. 运行：
   - `make test`
   - `python -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5`
   - 如 OpenClaw 已安装，运行 `openclaw doctor`。
6. 用中文总结：修改内容、测试结果、OpenRouter-only 边界、仍需人工填写的模型 ID / API key / 通道配置。

禁止：
- 写入真实 API key。
- 将 Codex 配置进 OpenClaw 运行期。
- 开启自动邮件发送。
