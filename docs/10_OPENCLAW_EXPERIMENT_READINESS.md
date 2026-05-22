# OpenClaw Experiment Readiness

Status: pre-experiment ready once final validation commands pass. Do not start the OpenClaw Agent experiment automatically.

## What Is Ready

- Real metadata discovery from arXiv, OpenAlex, Crossref, Semantic Scholar, and IETF.
- CNI discovery triage/watchlist before any candidate enters analysis.
- A/B + High candidates can be materialized as local metadata-only stubs.
- C candidates remain signal-only; D candidates remain background-only.
- Deterministic 72h dry-run pipeline produces `brief.json`, `brief.md`, adapter dry-run artifacts, and a redacted ledger.
- Email draft and pre-send review are draft-only local artifacts.
- Runtime guard checks OpenRouter-only model routing and blocks Codex runtime use.

## Still Dry-Run Only

- Literature analysis in the first OpenClaw experiment is deterministic local pipeline output.
- Adapter execution is dry-run only.
- Email is draft-only; no SMTP, sendmail, webhook, or delivery command is allowed.
- Real OpenRouter pipeline execution is not part of the first experiment.

## Allowed In The First OpenClaw Experiment

- Real metadata discovery from the approved provider allowlist.
- Discovery triage and watchlist generation.
- Metadata-only selected candidate stubs with `UNTRUSTED METADATA ONLY` and `body_is_untrusted`.
- Deterministic 72h dry-run pipeline.
- Adapter dry-run.
- Email draft generation.
- Pre-send review.

## Not Allowed In The First OpenClaw Experiment

- Real OpenRouter model calls.
- PDF retrieval.
- Full-text retrieval.
- Paywall bypass.
- Automatic email or webhook delivery.
- Codex, Codex CLI, Codex OAuth, `@openai/codex`, or coding-agent providers in OpenClaw runtime.
- Cron-triggered real model execution.

## Commands Before Experiment

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
make test
make runtime-guard
python3 scripts/validate_codex_metadata.py
PYTHONPATH=src python3 -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5
PYTHONPATH=src python3 -m zyw_insight.cli runtime-guard "$HOME/.openclaw/openclaw.zyw-insight.openrouter-only.json5"
openclaw doctor
```

If `openclaw doctor` is unavailable, document it as a non-blocking local tooling gap after runtime guard passes.

## First Experiment Command

DO NOT RUN AUTOMATICALLY. The user should manually start this after reviewing validation output:

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
  --output-dir .zyw_insight/first_openclaw_experiment \
  --pretty
```

Then draft and review only:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli email-draft .zyw_insight/first_openclaw_experiment --pretty
DRAFT_DIR=$(ls -td .zyw_insight/email_drafts/*-draft | head -1)
PYTHONPATH=src python3 -m zyw_insight.cli pre-send-review "$DRAFT_DIR" --pretty
```

## Safety Gates

- Tests ok.
- Runtime guard ok for repo and installed OpenClaw config.
- Codex metadata ok.
- OpenClaw doctor ok, or known non-blocking warning documented.
- Discovery provider allowlist ok.
- No OpenRouter real call unless manually approved outside the first experiment.
- No email sending.
- Draft-only output.

## Recommendation

Run the first OpenClaw experiment as real metadata discovery plus deterministic analysis pipeline only. Use adapter dry-run only, no real OpenRouter pipeline, no email send, and generate `brief.md`, email draft, and pre-send review for human review.

## Human Review Before Future Real Model Pipeline

- Confirm source tier and deep-read priority are A/B + High.
- Confirm full paper or standard review is legally accessible and manually approved.
- Confirm p95/p99/worst-case, baseline fairness, process constraints, operations, security, and reliability are present before strong conclusions.
- Confirm budget cap and real-call stage allowlist.
- Confirm ledger redaction and no message/body/content/reasoning storage.

## Full-paper Canary Phase

Manual full-paper canaries now have a separate open-access gate. They may only fetch PDFs from explicitly allowed open-access providers after eligibility approves an A/B + High candidate. They do not bypass paywalls, do not use credentials, do not fetch arbitrary URLs, and do not send delivery.

Commands are manual-only:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli full-paper-canary --query-profile datacenter_networking --provider arxiv --max-candidates 20 --internal-model-id openrouter/qwen/qwen3.5-397b-a17b --environment quality_first --spent-usd 50 --max-cost-usd 5 --pretty
PYTHONPATH=src python3 -m zyw_insight.cli three-paper-fulltext-canary --query-profile datacenter_networking --provider arxiv --provider openalex --max-candidates 30 --max-papers 3 --internal-model-id-analysis openrouter/qwen/qwen3.5-397b-a17b --internal-model-id-critic openrouter/qwen/qwen3.5-397b-a17b --internal-model-id-cross-validation openrouter/qwen/qwen3.5-397b-a17b --environment quality_first --spent-usd 50 --max-cost-usd 20 --pretty
```

Any real-call version requires explicit `--real-call --allow-network --confirm-openrouter-charge`, available OpenRouter model verification, and redacted ledger checks. `final_review` and `brief_synthesis` real calls remain forbidden.
