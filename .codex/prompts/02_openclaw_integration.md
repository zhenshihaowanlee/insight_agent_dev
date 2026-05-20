请阅读 AGENTS.md、openclaw/OPENCLAW_SETUP.md、codex/tasks/05_openclaw_integration.md。

目标：只实现实验版 OpenClaw 集成，不触碰生产配置。

请完成：
1. 检查 openclaw/openclaw.experimental.json5 是否仍是模板；
2. 生成一个本地运行说明，说明如何把本仓库作为 OpenClaw workspace；
3. 保证所有外部正文输入都标记为 untrusted content；
4. 保证 72h brief 只能生成 draft，不自动发送；
5. 运行 make test。

禁止：
- 不要自动执行 openclaw onboard；
- 不要把示例配置复制到 ~/.openclaw/openclaw.json；
- 不要请求或写入真实 token。
