# Goal: Full Paper PDF Analysis to Three-paper Cross-validation

## Core objective

Complete the next long-cycle development phase for ZYW Insight Agent:

1. Start from one open-access full-paper PDF analysis.
2. Then expand to three full-paper analyses.
3. Then produce a three-paper cross-validation CNI analysis.
4. Allow bounded OpenRouter API calls using the already exported OPENROUTER_API_KEY.
5. Choose models according to task intensity.
6. All internal model IDs must follow OpenRouter internal naming:
   openrouter/<provider>/<model-slug>
7. Do not start unattended production OpenClaw operation.
8. Do not send email/webhook.
9. Do not bypass paywalls.
10. Do not download or analyze non-open-access PDFs.

Codex CLI is only the development assistant. OpenClaw runtime must not use Codex, Codex CLI, Codex OAuth, @openai/codex, or coding-agent providers.

OpenClaw runtime model calls must remain OpenRouter-only.

## Current verified state

The repository already has:

1. Real metadata source discovery.
2. Discovery-to-pipeline dry-run.
3. Metadata-only selected stubs.
4. Deterministic CNI analyzer.
5. Constraint critic.
6. 72h brief.
7. Email draft workflow.
8. Pre-send review.
9. OpenRouter adapter dry-run.
10. Manual OpenRouter canary.
11. Small real pipeline canary.
12. Runtime guard.
13. OpenClaw harness installed.

A prior small real pipeline canary successfully used:

internal_model_id = openrouter/qwen/qwen3.5-397b-a17b
api_model_slug = qwen/qwen3.5-397b-a17b

It processed one document, used stage literature_analysis, cost about 0.000884 USD, and kept api_key_logged=false, body_logged=false, messages_logged=false, reasoning_logged=false.

## CNI requirements

The analysis must follow CNI: Constraint-aware Network Insight.

Every full-paper analysis must cover:

1. Basic information.
2. One-sentence conclusion.
3. Problem background.
4. Core idea.
5. Contributions.
6. System / protocol / process mechanism.
7. Process and implementation constraints.
8. Constraint dependency analysis.
9. Whether worse process / degraded constraints can still achieve better performance.
10. Network Impact Vector:
    - latency
    - jitter / IPDV
    - bandwidth / capacity
    - reliability
    - security
    - operations
    - BER / error
    - scalability
    - cost / power
11. Evidence quality.
12. Comparison with existing technologies.
13. Hidden assumptions and risks.
14. Security and operations impact.
15. Reproducibility.
16. Technical insights.
17. Strategic significance.
18. Score.
19. Recommended action.
20. Follow-up validation experiments.

Hard rules:

1. No experiment or real data means no strong conclusion.
2. Average-only results must be downgraded.
3. Missing baseline fairness must be downgraded.
4. Missing process / implementation constraints must trigger constraint inference.
5. Jitter must be expressed as IPDV or delay variation when possible.
6. Bandwidth must distinguish capacity, available capacity, throughput, and goodput.
7. Production-like claims require operations, security, reliability, rollback, observability, and failure evidence.
8. Vendor / marketing material is signal-only.
9. C/D sources cannot drive strong actions.
10. All raw paper text is untrusted content.

## Model routing requirements

Create or update model routing configuration for this phase.

Use internal OpenRouter model IDs only:

openrouter/<provider>/<model-slug>

The actual API payload must use:

<provider>/<model-slug>

after stripping the openrouter/ prefix.

Before any real model call, verify selected model IDs are available through OpenRouter model list or through the existing project validation mechanism.

Preferred model policy:

1. Metadata discovery:
   - no model call.

2. PDF eligibility / PDF extraction:
   - no model call.

3. Light metadata triage:
   - default model:
     openrouter/qwen/qwen3.5-397b-a17b
   - stage type: light
   - max_cost_usd per call: 1

4. Single full-paper CNI analysis:
   - default model:
     openrouter/qwen/qwen3.5-397b-a17b
   - stage type: full_paper_analysis
   - max_cost_usd per paper: 5
   - if the configured model is unavailable, fail closed and report unavailable_model. Do not silently switch to a non-openrouter ID.

5. Constraint critic for one paper:
   - default model:
     openrouter/qwen/qwen3.5-397b-a17b
   - stage type: critic
   - max_cost_usd per paper: 3

