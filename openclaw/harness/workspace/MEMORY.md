# MEMORY.md — Durable runtime memory

## Stable decisions

- The agent uses CNI: Constraint-aware Network Insight.
- The agent analyzes technical specifications, academic conference papers, lab reports, institutional updates, and industry technical materials.
- The first official system budget is 150–250 USD/month, with a 300 USD/month soft cap and a 400 USD/month hard cap.
- Quality-first mode targets 350 USD/month, with a 450 USD soft cap and a 600 USD hard cap.
- Budget states are 70% watch, 80% reduce low-value volume, 90% degrade or skip low-priority sources, 100% stop nonessential processing, and hard cap hard stop.
- In quality-first mode, preserve analysis quality for A/B tier and High priority sources before reducing model quality; reduce low-value volume first.
- Default production cadence is one technical insight brief every 72 hours.
- Default production throughput is 10–15 deep materials/day.
- Runtime model provider is OpenRouter only.
- Codex CLI is allowed only as a development assistant, not as an OpenClaw runtime dependency.
- External messages are draft-first and require human confirmation during early operation.
- Final review is manual-only.
- 72h briefs use the quality-first decision schema with traceability, confidence, decision readiness, action rationale, and budget context.
- OpenRouter adapter currently runs in dry-run mode only. It establishes request/response contracts, uses budget router decisions, and writes only redacted ledger events.
- Real OpenRouter canary calls require explicit manual approval. Adapter ledger must not record full source bodies, messages, API keys, tokens, secrets, authorization headers, or environment dumps.
- Manual OpenRouter canary is single-call only and defaults to dry-run. A real canary requires --real-call, --allow-network, --confirm-openrouter-charge, --max-cost-usd, a verified openrouter/<slug>, and OPENROUTER_API_KEY in the environment.
- Canary API payload model slug removes the internal openrouter/ prefix. Canary ledger remains redacted and final_review remains manual-only.
- OpenClaw cron currently runs only the local 72h dry-run pipeline. It produces draft-only brief artifacts, passes through budget routing, adapter dry-run, runtime guard, and redacted ledger, and must not trigger real canary, network calls, provider-key reads, email, or external notification.
- Email draft workflow only creates local draft artifacts: email_draft.eml, email_draft.md, email_draft_manifest.json, and approval_checklist.md. It does not send email, does not use SMTP/sendmail/Webhook, does not read provider keys, and keeps human approval pending by default.
- Pre-send review is a deterministic single-orchestrator review panel, not autonomous multi-agent runtime. It reviews evidence, constraints, delivery safety, readability, and budget/runtime boundary. Its strongest outcome is ready_for_human_review; external delivery remains manual.
- Source discovery may perform real metadata-only network access to the approved providers arXiv, OpenAlex, Crossref, Semantic Scholar, and IETF. Discovery does not call OpenRouter, read provider keys, download PDFs, fetch full text, bypass paywalls, or send delivery. Candidates must pass CNI triage; A/B + High may enter deep-read candidates, C is signal-only, and D is background-only.

## CNI scoring weights

- Problem importance: 15
- Core innovation: 15
- Evidence strength: 20
- Process-constraint robustness: 20
- Network metric net impact: 15
- Deployability: 10
- Strategic relevance: 5

## Network Impact Vector

[Latency, Jitter/IPDV, Bandwidth/Capacity, Reliability, Security, Operations, BER/Error, Scalability, Cost/Power]
