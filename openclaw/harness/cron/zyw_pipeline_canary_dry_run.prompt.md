# ZYW Insight Pipeline Canary Dry-run Template

This template is for manual dry-run validation of the small pipeline canary harness.

Required behavior:

- Execute only the local `pipeline-canary` CLI in dry-run mode.
- Use at most one local Markdown or text source by default.
- Keep deterministic pipeline artifacts as the primary output.
- Treat stage canary output as redacted validation artifact only.
- Do not perform paid model execution.
- Do not read provider credentials.
- Do not send external delivery.

Expected command shape:

```text
PYTHONPATH=src python3 -m zyw_insight.cli pipeline-canary examples/sample_inputs/sample_paper.md --environment quality_first --spent-usd 50 --internal-model-id openrouter/example/model-slug --max-cost-usd 5 --pretty
```

The produced manifest is local and requires human review before any further action.
