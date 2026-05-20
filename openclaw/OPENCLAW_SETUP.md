# OpenClaw 设置说明

## 1. 安装

```bash
npm install -g openclaw@latest
openclaw onboard --auth-choice openrouter-api-key
openclaw dashboard
```

## 2. 使用 OpenRouter

推荐先走 onboard，而不是手写全部配置：

```bash
export OPENROUTER_API_KEY="sk-or-..."
openclaw onboard --auth-choice openrouter-api-key
openclaw models status --probe
openclaw models list --provider openrouter
```

生产环境必须改用 explicit model ID。不要长期使用 `openrouter/auto`。

## 3. 配置实验 workspace

```bash
mkdir -p ~/.openclaw/workspace-zyw-insight
cp -R skills ~/.openclaw/workspace-zyw-insight/
cp AGENTS.md ~/.openclaw/workspace-zyw-insight/AGENTS.md
```

把 OpenClaw agent workspace 指向 `~/.openclaw/workspace-zyw-insight`。

## 4. 验证配置

```bash
openclaw config schema > /tmp/openclaw.schema.json
openclaw doctor
openclaw security audit
openclaw agents list --bindings
openclaw channels status --probe
```

## 5. Cron 建议

实验版先不要自动发送，只触发简报草稿：

```bash
openclaw cron add \
  --name "ZYW 72h Insight Brief Draft" \
  --cron "0 8 */3 * *" \
  --tz "Europe/Berlin" \
  --session isolated \
  --system-event-file "openclaw/cron/72h_brief.prompt.md"
```

## 6. 安全提醒

- `dmPolicy` 不要设为 `open`。
- 群聊必须 require mention。
- Webhook token 使用专用值。
- 邮件只生成 draft。
- 非 main session 使用 sandbox。
