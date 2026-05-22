# Experiment Readiness

The workspace is prepared for the first OpenClaw Agent experiment only after local tests, runtime guard, Codex metadata validation, harness install, and `openclaw doctor` have passed or documented non-blocking warnings.

## Ready

- Real metadata discovery from arXiv, OpenAlex, Crossref, Semantic Scholar, and IETF.
- CNI triage/watchlist before materialization.
- A/B + High candidates become metadata-only untrusted stubs.
- C/D candidates stay signal-only/background-only.
- Deterministic 72h dry-run, adapter dry-run, email draft, and pre-send review.

## Dry-Run Only

- First experiment analysis is deterministic.
- Adapter is dry-run.
- Email is draft-only.
- No real OpenRouter model pipeline.

## Allowed

- Metadata discovery from approved providers.
- Local candidate stubs containing `UNTRUSTED METADATA ONLY` and `body_is_untrusted`.
- Local `brief.json`, `brief.md`, email draft, and pre-send review.

## Not Allowed

- Real OpenRouter calls in the first experiment.
- PDF retrieval, full-text retrieval, or paywall bypass.
- SMTP, sendmail, webhook, or external delivery.
- Codex or coding-agent providers in OpenClaw runtime.

## Before Experiment

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
make test
make runtime-guard
python3 scripts/validate_codex_metadata.py
PYTHONPATH=src python3 -m zyw_insight.cli runtime-guard "$HOME/.openclaw/openclaw.zyw-insight.openrouter-only.json5"
openclaw doctor
```

## First Experiment

DO NOT RUN AUTOMATICALLY.

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

Then generate draft-only review artifacts:

```bash
PYTHONPATH=src python3 -m zyw_insight.cli email-draft .zyw_insight/first_openclaw_experiment --pretty
DRAFT_DIR=$(ls -td .zyw_insight/email_drafts/*-draft | head -1)
PYTHONPATH=src python3 -m zyw_insight.cli pre-send-review "$DRAFT_DIR" --pretty
```

## Safety Gates

- Tests ok.
- Runtime guard ok.
- Codex metadata ok.
- OpenClaw doctor ok or warning documented.
- Provider allowlist ok.
- No real OpenRouter call unless manually approved.
- No email sending.
- Draft-only output.

## Future Real Model Review

Before any future real model pipeline, a human must confirm source access, A/B + High selection, budget cap, stage allowlist, redacted ledger, and CNI evidence quality for tails, baselines, process constraints, operations, security, and reliability.

## Manual Full-paper Canaries

Full-paper canaries are manual-only. They require open-access PDF eligibility, A/B + High candidate selection, strict byte/page/text limits, and redacted ledgers. They must not fetch arbitrary URLs, paywalled PDFs, use credentials, send email/webhooks, or run `final_review` / `brief_synthesis` real calls.
