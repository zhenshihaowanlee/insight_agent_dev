# Manual Full-paper Canary

Manual only. Do not run automatically.

This command requires `OPENROUTER_API_KEY` in the shell and explicit real-call flags. It is limited to one open-access, eligibility-approved A/B + High candidate. It must not retrieve paywalled PDFs, bypass paywalls, send email, use webhook delivery, run `final_review`, or use Codex runtime.

Boundary markers: no final_review, no email.

Dry-run first:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli full-paper-canary \
  --query-profile datacenter_networking \
  --provider arxiv \
  --max-candidates 20 \
  --internal-model-id openrouter/qwen/qwen3.5-397b-a17b \
  --environment quality_first \
  --spent-usd 50 \
  --max-cost-usd 5 \
  --pretty
```

Manual real-call form:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli full-paper-canary \
  --query-profile datacenter_networking \
  --provider arxiv \
  --max-candidates 20 \
  --internal-model-id openrouter/qwen/qwen3.5-397b-a17b \
  --environment quality_first \
  --spent-usd 50 \
  --max-cost-usd 5 \
  --real-call \
  --allow-network \
  --confirm-openrouter-charge \
  --pretty
```
