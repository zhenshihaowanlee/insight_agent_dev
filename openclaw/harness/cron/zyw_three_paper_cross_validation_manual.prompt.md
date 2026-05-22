# Manual Three-paper Fulltext Cross-validation Canary

Manual only. Do not run automatically.

This command requires `OPENROUTER_API_KEY` in the shell and explicit real-call flags. It is limited to at most three open-access, eligibility-approved A/B + High candidates. It must not retrieve paywalled PDFs, bypass paywalls, send email, use webhook delivery, run `final_review`, run `brief_synthesis` as a real call, or use Codex runtime.

Boundary markers: no final_review, no email.

Dry-run first:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli three-paper-fulltext-canary \
  --query-profile datacenter_networking \
  --provider arxiv \
  --provider openalex \
  --max-candidates 30 \
  --max-papers 3 \
  --internal-model-id-analysis openrouter/qwen/qwen3.5-397b-a17b \
  --internal-model-id-critic openrouter/qwen/qwen3.5-397b-a17b \
  --internal-model-id-cross-validation openrouter/qwen/qwen3.5-397b-a17b \
  --environment quality_first \
  --spent-usd 50 \
  --max-cost-usd 20 \
  --pretty
```

Manual real-call form:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli three-paper-fulltext-canary \
  --query-profile datacenter_networking \
  --provider arxiv \
  --provider openalex \
  --max-candidates 30 \
  --max-papers 3 \
  --internal-model-id-analysis openrouter/qwen/qwen3.5-397b-a17b \
  --internal-model-id-critic openrouter/qwen/qwen3.5-397b-a17b \
  --internal-model-id-cross-validation openrouter/qwen/qwen3.5-397b-a17b \
  --environment quality_first \
  --spent-usd 50 \
  --max-cost-usd 20 \
  --real-call \
  --allow-network \
  --confirm-openrouter-charge \
  --pretty
```
