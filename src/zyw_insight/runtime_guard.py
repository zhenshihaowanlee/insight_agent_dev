"""Runtime boundary checks for OpenClaw configs.

The guard checks the OpenClaw runtime config template. It intentionally focuses on
config files, not documentation, because runtime docs may mention forbidden tools
as negative examples.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re


FORBIDDEN_PATTERNS = [
    r"openai-codex",
    r"@openai/codex",
    r"\bcodex\b",
    r"chatgpt/codex",
    r"codex\.openai",
]

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",
    r"OPENROUTER_API_KEY\s*[:=]\s*['\"][^'\"]+['\"]",
    r"OPENAI_API_KEY\s*[:=]\s*['\"][^'\"]+['\"]",
]
ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
SCHEMA_DIR = ROOT / "schemas"
SRC_DIR = ROOT / "src" / "zyw_insight"
CRON_DIR = ROOT / "openclaw" / "harness" / "cron"
FORBIDDEN_BUDGET_TERMS = ("codex", "coding-agent", "oauth", "@openai/codex")
FORBIDDEN_ADAPTER_CALL_PATTERNS = (
    "requests.post",
    "urllib.request.urlopen",
    "http.client",
    "aiohttp",
    "curl ",
    "httpx.post",
)


@dataclass(frozen=True)
class RuntimeGuardResult:
    ok: bool
    path: str
    failures: list[str]


def check_runtime_config(path: str | Path) -> RuntimeGuardResult:
    p = Path(path).expanduser()
    failures: list[str] = []
    if not p.exists():
        return RuntimeGuardResult(False, str(p), ["config file does not exist"])
    text = p.read_text(encoding="utf-8")
    lower = text.lower()

    if "openrouter/" not in lower:
        failures.append("no openrouter/ model reference found")

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            failures.append(f"forbidden runtime pattern found: {pattern}")

    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            failures.append(f"possible secret found: {pattern}")

    if "deliver: true" in lower:
        failures.append("deliver: true found; early runtime should be draft-only")

    failures.extend(_check_budget_configs())
    failures.extend(_check_adapter_dry_run())
    failures.extend(_check_openrouter_canary())
    failures.extend(_check_pipeline_canary())
    failures.extend(_check_source_discovery())
    failures.extend(_check_discovery_pipeline_integration())
    failures.extend(_check_fulltext_canary_boundary())
    failures.extend(_check_openclaw_source_discovery_policy(text))
    failures.extend(_check_pipeline_dry_run())
    failures.extend(_check_email_draft_workflow())
    failures.extend(_check_pre_send_review())
    return RuntimeGuardResult(not failures, str(p), failures)


def _check_budget_configs() -> list[str]:
    failures: list[str] = []
    if not CONFIG_DIR.exists():
        failures.append("configs directory missing")
        return failures

    budget_paths = sorted(CONFIG_DIR.glob("budget.*.json"))
    if not budget_paths:
        failures.append("no budget policy configs found")
        return failures
    if not (CONFIG_DIR / "budget.quality_first.json").exists():
        failures.append("quality_first budget config missing")

    for path in budget_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"{path}: possible secret found: {pattern}")
        try:
            policy = json.loads(text)
        except json.JSONDecodeError as exc:
            failures.append(f"{path}: invalid JSON: {exc}")
            continue

        delivery = policy.get("delivery_policy") or {}
        if delivery.get("draft_only") is not True:
            failures.append(f"{path}: delivery_policy.draft_only must be true")
        if delivery.get("requires_human_approval") is not True:
            failures.append(f"{path}: delivery_policy.requires_human_approval must be true")

        stage_policies = policy.get("stage_policies") or {}
        if (stage_policies.get("final_review") or {}).get("manual_only") is not True:
            failures.append(f"{path}: final_review manual_only must be true")
        for stage, stage_policy in stage_policies.items():
            for key in ("preferred_model", "fallback_model"):
                model_id = stage_policy.get(key)
                if not isinstance(model_id, str):
                    failures.append(f"{path}: {stage}.{key} missing")
                    continue
                lowered_model = model_id.lower()
                if not model_id.startswith("openrouter/"):
                    failures.append(f"{path}: {stage}.{key} must start with openrouter/")
                if any(term in lowered_model for term in FORBIDDEN_BUDGET_TERMS):
                    failures.append(f"{path}: forbidden provider term in {stage}.{key}")

        provider = policy.get("provider_policy") or {}
        if provider.get("allowed_provider_prefixes") != ["openrouter/"]:
            failures.append(f"{path}: allowed_provider_prefixes must be only openrouter/")
        required_forbidden = {"codex", "coding-agent", "oauth", "@openai/codex"}
        if not required_forbidden.issubset(set(provider.get("forbidden_provider_terms") or [])):
            failures.append(f"{path}: forbidden_provider_terms incomplete")

        if policy.get("environment") == "quality_first":
            if float(policy.get("hard_cap_usd", 0)) > 600 and "manual_override_policy" not in policy:
                failures.append(f"{path}: quality_first hard_cap_usd exceeds 600 without manual_override_policy")

    return failures


def _check_adapter_dry_run() -> list[str]:
    failures: list[str] = []
    required_schemas = ["model_request.schema.json", "model_response.schema.json", "adapter_run.schema.json"]
    for schema_name in required_schemas:
        path = SCHEMA_DIR / schema_name
        if not path.exists():
            failures.append(f"{schema_name} missing")
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{schema_name}: invalid JSON: {exc}")
            continue
        dry_run = (schema.get("properties") or {}).get("dry_run") or {}
        if dry_run.get("const") is not True:
            failures.append(f"{schema_name}: dry_run must be const true")

    adapter = SRC_DIR / "openrouter_adapter.py"
    if not adapter.exists():
        failures.append("openrouter_adapter.py missing")
        return failures
    text = adapter.read_text(encoding="utf-8")
    lowered = text.lower()
    if "openrouter_api_key" in lowered:
        failures.append("openrouter_adapter.py must not read or mention runtime API key env vars")
    for marker in FORBIDDEN_ADAPTER_CALL_PATTERNS:
        if marker in lowered:
            failures.append(f"openrouter_adapter.py contains forbidden network call marker: {marker}")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            failures.append(f"openrouter_adapter.py possible secret found: {pattern}")
    return failures


def _check_openrouter_canary() -> list[str]:
    failures: list[str] = []
    config_path = CONFIG_DIR / "openrouter_canary.json"
    if not config_path.exists():
        failures.append("openrouter_canary.json missing")
        return failures
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"openrouter_canary.json invalid JSON: {exc}")
        return failures
    expected = {
        "enabled_by_default": False,
        "default_dry_run": True,
        "max_real_calls_per_run": 1,
        "require_manual_flags": True,
        "require_env_api_key": True,
        "ledger_redaction_required": True,
        "draft_only": True,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            failures.append(f"openrouter_canary.json: {key} must be {value!r}")
    if config.get("allowed_provider") != "openrouter":
        failures.append("openrouter_canary.json: allowed_provider must be openrouter")
    if config.get("internal_model_prefix") != "openrouter/":
        failures.append("openrouter_canary.json: internal_model_prefix must be openrouter/")
    required_forbidden = {"codex", "coding-agent", "oauth", "@openai/codex"}
    if not required_forbidden.issubset(set(config.get("forbidden_provider_terms") or [])):
        failures.append("openrouter_canary.json: forbidden_provider_terms incomplete")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, config_path.read_text(encoding="utf-8"), flags=re.IGNORECASE):
            failures.append(f"openrouter_canary.json possible secret found: {pattern}")

    canary = SRC_DIR / "openrouter_canary.py"
    if not canary.exists():
        failures.append("openrouter_canary.py missing")
        return failures
    text = canary.read_text(encoding="utf-8")
    lowered = text.lower()
    if "execute_openrouter_canary" not in text:
        failures.append("openrouter_canary.py must expose execute_openrouter_canary")
    if "real_call" not in text or "allow_network" not in text or "confirm_charge" not in text:
        failures.append("openrouter_canary.py must require real_call/allow_network/confirm_charge gates")
    if "default_dry_run" not in config_path.read_text(encoding="utf-8"):
        failures.append("openrouter canary config must include default_dry_run")
    if "https://openrouter.ai/api/v1/chat/completions" not in text:
        failures.append("openrouter_canary.py endpoint must be OpenRouter chat completions")
    if "redact_response_choices" not in text:
        failures.append("openrouter_canary.py must redact model response choices before logging")
    if '"choices": parsed.get("choices"' in text or "'choices': parsed.get('choices'" in text:
        failures.append("openrouter_canary.py must not store raw OpenRouter choices")
    for marker in ("reasoning_sha256", "reasoning_length", "reasoning_redacted", "reasoning_details_sha256", "reasoning_details_length", "reasoning_details_redacted"):
        if marker not in text:
            failures.append(f"openrouter_canary.py missing response reasoning redaction marker: {marker}")
    forbidden_endpoints = ("api.openai.com", "localhost", "127.0.0.1")
    for endpoint in forbidden_endpoints:
        if endpoint in lowered:
            failures.append(f"openrouter_canary.py contains forbidden endpoint marker: {endpoint}")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            failures.append(f"openrouter_canary.py possible secret found: {pattern}")
    for forbidden_sink in ("append_budget_event(os.environ", "metadata.*openrouter_api_key", "ledger.*openrouter_api_key"):
        if forbidden_sink in lowered:
            failures.append("openrouter_canary.py appears to log API key/env data")
    ledger_module = SRC_DIR / "budget_ledger.py"
    if not ledger_module.exists():
        failures.append("budget_ledger.py missing")
    else:
        ledger_text = ledger_module.read_text(encoding="utf-8")
        for marker in ("reasoning", "reasoning_details", "messages", "body", "content", "headers", "authorization"):
            if marker not in ledger_text:
                failures.append(f"budget_ledger.py forbidden event key missing: {marker}")
        if '"manual_required": bool(' not in ledger_text:
            failures.append("budget_ledger.py must coerce canary manual_required to boolean")
    return failures


def _check_pipeline_dry_run() -> list[str]:
    failures: list[str] = []
    for schema_name in ("pipeline_run.schema.json", "draft_artifact.schema.json"):
        path = SCHEMA_DIR / schema_name
        if not path.exists():
            failures.append(f"{schema_name} missing")
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{schema_name}: invalid JSON: {exc}")
            continue
        if schema_name == "pipeline_run.schema.json":
            dry_run = (schema.get("properties") or {}).get("dry_run") or {}
            if dry_run.get("const") is not True:
                failures.append(f"{schema_name}: dry_run must be const true")

    pipeline = SRC_DIR / "pipeline.py"
    if not pipeline.exists():
        failures.append("pipeline.py missing")
    else:
        text = pipeline.read_text(encoding="utf-8")
        lowered = text.lower()
        if "openrouter_api_key" in lowered:
            failures.append("pipeline.py must not read runtime API key env vars")
        forbidden_pipeline_markers = (
            "execute_openrouter_canary(",
            "real_call=true",
            "urllib.request.urlopen",
            "requests.post",
            "httpx.",
            "aiohttp",
            "smtplib",
            "sendmail",
        )
        for marker in forbidden_pipeline_markers:
            if marker in lowered:
                failures.append(f"pipeline.py contains forbidden marker: {marker}")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"pipeline.py possible secret found: {pattern}")

    renderer = SRC_DIR / "draft_renderer.py"
    if not renderer.exists():
        failures.append("draft_renderer.py missing")
    else:
        text = renderer.read_text(encoding="utf-8")
        for marker in ("OPENROUTER_API_KEY", "Authorization: Bearer", "sk-"):
            if marker.lower() in text.lower():
                failures.append(f"draft_renderer.py contains forbidden output marker: {marker}")

    if not CRON_DIR.exists():
        failures.append("openclaw cron directory missing")
    else:
        cron_paths = [
            CRON_DIR / "zyw_72h_dry_run.prompt.md",
            CRON_DIR / "zyw_72h_dry_run.config.json5",
        ]
        forbidden_cron_terms = (
            "--real-call",
            "--allow-network",
            "--confirm-openrouter-charge",
            "OPENROUTER_API_KEY",
            "curl",
            "requests.post",
            "httpx",
            "webhook",
            "sendmail",
            "smtp",
        )
        for path in cron_paths:
            if not path.exists():
                failures.append(f"{path.name} missing")
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for term in forbidden_cron_terms:
                if term.lower() in lowered:
                    failures.append(f"{path.name} contains forbidden cron dry-run marker: {term}")

    return failures


def _check_pipeline_canary() -> list[str]:
    failures: list[str] = []
    schema_path = SCHEMA_DIR / "pipeline_canary.schema.json"
    if not schema_path.exists():
        failures.append("pipeline_canary.schema.json missing")
    else:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"pipeline_canary.schema.json: invalid JSON: {exc}")
        else:
            required = set(schema.get("required") or [])
            for key in ("dry_run", "manual_approval", "runtime_boundary", "real_stage_canaries"):
                if key not in required:
                    failures.append(f"pipeline_canary.schema.json missing required key: {key}")

    module = SRC_DIR / "pipeline_canary.py"
    if not module.exists():
        failures.append("pipeline_canary.py missing")
    else:
        text = module.read_text(encoding="utf-8")
        lowered = text.lower()
        for marker in (
            "real_call: bool = false",
            "default_allowed_real_stages",
            "literature_analysis",
            "never_real_stages",
            "final_review",
            "brief_synthesis",
            "cron_triggered_real_call",
            "reasoning_logged",
            "execute_openrouter_canary",
        ):
            if marker not in lowered:
                failures.append(f"pipeline_canary.py missing guard marker: {marker}")
        forbidden_markers = (
            "smtplib",
            "sendmail",
            "webhook_url",
            "webhook(",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request.urlopen",
            "openrouter_api_key",
        )
        for marker in forbidden_markers:
            if marker in lowered:
                failures.append(f"pipeline_canary.py contains forbidden marker: {marker}")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"pipeline_canary.py possible secret found: {pattern}")

    if CRON_DIR.exists():
        for path in (
            CRON_DIR / "zyw_pipeline_canary_dry_run.prompt.md",
            CRON_DIR / "zyw_pipeline_canary_dry_run.config.json5",
        ):
            if not path.exists():
                failures.append(f"{path.name} missing")
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for marker in ("--real-call", "--allow-network", "--confirm-openrouter-charge", "openrouter_api_key", "final_review", "smtp", "sendmail", "webhook", "curl"):
                if marker in lowered:
                    failures.append(f"{path.name} contains forbidden pipeline canary template marker: {marker}")
    return failures


def _check_source_discovery() -> list[str]:
    failures: list[str] = []
    config_path = CONFIG_DIR / "source_discovery.json"
    if not config_path.exists():
        failures.append("source_discovery.json missing")
        return failures
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"source_discovery.json invalid JSON: {exc}")
        return failures
    expected_allowlist = ["arxiv", "openalex", "crossref", "semantic_scholar", "ietf"]
    if config.get("provider_allowlist") != expected_allowlist:
        failures.append("source_discovery.json provider_allowlist must match approved providers")
    for key in ("pdf_download_enabled", "fulltext_fetch_enabled", "paywall_bypass_enabled", "delivery_enabled", "model_call_enabled_by_default"):
        if config.get(key) is not False:
            failures.append(f"source_discovery.json {key} must be false")
    for schema_name in ("source_candidate.schema.json", "discovery_run.schema.json"):
        if not (SCHEMA_DIR / schema_name).exists():
            failures.append(f"{schema_name} missing")

    module = SRC_DIR / "source_discovery.py"
    if not module.exists():
        failures.append("source_discovery.py missing")
    else:
        text = module.read_text(encoding="utf-8")
        lowered = text.lower()
        for provider in expected_allowlist:
            if provider not in lowered:
                failures.append(f"source_discovery.py missing provider marker: {provider}")
        forbidden = ("openrouter_api_key", "openrouter-canary", "--real-call", "download_pdf", "pdf_downloaded\": true", "fulltext_fetched\": true", "paywall_bypassed\": true", "smtplib", "sendmail", "webhook_url", "webhook(")
        for marker in forbidden:
            if marker in lowered:
                failures.append(f"source_discovery.py contains forbidden discovery marker: {marker}")
    for path in (
        CRON_DIR / "zyw_source_discovery_real_metadata.prompt.md",
        CRON_DIR / "zyw_source_discovery_real_metadata.config.json5",
    ):
        if not path.exists():
            failures.append(f"{path.name} missing")
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        forbidden = ("openrouter_api_key", "--real-call", "openrouter-canary", "pipeline-canary --real-call", "smtp", "sendmail", "webhook", "download pdf", "pdf download")
        for marker in forbidden:
            if marker in lowered:
                failures.append(f"{path.name} contains forbidden discovery cron marker: {marker}")
    return failures


def _check_discovery_pipeline_integration() -> list[str]:
    failures: list[str] = []
    cli = SRC_DIR / "cli.py"
    module = SRC_DIR / "discovery_pipeline.py"
    if not cli.exists():
        failures.append("cli.py missing")
    else:
        text = cli.read_text(encoding="utf-8")
        if "run-discovery-72h-dry-run" not in text:
            failures.append("CLI must expose run-discovery-72h-dry-run")
    if not module.exists():
        failures.append("discovery_pipeline.py missing")
        return failures

    text = module.read_text(encoding="utf-8")
    lowered = text.lower()
    required_markers = (
        "untrusted metadata only",
        "no full text fetched",
        "no pdf downloaded",
        "not sufficient for strong conclusion",
        "body_is_untrusted: true",
        "eligible_source_tiers",
        "eligible_deep_read_priority",
        "signal_only_tiers",
        "background_only_tiers",
        "selected_candidate_stubs",
        "candidate_to_pipeline_input",
        "run_72h_dry_run_pipeline",
        "api_key_read",
    )
    for marker in required_markers:
        if marker not in lowered:
            failures.append(f"discovery_pipeline.py missing required marker: {marker}")

    forbidden_markers = (
        "os.environ",
        "openrouter_api_key",
        "execute_openrouter_canary(",
        "openrouter-canary",
        "pipeline-canary",
        "--real-call",
        "--allow-network",
        "--confirm-openrouter-charge",
        "requests.post",
        "httpx",
        "aiohttp",
        "urllib.request.urlopen",
        "smtplib",
        "sendmail",
        "webhook_url",
        "webhook(",
        "download_pdf",
        "fetch_fulltext",
        "bypass_paywall",
        "pdf_downloaded\": true",
        "fulltext_fetched\": true",
        "paywall_bypassed\": true",
    )
    for marker in forbidden_markers:
        if marker in lowered:
            failures.append(f"discovery_pipeline.py contains forbidden marker: {marker}")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            failures.append(f"discovery_pipeline.py possible secret found: {pattern}")

    if CRON_DIR.exists():
        forbidden_cron_terms = (
            "--real-call",
            "--allow-network",
            "--confirm-openrouter-charge",
            "OPENROUTER_API_KEY",
            "pdf download",
            "download pdf",
            "download_pdf",
            "smtp",
            "sendmail",
            "webhook",
            "curl",
            "openrouter-canary",
        )
        for path in sorted(CRON_DIR.glob("zyw_*.config.json5")) + [p for p in sorted(CRON_DIR.glob("zyw_*.prompt.md")) if "_manual" not in p.name]:
            lowered_cron = path.read_text(encoding="utf-8").lower()
            for term in forbidden_cron_terms:
                if term.lower() in lowered_cron:
                    failures.append(f"{path.name} contains forbidden OpenClaw cron marker: {term}")
    return failures


def _check_fulltext_canary_boundary() -> list[str]:
    failures: list[str] = []
    config_path = CONFIG_DIR / "fulltext_policy.json"
    if not config_path.exists():
        failures.append("fulltext_policy.json missing")
        return failures
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"fulltext_policy.json invalid JSON: {exc}")
        return failures
    expected_false = (
        "arbitrary_url_fetch_enabled",
        "paywall_bypass_enabled",
        "credential_use_enabled",
        "publisher_pdf_fetch_enabled",
        "allow_c_or_d_pdf_analysis",
    )
    for key in expected_false:
        if config.get(key) is not False:
            failures.append(f"fulltext_policy.json {key} must be false")
    if config.get("open_access_only") is not True:
        failures.append("fulltext_policy.json open_access_only must be true")
    if "arxiv" not in set(config.get("provider_allowlist") or []):
        failures.append("fulltext_policy.json provider_allowlist must include arxiv")
    for key in ("max_pdf_bytes", "max_pages", "max_extracted_chars"):
        if not isinstance(config.get(key), int) or config.get(key) <= 0:
            failures.append(f"fulltext_policy.json {key} must be positive integer")

    token_policy_path = CONFIG_DIR / "fulltext_token_policy.json"
    if not token_policy_path.exists():
        failures.append("fulltext_token_policy.json missing")
    else:
        try:
            token_policy = json.loads(token_policy_path.read_text(encoding="utf-8")).get("one_shot_full_paper") or {}
        except json.JSONDecodeError as exc:
            failures.append(f"fulltext_token_policy.json invalid JSON: {exc}")
            token_policy = {}
        if int(token_policy.get("max_output_tokens_hard") or 0) <= 256:
            failures.append("fulltext_token_policy.json one-shot max_output_tokens_hard must be greater than 256")

    for schema_name in ("fulltext_eligibility.schema.json", "fulltext_artifact.schema.json", "cross_validation_report.schema.json", "fulltext_prompt_audit.schema.json", "full_paper_analysis_run.schema.json", "token_budget.schema.json"):
        if not (SCHEMA_DIR / schema_name).exists():
            failures.append(f"{schema_name} missing")

    modules = {
        "fulltext_eligibility.py": ("open_access_only", "paywall_bypass", "fetch_allowed", "C/D candidates cannot enter fulltext analysis"),
        "fulltext_fetch.py": ("max_pdf_bytes", "max_pages", "max_extracted_chars", "body_logged_to_ledger", "ocr_used"),
        "pdf_text_extract.py": ("ocr_used", "loop_count", "max_chars"),
        "full_paper_canary.py": ("full-paper", "three", "final_review_real_call_executed", "brief_synthesis_real_call_executed", "execute_openrouter_canary", "allow_fulltext_prompt", "one_shot_fulltext", "fulltext_prompt_audit", "model_cni_schema_valid"),
        "cross_validation.py": ("claims_full_paper_cross_validation", "full_text_limited_cross_validation", "final_review_real_call_executed"),
    }
    for module_name, required_markers in modules.items():
        path = SRC_DIR / module_name
        if not path.exists():
            failures.append(f"{module_name} missing")
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for marker in required_markers:
            if marker.lower() not in lowered:
                failures.append(f"{module_name} missing marker: {marker}")
        for forbidden in ("openrouter_api_key", "smtplib", "sendmail", "webhook_url", "webhook(", "final_review\",", "brief_synthesis\","):
            if forbidden in lowered:
                failures.append(f"{module_name} contains forbidden marker: {forbidden}")
        if module_name in {"fulltext_fetch.py", "pdf_text_extract.py"} and "ocr" in lowered and "ocr_used" not in lowered:
            failures.append(f"{module_name} mentions OCR without explicit disabled marker")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"{module_name} possible secret found: {pattern}")

    canary_text = (SRC_DIR / "openrouter_canary.py").read_text(encoding="utf-8") if (SRC_DIR / "openrouter_canary.py").exists() else ""
    if "messages_sha256" not in canary_text or "messages_redacted" not in canary_text:
        failures.append("openrouter_canary.py must redact one-shot messages with hash markers")
    if "selected_text" not in canary_text or "transient OpenRouter request" not in canary_text:
        failures.append("openrouter_canary.py must mark selected_text as transient fulltext prompt data")
    ledger_text = (SRC_DIR / "budget_ledger.py").read_text(encoding="utf-8") if (SRC_DIR / "budget_ledger.py").exists() else ""
    for forbidden_key in ("selected_text", "messages", "body", "content", "reasoning", "reasoning_details"):
        if forbidden_key not in ledger_text:
            failures.append(f"budget_ledger.py must forbid ledger key: {forbidden_key}")

    for path in (
        CRON_DIR / "zyw_full_paper_canary_manual.prompt.md",
        CRON_DIR / "zyw_three_paper_cross_validation_manual.prompt.md",
    ):
        if not path.exists():
            failures.append(f"{path.name} missing")
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        for marker in ("manual only", "do not run automatically", "requires", "--real-call", "--allow-network", "--confirm-openrouter-charge", "no final_review", "no email"):
            if marker not in lowered:
                failures.append(f"{path.name} missing required manual template marker: {marker}")
        if "enabled: true" in lowered:
            failures.append(f"{path.name} must not enable cron")
    return failures


def _check_openclaw_source_discovery_policy(config_text: str) -> list[str]:
    failures: list[str] = []
    lowered = config_text.lower()
    if "sourcediscovery" not in lowered:
        policy_path = ROOT / "openclaw" / "harness" / "config" / "source_discovery.policy.json"
        if not policy_path.exists():
            failures.append("OpenClaw config has no sourceDiscovery block and fallback source_discovery.policy.json is missing")
            return failures
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"source_discovery.policy.json invalid JSON: {exc}")
            return failures
        if policy.get("providerAllowlist") != ["arxiv", "openalex", "crossref", "semantic_scholar", "ietf"]:
            failures.append("source_discovery.policy.json providerAllowlist must match approved providers")
        for key in ("modelNetworkAllowedByDiscovery", "deliveryNetworkAllowedByDiscovery", "pdfDownloadEnabled", "fulltextFetchEnabled", "paywallBypassEnabled"):
            if policy.get(key) is not False:
                failures.append(f"source_discovery.policy.json {key} must be false")
        return failures

    required_terms = (
        "realmetadatadiscoveryenabled",
        "discoverynetworkallowed",
        "modelnetworkallowedbydiscovery: false",
        "deliverynetworkallowedbydiscovery: false",
        "pdfdownloadenabled: false",
        "fulltextfetchenabled: false",
        "paywallbypassenabled: false",
        '"arxiv"',
        '"openalex"',
        '"crossref"',
        '"semantic_scholar"',
        '"ietf"',
    )
    for term in required_terms:
        if term.lower() not in lowered:
            failures.append(f"OpenClaw sourceDiscovery missing safe setting: {term}")
    return failures


def _check_email_draft_workflow() -> list[str]:
    failures: list[str] = []
    for schema_name in ("email_draft.schema.json", "human_approval.schema.json"):
        path = SCHEMA_DIR / schema_name
        if not path.exists():
            failures.append(f"{schema_name} missing")
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{schema_name}: invalid JSON: {exc}")
            continue
        if schema_name == "email_draft.schema.json":
            props = schema.get("properties") or {}
            draft_only = props.get("draft_only") or {}
            if draft_only.get("const") is not True:
                failures.append("email_draft.schema.json: draft_only must be const true")
        if schema_name == "human_approval.schema.json":
            decision = ((schema.get("properties") or {}).get("approval_decision") or {})
            if "pending" not in set(decision.get("enum") or []):
                failures.append("human_approval.schema.json: approval_decision must include pending")

    module = SRC_DIR / "email_draft.py"
    if not module.exists():
        failures.append("email_draft.py missing")
    else:
        text = module.read_text(encoding="utf-8")
        lowered = text.lower()
        forbidden_markers = (
            "import smtplib",
            "smtplib.",
            "smtp(",
            ".sendmail(",
            "sendmail ",
            "requests.post",
            "httpx",
            "aiohttp",
            "curl ",
            "urllib.request.urlopen",
            "os.environ",
        )
        for marker in forbidden_markers:
            if marker in lowered:
                failures.append(f"email_draft.py contains forbidden email draft marker: {marker}")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"email_draft.py possible secret found: {pattern}")

    if CRON_DIR.exists():
        for path in (CRON_DIR / "zyw_email_draft_dry_run.prompt.md", CRON_DIR / "zyw_email_draft_dry_run.config.json5"):
            if not path.exists():
                failures.append(f"{path.name} missing")
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for marker in ("smtp", "sendmail", "webhook", "curl", "openrouter_api_key", "--real-call"):
                if marker in lowered:
                    failures.append(f"{path.name} contains forbidden email draft marker: {marker}")

    return failures


def _check_pre_send_review() -> list[str]:
    failures: list[str] = []
    schema_path = SCHEMA_DIR / "pre_send_review.schema.json"
    if not schema_path.exists():
        failures.append("pre_send_review.schema.json missing")
    else:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"pre_send_review.schema.json: invalid JSON: {exc}")
        else:
            props = schema.get("properties") or {}
            dry_run = props.get("dry_run") or {}
            if dry_run.get("const") is not True:
                failures.append("pre_send_review.schema.json: dry_run must be const true")
            decisions = set((props.get("overall_decision") or {}).get("enum") or [])
            if "approved_for_send" in decisions:
                failures.append("pre_send_review.schema.json must not allow approved_for_send")

    module = SRC_DIR / "pre_send_review.py"
    if not module.exists():
        failures.append("pre_send_review.py missing")
    else:
        text = module.read_text(encoding="utf-8")
        lowered = text.lower()
        forbidden_markers = (
            "import smtplib",
            "smtplib.",
            "smtp(",
            ".sendmail(",
            "sendmail ",
            "requests.post(",
            "httpx.",
            "aiohttp.",
            "urllib.request.urlopen(",
            "os.environ",
            "execute_openrouter_canary(",
        )
        for marker in forbidden_markers:
            if marker in lowered:
                failures.append(f"pre_send_review.py contains forbidden marker: {marker}")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"pre_send_review.py possible secret found: {pattern}")

    if CRON_DIR.exists():
        for path in (CRON_DIR / "zyw_pre_send_review_dry_run.prompt.md", CRON_DIR / "zyw_pre_send_review_dry_run.config.json5"):
            if not path.exists():
                failures.append(f"{path.name} missing")
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for marker in ("smtp", "sendmail", "webhook", "curl", "openrouter_api_key", "--real-call"):
                if marker in lowered:
                    failures.append(f"{path.name} contains forbidden pre-send review marker: {marker}")

    return failures
