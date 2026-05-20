# Codex CLI 本地开发运行手册

本手册面向 `ZYW Insight Agent` 的本地开发。仓库已经包含 `AGENTS.md`，Codex CLI 从仓库根目录启动时会读取它，并把其中的 CNI 方法论、预算约束、质量闸门和测试要求作为项目级开发指令。

## 1. 推荐目录位置

建议把项目放在一个独立目录，不要放在包含个人文件、密钥或无关仓库的大目录下。

```bash
mkdir -p ~/projects
cd ~/projects
unzip /path/to/zyw_insight_openclaw_agent.zip
cd zyw_insight_openclaw_agent
```

如果使用 Windows，建议优先使用 PowerShell 原生 Codex 或 WSL2。无论哪种方式，都只在项目根目录启动 Codex。

## 2. 安装与升级

```bash
npm i -g @openai/codex
codex --version
```

升级：

```bash
npm i -g @openai/codex@latest
```

第一次运行时，按照提示用 ChatGPT 账号或 API key 登录。

## 3. 推荐 Codex CLI 权限策略

实验开发建议使用 workspace-write + on-request：

```bash
codex --sandbox workspace-write --ask-for-approval on-request
```

含义：Codex 可以在当前工作区内读写和运行常规命令；涉及网络、越界写入或高风险操作时需要你批准。

只读审查模式：

```bash
codex --sandbox read-only --ask-for-approval never
```

适合让 Codex 审查代码、总结架构、找风险，但不允许它修改文件。

不要在真实机器上使用：

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

除非你已经在一次性虚拟机、容器或完全隔离环境中运行。

## 4. 项目级配置

仓库提供 `.codex/config.toml.example`。你可以复制为 `.codex/config.toml` 后按需调整：

```bash
cp .codex/config.toml.example .codex/config.toml
```

注意：项目级 `.codex/config.toml` 只会在你把该项目标记为可信后加载。若 Codex 没有读取项目配置，请先检查 `codex status`、当前目录和 trust 状态。

## 5. 启动后的第一条指令

在仓库根目录运行：

```bash
codex --sandbox workspace-write --ask-for-approval on-request
```

然后输入：

```text
请先阅读 AGENTS.md、README.md、docs/01_DEVELOPMENT_PLAN.md、docs/03_CNI_METHOD_SPEC.md 和 codex/tasks/01_scaffold.md。
不要修改 OpenClaw 生产配置，不要写入真实 API key。
请完成 PoC 第一阶段：校验项目结构、运行测试、指出最小可实现闭环还缺哪些模块。
```

## 6. 用 codex exec 执行单次任务

当你希望 Codex 执行一个明确任务并退出时，用 `codex exec`：

```bash
codex exec --sandbox workspace-write --ask-for-approval on-request \
  "Read AGENTS.md and codex/tasks/01_scaffold.md. Validate the repo, run make test, and only fix issues required to make tests pass."
```

也可以把 prompt 存在文件里：

```bash
cat codex/prompts/poc_scaffold.prompt.md | codex exec --sandbox workspace-write --ask-for-approval on-request -
```

## 7. 分阶段开发顺序

建议严格按以下顺序推进，不要一次性让 Codex 实现全系统：

1. `codex/tasks/01_scaffold.md`：校验项目、测试、CLI 基础。
2. `codex/tasks/02_ingestion.md`：资料导入，先支持 Markdown/文本，再支持 PDF/URL。
3. `codex/tasks/03_triage.md`：来源可信度、领域、是否深读。
4. `codex/tasks/04_cni_analysis_schema.md`：CNI JSON 输出与 schema 校验。
5. `codex/tasks/06_budget_and_guardrails.md`：预算估算、质量闸门、降级策略。
6. `codex/tasks/05_openclaw_integration.md`：OpenClaw skills、cron、provider 配置。

## 8. 每次让 Codex 修改代码时的约束模板

```text
请只修改与当前任务直接相关的文件。
先列出计划修改的文件，再执行。
不要改 schemas，除非任务明确要求。
不要改 OpenClaw production 配置。
不要新增生产依赖，除非先说明原因。
修改后运行 make test。
最后用中文总结：改了什么、测试结果、风险、下一步。
```

## 9. 本项目必须保持的质量闸门

CNI 分析不是普通摘要。任何单篇文献输出都必须覆盖：工艺/实现约束、约束依赖性、较差工艺反事实、Network Impact Vector、证据质量、隐含假设、安全运维影响、评分和建议动作。

必须阻断或降级的情况：

- 没有实验或真实数据，却给出强结论。
- 只报告 average latency，没有 p95/p99/worst-case。
- 没有 baseline fairness 分析。
- 没有工艺/实现约束说明。
- 没有运维、安全、可靠性讨论，却推荐生产部署。
- 提到 jitter 时不区分 IPDV / delay variation / inter-arrival variation。
- 提到 bandwidth 时混淆 capacity、available capacity、throughput、goodput。
- 声称“较差工艺实现较优性能”时没有成立条件。

## 10. 推荐日常命令

```bash
make test
python -m zyw_insight.cli budget --scenario baseline_efficient --model gpt-5.4-nano
python -m zyw_insight.cli quality-check examples/sample_outputs/literature_analysis.json
```

## 11. Git 工作流建议

```bash
git init
git add .
git commit -m "Initial ZYW Insight Agent scaffold"
git checkout -b poc/ingestion
```

每完成一个 task 让 Codex 输出 diff 总结，然后你人工 review：

```bash
git diff --stat
git diff
make test
```

确认无误后再提交。
