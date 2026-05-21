# ZYW Insight 72h Dry-run Pipeline

Run the local CNI 72h pipeline in dry-run mode only.

Required behavior:

- Execute the local `zyw_insight` CLI command for `run-72h-dry-run`.
- Use local Markdown and text inputs only.
- Generate draft-only JSON and Markdown artifacts for human review.
- Route the brief synthesis stage through adapter dry-run and redacted ledger recording.
- Do not perform any paid model execution.
- Do not read provider credentials.
- Do not send external delivery.

Expected command shape:

```text
PYTHONPATH=src python3 -m zyw_insight.cli run-72h-dry-run examples/sample_inputs --environment quality_first --spent-usd 0 --window-hours 72 --trigger openclaw_cron_dry_run --pretty
```

The produced Markdown brief is a draft artifact and requires human approval before any external sharing.
