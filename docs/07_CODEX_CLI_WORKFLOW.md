# Codex CLI 本地开发流程

本项目按 Codex CLI 本地开发设计。不要把 Codex CLI 当成生产运行时；它用于辅助开发、代码审查、测试修复和配置审阅。生产运行时仍由 Python 服务 + OpenClaw Gateway + 模型 API 承担。

## 1. 本地目录

建议：

```bash
unzip zyw_insight_openclaw_agent_codex_cli.zip
cd zyw_insight_openclaw_agent
python -m venv .venv
source .venv/bin/activate
pip install -e .
make test
```

从仓库根目录运行：

```bash
codex
```

Codex CLI 会读取仓库根目录的 `AGENTS.md`，并在项目被信任后读取 `.codex/config.toml`、`.codex/rules/` 和 `.agents/skills/`。

## 2. 推荐全局配置

将 `codex/user_config.example.toml` 中适合你的字段复制到：

```bash
~/.codex/config.toml
```

不要把真实认证信息、API key、公司代理配置写入仓库。

## 3. 推荐启动提示词

在 Codex CLI TUI 中粘贴：

```text
请读取 .codex/prompts/01_start_poc.md 并执行。先列出计划修改的文件，等我确认后再改动。
```

如果你希望它直接执行，也可以说：

```text
请读取 .codex/prompts/01_start_poc.md 并执行。允许修改仓库内文件，禁止改动 ~/.codex、~/.openclaw 和真实密钥。
```

## 4. 分阶段任务顺序

1. `codex/tasks/01_scaffold.md`：项目骨架与测试闭环。
2. `codex/tasks/02_ingestion.md`：资料输入、解析、元数据入库。
3. `codex/tasks/03_triage.md`：来源可信度、领域、深读级别。
4. `codex/tasks/04_cni_analysis_schema.md`：CNI 输出、schema 校验、质量闸门。
5. `codex/tasks/05_openclaw_integration.md`：实验版 OpenClaw workspace 和 skill 触发。
6. `codex/tasks/06_budget_and_guardrails.md`：预算控制、模型路由、降级策略。

## 5. Codex CLI 技能

本仓库提供两套技能目录：

- `.agents/skills/`：Codex CLI 自动发现使用。
- `skills/`：OpenClaw workspace 使用。

目前两者内容保持一致。修改其中一套后，要同步另一套。

在 Codex CLI 中可以输入 `/skills` 查看可用技能，或者在提示中显式提到：

```text
请使用 cni-literature-analysis skill 分析 examples/sample_article.md。
```

## 6. 安全与审批建议

本项目默认：

- `sandbox_mode = "workspace-write"`
- `approval_policy = "on-request"`
- `network_access = false`

也就是说，Codex 可以改当前仓库文件，但访问网络、修改仓库外配置、全局安装、OpenClaw provider onboarding 等操作应由你审批。

## 7. 每次让 Codex 工作时的最小检查清单

要求 Codex 每次输出：

1. 修改了哪些文件；
2. 为什么修改；
3. 运行了哪些测试；
4. 是否影响预算、schema、OpenClaw 配置或安全边界；
5. 下一步建议。

## 8. 不建议让 Codex CLI 做的事

- 直接写入生产 API key。
- 自动把模板配置覆盖到 `~/.openclaw/openclaw.json`。
- 自动发送邮件或消息。
- 在没有人工确认时触发 GPT-5.5 Pro 终审。
- 把 vendor claim 或 arXiv 未审稿资料升格为强结论。
