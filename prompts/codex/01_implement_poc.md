# Codex Prompt 01 — 实现 PoC 闭环

请实现实验版 PoC 的最小闭环：

1. `ingest`：读取 URL/本地 Markdown/PDF 占位输入，生成 `SourceItem`。
2. `triage`：按规则给出 source_rank 和 deep_read_decision。
3. `analyze`：调用 LLM 前先保留 stub，输出符合 schema 的 JSON。
4. `quality-check`：运行 hard rules。
5. `brief`：聚合多个 analysis JSON 生成 Markdown 草稿。

要求：

- 不接入真实模型 API，先做可测试 stub。
- 不写真实密钥。
- 添加 tests。
- 运行 `make test`。