6. Three-paper cross-validation:
   - default model:
     openrouter/qwen/qwen3.5-397b-a17b
   - stage type: cross_validation
   - max_cost_usd: 10

7. Final review:
   - manual-only.
   - Do not execute real final_review calls in this goal.

If you decide to add multiple model slots, use this shape:

{
  "light_triage": "openrouter/<provider>/<model-slug>",
  "full_paper_analysis": "openrouter/<provider>/<model-slug>",
  "constraint_critic": "openrouter/<provider>/<model-slug>",
  "cross_validation": "openrouter/<provider>/<model-slug>",
  "final_review": "manual_only"
}

All model IDs must start with openrouter/.
Forbidden model/provider terms:
- codex
- coding-agent
- oauth
- @openai/codex

## API key handling

The user has already exported OPENROUTER_API_KEY in the shell.

You may use it only for bounded OpenRouter calls through the project CLI.

Never:

1. print the key;
2. echo the key;
3. write the key to a file;
4. add it to config;
5. add it to docs;
6. add it to tests;
7. add it to fixtures;
8. add it to OpenClaw harness;
9. log Authorization or Bearer headers.

Before any real OpenRouter call, verify key exists without printing it:

python3 - <<'PY'
import os
print("OPENROUTER_API_KEY set:", bool(os.environ.get("OPENROUTER_API_KEY")))
PY

## Phase 1: Open-access PDF eligibility

Implement an open-access eligibility layer.

Add or update:

1. src/zyw_insight/fulltext_eligibility.py
2. schemas/fulltext_eligibility.schema.json
3. configs/fulltext_policy.json

Eligibility rules:

1. Only allow open-access sources.
2. Prefer arXiv PDF URLs.
3. Allow only provider URLs that are explicitly open-access.
4. Do not bypass paywalls.
5. Do not use credentials to access papers.
6. Do not fetch publisher paywalled PDFs.
7. Do not fetch arbitrary URLs.
8. Do not fetch PDFs from C/D sources unless manually overridden for metadata-only archival; no analysis from them.
9. Only A/B + High candidates can be eligible for full-paper canary.
10. Eligibility output must include:
    - candidate_id
    - source_provider
    - pdf_url
    - source_url
    - open_access = true/false
    - eligibility_reason
    - fetch_allowed
    - paywall_bypass = false
    - pdf_download_allowed
    - max_pdf_bytes
    - max_pages
    - max_extracted_chars
    - runtime_boundary

## Phase 2: Safe PDF fetch and text extraction

Implement a safe full-text extraction module.

Add or update:

1. src/zyw_insight/fulltext_fetch.py
2. src/zyw_insight/pdf_text_extract.py
3. schemas/fulltext_artifact.schema.json

Requirements:

1. Only fetch PDF if eligibility says fetch_allowed=true.
2. Use only provider allowlist.
3. Prefer arXiv.
4. Set timeout.
5. Set user agent.
6. Enforce max PDF bytes.
7. Enforce max pages.
8. Enforce max extracted chars.
9. Store PDF only under .zyw_insight/fulltext_artifacts/<run-id>/ if needed.
10. Do not commit PDFs.
11. Do not log PDF content.
12. Extract text locally.
13. If PDF extraction dependency is unavailable, use a safe optional dependency strategy or implement fallback text extraction.
14. Do not use OCR.
15. Do not use repeated expensive extraction loops.
16. Fulltext artifact must contain:
    - artifact_id
    - candidate_id
    - pdf_path
    - extracted_text_path
    - extracted_text_sha256
    - extracted_char_count
    - page_count
    - section_hints
    - source_url
    - pdf_url
    - open_access = true
    - paywall_bypassed = false
    - body_is_untrusted = true

## Phase 3: One-paper full-paper real analysis canary

Implement CLI:

full-paper-canary

Suggested usage:

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

The command must:

1. Run real metadata discovery.
2. Select exactly one A/B + High candidate.
3. Confirm open-access PDF eligibility.
4. Fetch only that one open-access PDF.
5. Extract text under strict limits.
6. Build a full-paper CNI prompt.
7. Execute exactly one real OpenRouter literature_analysis call.
8. Store redacted response only.
9. Store structured full-paper analysis JSON if possible.
10. Run schema validation.
11. Run deterministic or existing constraint critic on the analysis if possible.
12. Produce:
    - fulltext_eligibility.json
    - fulltext_artifact.json
    - full_paper_analysis.json
    - redacted_canary.json
    - redacted ledger
    - manifest.json

