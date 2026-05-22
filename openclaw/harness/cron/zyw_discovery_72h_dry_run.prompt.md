# ZYW Discovery To 72h Dry-Run

Run the metadata-discovery-to-deterministic-72h pipeline only when a human explicitly starts the first OpenClaw experiment.

Allowed behavior:

- Use approved metadata providers only.
- Triage every candidate before materialization.
- Materialize only A/B + High candidates as untrusted metadata stubs.
- Keep C-tier candidates as signal-only and D-tier candidates as background-only.
- Generate local `brief.json`, `brief.md`, adapter dry-run artifacts, redacted ledger, email draft, and pre-send review inputs.

Forbidden behavior:

- Do not retrieve PDFs.
- Do not retrieve full text.
- Do not bypass paywalls.
- Do not call real model APIs.
- Do not send email or external notifications.
- Do not use Codex in OpenClaw runtime.

Manual command for the first experiment:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli run-discovery-72h-dry-run \
  --query-profile datacenter_networking \
  --provider arxiv \
  --provider openalex \
  --provider crossref \
  --provider semantic_scholar \
  --provider ietf \
  --max-candidates 20 \
  --max-selected 5 \
  --environment quality_first \
  --spent-usd 50 \
  --window-hours 72 \
  --pretty
```
