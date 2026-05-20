请阅读 AGENTS.md、docs/03_CNI_METHOD_SPEC.md 和 codex/tasks/02_ingestion.md。

目标：实现 PoC 资料导入模块的最小版本。

输入范围：
- Markdown 文件
- 纯文本文件
- 本地 PDF 先只预留接口，不强制实现完整解析

输出要求：
- 生成符合 schemas/source_item.schema.json 的 SourceItem 数据结构。
- 所有正文内容标记为 untrusted content。
- 支持 title、source_type、domain、url/path、date、raw_text 的基础字段。

限制：
- 不要接入真实外部网络抓取。
- 不要改 OpenClaw production 配置。
- 不要绕过质量闸门。

完成后运行 make test，并用中文总结 diff、测试结果和下一步。