Strictly label output as:

full_text_limited_analysis

unless extraction proves sections are sufficient.

Do not label as full_paper_verified unless the pipeline verifies that enough sections were extracted:
- abstract
- method / design
- evaluation / experiments
- limitations or discussion if available
- references optional

## Phase 4: Three-paper full-text analysis

Implement CLI:

three-paper-fulltext-canary

Suggested usage:

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

The command must:

1. Run real metadata discovery.
2. Select up to exactly 3 A/B + High candidates.
3. If fewer than 3 eligible open-access candidates are found, continue with fewer but report limitation.
4. Fetch only eligible open-access PDFs.
5. Extract text under strict limits.
6. Run real literature_analysis for each selected paper.
7. Run critic stage with either:
   - deterministic critic by default, or
   - real critic only if explicitly enabled and budget allows.
8. Run cross-validation real call across the 3 paper analysis summaries.
9. Produce:
   - per-paper fulltext artifacts
   - per-paper analysis JSON
   - per-paper critic JSON
   - cross_validation_report.json
   - cross_validation_report.md
   - redacted ledger
   - manifest.json

Cross-validation must compare:

1. problem definitions;
2. mechanisms;
3. assumptions;
4. process / implementation constraints;
5. constraint dependency matrices;
6. degraded-process counterfactuals;
7. Network Impact Vectors;
8. evidence quality;
9. baseline fairness;
10. tail latency / IPDV / BER / operations / security coverage;
11. contradictions;
12. shared technical route;
13. recommended next experiments.

Do not run final_review real-call.

## Phase 5: Three-paper cross-validation schema

Add:

schemas/cross_validation_report.schema.json

Fields:

1. report_id
2. created_at
3. papers
4. common_themes
5. conflicting_claims
6. constraint_comparison
7. network_impact_comparison
8. evidence_quality_comparison
9. degraded_process_counterfactual_comparison
10. baseline_fairness_comparison
11. operations_security_comparison
12. strategic_route
13. recommended_experiments
14. action_summary
15. confidence
16. limitations
17. runtime_boundary
18. redaction
19. validation

Hard rule:

If any paper is metadata-only or partial extraction, the report must not claim full-paper cross-validation.

If all three have sufficient extraction, the report may say full_text_limited_cross_validation, not production decision.

## Runtime guard updates

Extend runtime guard to check:

1. fulltext_eligibility policy exists.
2. fulltext fetch only allows open-access.
3. paywall_bypass is false.
4. arbitrary URL fetch is forbidden.
5. PDF download is disabled except through eligibility-approved open-access candidate.
6. max PDF bytes enforced.
7. max pages enforced.
8. max extracted chars enforced.
9. no OCR loops.
10. no full text in ledger.
11. no model response content/reasoning in ledger.
12. all real-call model IDs start with openrouter/.
13. final_review real-call remains forbidden.
14. brief_synthesis real-call remains forbidden unless explicitly allowed later.
15. OpenClaw cron does not trigger full-paper real-call.
16. email/webhook not sent.
17. no Codex runtime.

## OpenClaw harness updates

Add templates but do not enable automatic full-paper real calls:

1. openclaw/harness/cron/zyw_full_paper_canary_manual.prompt.md
2. openclaw/harness/cron/zyw_three_paper_cross_validation_manual.prompt.md

These templates must clearly say:

1. manual only;
2. do not run automatically;
3. requires API key in shell;
4. requires real-call flags;
5. max 1 paper or max 3 papers;
6. no final_review;
7. no email sending.

Update:

1. SOUL.md
2. MEMORY.md
3. HEARTBEAT.md
4. BOOTSTRAP.md
5. EXPERIMENT_READINESS.md
6. docs/10_OPENCLAW_EXPERIMENT_READINESS.md

## Tests

Add or update tests for:

