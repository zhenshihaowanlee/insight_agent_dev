# Task 02 — Implement source ingestion

Goal: implement `zyw-insight ingest` for local Markdown/text files and URL metadata stubs.

Requirements:

- Input: `--url` or `--file`.
- Output: JSON conforming to `schemas/source_item.schema.json`.
- Compute a stable content hash when local content exists.
- Assign preliminary source type and domain.
- Do not fetch arbitrary web pages yet unless explicitly requested.

Acceptance:

- Tests cover local Markdown and URL-only item.
- No network needed for tests.
