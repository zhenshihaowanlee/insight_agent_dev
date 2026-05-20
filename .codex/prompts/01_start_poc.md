请阅读 AGENTS.md、docs/01_DEVELOPMENT_PLAN.md、docs/03_CNI_METHOD_SPEC.md 和 codex/tasks/01_scaffold.md。

目标：完成 ZYW Insight Agent 的 PoC 本地开发闭环。

约束：
1. 不要改生产 OpenClaw 配置。
2. 不要写入真实 API key。
3. 先列出计划修改的文件。
4. 保持 schemas/ 的核心字段不变，除非发现 schema 与 CNI 方法论冲突。
5. 修改后运行 make test。
6. 输出 diff 摘要、测试结果、风险和下一步。

第一步任务：
- 校验 Python 包结构；
- 补全 ingestion 模块的最小接口；
- 新增或更新单元测试；
- 保证本地 CLI 能读取 examples/sample_article.md 并生成一个可被质量闸门检查的 stub 分析输出。
