请阅读 AGENTS.md、README.md、docs/01_DEVELOPMENT_PLAN.md、docs/03_CNI_METHOD_SPEC.md 和 codex/tasks/01_scaffold.md。

目标：完成 PoC 第一阶段的最小开发闭环。

限制：
- 不要修改 OpenClaw production 配置。
- 不要写入真实 API key。
- 不要改 schemas，除非发现 schema 与现有测试直接冲突。
- 不要新增生产依赖，除非先说明原因。

执行：
1. 校验 Python 包结构。
2. 运行 make test。
3. 如测试失败，只做最小修复。
4. 检查 CLI budget 和 quality-check 是否可运行。
5. 总结当前缺口，并提出下一步最小任务。