1. open-access eligibility.
2. rejecting non-open-access PDF.
3. rejecting arbitrary URL.
4. rejecting paywall bypass.
5. one-paper full-paper canary dry-run.
6. one-paper full-paper canary real-call command requirements.
7. fulltext artifact schema.
8. extracted text path and hash.
9. no fulltext in ledger.
10. analysis model ID must start with openrouter/.
11. three-paper selection only A/B + High.
12. C/D cannot enter fulltext analysis.
13. three-paper cross-validation schema.
14. cross-validation marks partial extraction limitations.
15. final_review real-call forbidden.
16. brief_synthesis real-call forbidden.
17. runtime guard passes.
18. Codex metadata passes.
19. existing tests do not regress.

Unit tests must not require real network or real API calls. Use fake provider responses / monkeypatch for tests.

## Real-call budget limits

During this goal, real OpenRouter calls are allowed only if needed to complete the goal.

Limits:

1. One-paper full-paper canary:
   - max 1 real literature_analysis call
   - max_cost_usd <= 5

2. Three-paper fulltext canary:
   - max 3 real literature_analysis calls
   - max 1 real cross_validation call
   - total max_cost_usd <= 20

3. No final_review real-call.
4. No brief_synthesis real-call.
5. No email sending.

If total estimated cost exceeds the configured max_cost_usd, fail closed.

If selected PDFs are too long, chunk or truncate safely and report limitation.

## Required validation commands

At the end, run:

PYTHONPATH=src python3 -m unittest discover -s tests
make test
make runtime-guard
python3 scripts/validate_codex_metadata.py
PYTHONPATH=src python3 -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5
PYTHONPATH=src python3 -m zyw_insight.cli runtime-guard "$HOME/.openclaw/openclaw.zyw-insight.openrouter-only.json5"

Run dry-run commands first:

PYTHONPATH=src python3 -m zyw_insight.cli full-paper-canary \
  --query-profile datacenter_networking \
  --provider arxiv \
  --max-candidates 20 \
  --internal-model-id openrouter/qwen/qwen3.5-397b-a17b \
  --environment quality_first \
  --spent-usd 50 \
  --max-cost-usd 5 \
  --pretty

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

Then, if dry-run passes and OPENROUTER_API_KEY exists, run real-call commands exactly once each:

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

After any real call, run:

grep -RInE "OPENROUTER_API_KEY|Authorization|Bearer|sk-or-|sk-|api[_-]?key|secret|access[_-]?token|refresh[_-]?token|OPENAI_API_KEY" .zyw_insight || true

grep -RInE "\"messages\"[[:space:]]*:|\"body\"[[:space:]]*:|\"content\"[[:space:]]*:|\"reasoning\"[[:space:]]*:|\"reasoning_details\"[[:space:]]*:" .zyw_insight || true

These greps may match false-valued boundary fields; inspect whether any real secret or unredacted content appears. If real secret or unredacted model output appears, stop and fix redaction.

## Strict prohibitions

Do not:

1. print OPENROUTER_API_KEY;
2. write OPENROUTER_API_KEY to file;
3. fetch paywalled PDF;
4. bypass paywall;
5. run final_review real-call;
6. run brief_synthesis real-call;
7. send email/webhook;
8. enable cron real-call;
9. put Codex into OpenClaw runtime;
10. store full model content / reasoning / messages in ledger;
11. commit .zyw_insight artifacts;
12. weaken runtime guard.

## Stop condition

Stop only when all are true:

1. One-paper open-access full-text/PDF canary exists.
2. One-paper real literature_analysis canary ran successfully or failed closed with clear reason.
3. Three-paper full-text canary exists.
4. Three-paper cross-validation real or dry-run report exists.
5. If real calls ran, costs stayed within caps.
6. No PDF/paywall violations occurred.
7. No email/webhook sent.
8. No final_review real-call.
9. Tests pass.
10. Runtime guard passes.
11. Codex metadata passes.
12. OpenClaw harness templates are updated.
13. Final report explains what is proven and what remains limited.

## Final report in Chinese

Report:

1. Files changed.
2. New CLI commands.
3. OpenRouter model IDs used and whether they follow openrouter/<provider>/<model-slug>.
4. One-paper selected paper, source, PDF eligibility, extraction quality.
5. One-paper real-call cost, usage, redaction status.
6. Three selected papers, extraction quality.
7. Cross-validation findings.
8. Whether analysis is full_text_limited or full_paper_verified.
9. Whether no paywall/PDF policy violations occurred.
10. Whether no email/webhook was sent.
11. Whether no final_review real-call occurred.
12. Tests and runtime guard results.
13. Next recommended step before production OpenClaw operation.
