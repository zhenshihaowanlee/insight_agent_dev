# Codex CLI 高权限开发 OpenClaw Agent 手册

## 1. 推荐启动命令

从仓库根目录启动：

```bash
codex \
  --sandbox workspace-write \
  --add-dir "$HOME/.openclaw" \
  --ask-for-approval on-request
```

这比全量 `danger-full-access` 更安全，同时能让 Codex 修改 OpenClaw 本地配置、workspace、skills 和 memory/soul harness。

如果你明确希望 Codex 拥有完整本地权限，请先进入隔离环境并备份：

```bash
cp -a "$HOME/.openclaw" "$HOME/.openclaw.backup.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
codex --sandbox danger-full-access --ask-for-approval on-request
```

## 2. 启动后给 Codex 的第一条指令

```text
请读取 .codex/prompts/04_high_privilege_openclaw_harness.md 并执行。
你可以修改本仓库和 ~/.openclaw 中的 OpenClaw 配置、workspace harness、skills、memory/soul 文件。
但 OpenClaw 运行期必须只使用 OpenRouter API，不得配置或调用 Codex、Codex CLI、Codex OAuth、@openai/codex 或任何 coding-agent provider。
先列出计划修改的文件和命令，等我确认后再执行真实安装。
```

## 3. 安装前检查

```bash
make test
python -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5
bash scripts/install_openclaw_harness.sh --dry-run
```

## 4. 安装到 OpenClaw

```bash
bash scripts/install_openclaw_harness.sh
openclaw doctor
```

## 5. 人工填写项

以下内容必须由你人工填写或确认，不应由 Codex 猜测：

- OpenRouter API key；
- 当前可用且价格合适的 OpenRouter explicit model ID；
- Telegram/Slack/Email channel token 与 allowlist；
- 预算告警邮箱或 webhook；
- 是否允许自动发送，初期建议保持 draft-only。
