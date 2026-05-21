# ZYW Insight Local Draft Artifact

Create a local review artifact from the latest 72h dry-run brief.

Required behavior:

- Invoke the local `zyw_insight` CLI command for `email-draft`.
- Use a completed local dry-run pipeline directory as input.
- Produce local `.md`, `.eml`, manifest, and approval checklist files.
- Keep the artifact draft-only and require human approval before any external delivery.
- Do not use transport services or network actions.
- Do not read provider credentials.

Expected command shape:

```text
PYTHONPATH=src python3 -m zyw_insight.cli email-draft .zyw_insight/runs/<run-id>-72h-dry-run --pretty
```

The generated `.eml` file is only a local review artifact.
