from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas"

NETWORK_IMPACT_KEYS = [
    "latency",
    "jitter_ipdv",
    "bandwidth_capacity",
    "reliability",
    "security",
    "operations",
    "ber_error",
    "scalability",
    "cost_power",
]
ALLOWED_IMPACTS = {"++", "+", "0", "-", "--", "?"}
ALLOWED_CRITIC_SEVERITIES = {"info", "warning", "major", "critical"}
ALLOWED_ACTIONS = {"S", "A", "B", "C", "D"}
ALLOWED_CONFIDENCE_ADJUSTMENTS = {"upgrade", "keep", "downgrade", "severe_downgrade"}
ALLOWED_SIGNAL_STRENGTHS = {"high", "medium", "low", "weak", "unclear"}
ALLOWED_BRIEF_CONFIDENCE = {"high", "medium", "low", "weak"}
ALLOWED_QUALITY_PRIORITY = {"high", "balanced", "cost_saving"}
ALLOWED_BUDGET_MODE = {"poc", "production", "quality_first", "research", "flagship"}
ALLOWED_CONFLICT_SEVERITY = {"low", "medium", "high", "critical"}
ALLOWED_MODEL_RESPONSE_STATUS = {"planned", "skipped", "denied", "mock_success", "mock_error"}
ALLOWED_PIPELINE_TRIGGERS = {"manual", "openclaw_cron_dry_run"}
ALLOWED_DRAFT_ARTIFACT_TYPES = {"markdown_brief", "json_brief", "run_manifest"}
ALLOWED_APPROVAL_DECISIONS = {"pending", "approved_for_manual_send", "rejected", "needs_revision"}
ALLOWED_PRE_SEND_DECISIONS = {"ready_for_human_review", "needs_revision", "blocked"}
ALLOWED_PIPELINE_CANARY_STAGES = {"literature_analysis"}
ALLOWED_DISCOVERY_PROVIDERS = {"arxiv", "semantic_scholar", "openalex", "crossref", "ietf", "manual_watchlist"}
ALLOWED_SOURCE_TIER_HINTS = {"A", "B", "C", "D", "unknown"}
ALLOWED_DEEP_READ_HINTS = {"High", "Medium", "Low", "unknown"}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key|authorization|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]


class SchemaValidationError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("schema validation failed: " + "; ".join(errors))


def load_schema(name_or_path: str | Path) -> Dict[str, Any]:
    path = Path(name_or_path)
    if not path.suffix:
        path = SCHEMA_DIR / f"{path}.schema.json"
    elif not path.is_absolute():
        path = ROOT / path
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _type_matches(value: Any, expected: Any) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    for item in expected_types:
        if item == "object" and isinstance(value, dict):
            return True
        if item == "array" and isinstance(value, list):
            return True
        if item == "string" and isinstance(value, str):
            return True
        if item == "boolean" and isinstance(value, bool):
            return True
        if item == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if item == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if item == "null" and value is None:
            return True
    return False


def _minimal_validate(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in schema.get("required", []):
        if key not in data:
            errors.append(f"missing required key: {key}")

    properties = schema.get("properties", {})
    for key, spec in properties.items():
        if key in data and "type" in spec and not _type_matches(data[key], spec["type"]):
            errors.append(f"{key} has invalid type")
        if key in data and "const" in spec and data[key] != spec["const"]:
            errors.append(f"{key} must equal {spec['const']!r}")

    if schema.get("title") == "CNILiteratureAnalysis":
        network = data.get("network_impact_vector", {})
        if not isinstance(network, dict):
            errors.append("network_impact_vector must be an object")
        else:
            for key in NETWORK_IMPACT_KEYS:
                item = network.get(key)
                if not isinstance(item, dict):
                    errors.append(f"network_impact_vector.{key} missing or invalid")
                    continue
                impact = item.get("impact")
                if impact not in ALLOWED_IMPACTS:
                    errors.append(f"network_impact_vector.{key}.impact invalid: {impact!r}")
                for required in ("evidence", "risk"):
                    if not isinstance(item.get(required), str):
                        errors.append(f"network_impact_vector.{key}.{required} must be string")

        score = data.get("score", {})
        if not isinstance(score, dict):
            errors.append("score must be an object")
        else:
            total = score.get("total_score")
            if not isinstance(total, (int, float)) or isinstance(total, bool) or not 0 <= total <= 100:
                errors.append("score.total_score must be a number from 0 to 100")

    if schema.get("title") == "CNIConstraintCritic":
        action = data.get("recommended_action_after")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"recommended_action_after invalid: {action!r}")
        adjustment = data.get("confidence_adjustment")
        if adjustment not in ALLOWED_CONFIDENCE_ADJUSTMENTS:
            errors.append(f"confidence_adjustment invalid: {adjustment!r}")

        score_after = data.get("score_after", {})
        if not isinstance(score_after, dict):
            errors.append("score_after must be an object")
        else:
            total = score_after.get("total_score")
            if not isinstance(total, (int, float)) or isinstance(total, bool) or not 0 <= total <= 100:
                errors.append("score_after.total_score must be a number from 0 to 100")

        violations = data.get("hard_rule_violations", [])
        if not isinstance(violations, list):
            errors.append("hard_rule_violations must be an array")
        else:
            required = {"rule_id", "severity", "message", "affected_sections", "suggested_fix"}
            for index, item in enumerate(violations):
                if not isinstance(item, dict):
                    errors.append(f"hard_rule_violations[{index}] must be object")
                    continue
                missing = required - set(item)
                if missing:
                    errors.append(f"hard_rule_violations[{index}] missing: {', '.join(sorted(missing))}")
                if item.get("severity") not in ALLOWED_CRITIC_SEVERITIES:
                    errors.append(f"hard_rule_violations[{index}].severity invalid: {item.get('severity')!r}")

    if schema.get("title") == "CNI72hBrief":
        if not isinstance(data.get("schema_version"), str) or not data.get("schema_version"):
            errors.append("schema_version must be present")

        if not isinstance(data.get("input_traceability"), list):
            errors.append("input_traceability must be an array")

        insight = data.get("insight_quality", {})
        if not isinstance(insight, dict):
            errors.append("insight_quality must be an object")
        elif insight.get("overall_confidence") not in ALLOWED_BRIEF_CONFIDENCE:
            errors.append(f"insight_quality.overall_confidence invalid: {insight.get('overall_confidence')!r}")

        readiness = data.get("decision_readiness", {})
        if not isinstance(readiness, dict):
            errors.append("decision_readiness must be an object")
        elif readiness.get("requires_human_review") is not True:
            errors.append("decision_readiness.requires_human_review must be true")

        budget = data.get("budget_context", {})
        if not isinstance(budget, dict):
            errors.append("budget_context must be an object")
        else:
            if budget.get("quality_priority") not in ALLOWED_QUALITY_PRIORITY:
                errors.append(f"budget_context.quality_priority invalid: {budget.get('quality_priority')!r}")
            if budget.get("budget_mode") not in ALLOWED_BUDGET_MODE:
                errors.append(f"budget_context.budget_mode invalid: {budget.get('budget_mode')!r}")

        window = data.get("window", {})
        if not isinstance(window, dict):
            errors.append("window must be an object")
        else:
            hours = window.get("hours")
            if not isinstance(hours, (int, float)) or isinstance(hours, bool) or hours <= 0:
                errors.append("window.hours must be a positive number")

        draft = data.get("draft_delivery", {})
        if not isinstance(draft, dict):
            errors.append("draft_delivery must be an object")
        else:
            if draft.get("mode") != "draft_only":
                errors.append("draft_delivery.mode must be draft_only")
            if draft.get("requires_human_approval") is not True:
                errors.append("draft_delivery.requires_human_approval must be true")

        network = data.get("network_metric_trends", {})
        if not isinstance(network, dict):
            errors.append("network_metric_trends must be an object")
        else:
            for key in NETWORK_IMPACT_KEYS:
                if key not in network:
                    errors.append(f"network_metric_trends.{key} missing")

        radar = data.get("technology_signal_radar", [])
        if not isinstance(radar, list):
            errors.append("technology_signal_radar must be an array")
        else:
            for index, item in enumerate(radar):
                if not isinstance(item, dict):
                    errors.append(f"technology_signal_radar[{index}] must be object")
                    continue
                if item.get("signal_strength") not in ALLOWED_SIGNAL_STRENGTHS:
                    errors.append(f"technology_signal_radar[{index}].signal_strength invalid: {item.get('signal_strength')!r}")
                if item.get("recommended_action") not in ALLOWED_ACTIONS:
                    errors.append(f"technology_signal_radar[{index}].recommended_action invalid: {item.get('recommended_action')!r}")

        conflicts = data.get("cross_document_conflicts", [])
        if not isinstance(conflicts, list):
            errors.append("cross_document_conflicts must be an array")
        else:
            for index, item in enumerate(conflicts):
                if not isinstance(item, dict):
                    errors.append(f"cross_document_conflicts[{index}] must be object")
                    continue
                if item.get("severity") not in ALLOWED_CONFLICT_SEVERITY:
                    errors.append(f"cross_document_conflicts[{index}].severity invalid: {item.get('severity')!r}")

    if schema.get("title") == "CNIBudgetPolicy":
        from .budget import validate_budget_policy

        try:
            validate_budget_policy(data)
        except ValueError as exc:
            errors.append(str(exc))

    if schema.get("title") == "OpenRouterModelRequest":
        _check_no_secret_like(data, errors, "model_request")
        if data.get("provider") != "openrouter":
            errors.append("model_request.provider must be openrouter")
        model_id = data.get("model_id")
        if not isinstance(model_id, str) or not model_id.startswith("openrouter/"):
            errors.append("model_request.model_id must start with openrouter/")
        if data.get("dry_run") is not True:
            errors.append("model_request.dry_run must be true")

    if schema.get("title") == "OpenRouterModelResponse":
        _check_no_secret_like(data, errors, "model_response")
        if data.get("dry_run") is not True:
            errors.append("model_response.dry_run must be true")
        if data.get("provider") != "openrouter":
            errors.append("model_response.provider must be openrouter")
        if data.get("status") not in ALLOWED_MODEL_RESPONSE_STATUS:
            errors.append(f"model_response.status invalid: {data.get('status')!r}")
        model_id = data.get("model_id")
        if model_id is not None and (not isinstance(model_id, str) or not model_id.startswith("openrouter/")):
            errors.append("model_response.model_id must start with openrouter/ when present")

    if schema.get("title") == "OpenRouterAdapterRun":
        _check_no_secret_like(data, errors, "adapter_run")
        if data.get("dry_run") is not True:
            errors.append("adapter_run.dry_run must be true")
        boundary = data.get("runtime_boundary", {})
        if not isinstance(boundary, dict):
            errors.append("adapter_run.runtime_boundary must be object")
        else:
            if boundary.get("openrouter_only") is not True:
                errors.append("adapter_run.runtime_boundary.openrouter_only must be true")
            if boundary.get("codex_runtime_used") is not False:
                errors.append("adapter_run.runtime_boundary.codex_runtime_used must be false")
            if boundary.get("network_request_sent") is not False:
                errors.append("adapter_run.runtime_boundary.network_request_sent must be false")

    if schema.get("title") == "OpenRouterCanaryRun":
        _check_no_secret_like(data, errors, "openrouter_canary")
        _check_no_forbidden_canary_payload(data, errors, "openrouter_canary")
        if data.get("provider") != "openrouter":
            errors.append("openrouter_canary.provider must be openrouter")
        internal_model = data.get("internal_model_id")
        if not isinstance(internal_model, str) or not internal_model.startswith("openrouter/"):
            errors.append("openrouter_canary.internal_model_id must start with openrouter/")
        api_slug = data.get("api_model_slug")
        if not isinstance(api_slug, str) or api_slug.startswith("openrouter/"):
            errors.append("openrouter_canary.api_model_slug must not start with openrouter/")
        for marker in ("codex", "coding-agent", "oauth", "@openai/codex"):
            if marker in str(internal_model).lower() or marker in str(api_slug).lower():
                errors.append(f"openrouter_canary contains forbidden provider term: {marker}")
        boundary = data.get("runtime_boundary", {})
        if not isinstance(boundary, dict):
            errors.append("openrouter_canary.runtime_boundary must be object")
        else:
            if boundary.get("codex_runtime_used") is not False:
                errors.append("openrouter_canary.runtime_boundary.codex_runtime_used must be false")
            if boundary.get("api_key_logged") is not False:
                errors.append("openrouter_canary.runtime_boundary.api_key_logged must be false")
            if boundary.get("body_logged") is not False:
                errors.append("openrouter_canary.runtime_boundary.body_logged must be false")
            if boundary.get("messages_logged") is not False:
                errors.append("openrouter_canary.runtime_boundary.messages_logged must be false")
        ledger_event = data.get("ledger_event", {})
        if isinstance(ledger_event, dict):
            if ledger_event.get("manual_required") is None:
                errors.append("openrouter_canary.ledger_event.manual_required must not be null")
            _check_no_forbidden_canary_payload(ledger_event, errors, "openrouter_canary.ledger_event")
        response = data.get("response", {})
        if isinstance(response, dict):
            for index, choice in enumerate(response.get("choices") or []):
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message") or {}
                if not isinstance(message, dict):
                    continue
                if message.get("content_redacted") is True and "content" in message:
                    errors.append(f"openrouter_canary.response.choices[{index}].message.content must not be present when content_redacted=true")
                for field in ("reasoning", "reasoning_details"):
                    if field in message:
                        errors.append(f"openrouter_canary.response.choices[{index}].message.{field} must not be present")
                    redacted_key = f"{field}_redacted"
                    if redacted_key in message and message.get(redacted_key) is not True:
                        errors.append(f"openrouter_canary.response.choices[{index}].message.{redacted_key} must be true when present")
        approval = data.get("manual_approval", {})
        cost = data.get("cost", {})
        if data.get("real_call_executed") is True:
            if data.get("dry_run") is not False:
                errors.append("real canary execution requires dry_run=false")
            if (data.get("runtime_boundary") or {}).get("network_request_sent") is not True:
                errors.append("real canary execution requires network_request_sent=true")
            if approval.get("real_call_flag") is not True:
                errors.append("real canary execution requires real_call_flag=true")
            if approval.get("allow_network_flag") is not True:
                errors.append("real canary execution requires allow_network_flag=true")
            if approval.get("confirm_charge_flag") is not True:
                errors.append("real canary execution requires confirm_charge_flag=true")
            max_cost = cost.get("max_cost_usd")
            if not isinstance(max_cost, (int, float)) or isinstance(max_cost, bool) or max_cost <= 0:
                errors.append("real canary execution requires cost.max_cost_usd > 0")
            if data.get("stage") == "final_review" and approval.get("manual_override") is not True:
                errors.append("final_review real canary requires manual_override=true")

    if schema.get("title") == "ZYWSmallPipelineCanary":
        _check_no_secret_like(data, errors, "pipeline_canary")
        _check_no_forbidden_pipeline_canary_payload(data, errors, "pipeline_canary")
        approval = data.get("manual_approval", {})
        if not isinstance(approval, dict):
            errors.append("pipeline_canary.manual_approval must be object")
        else:
            if approval.get("max_documents", 0) > 2 and approval.get("manual_override") is not True:
                errors.append("pipeline_canary.manual_approval.max_documents must be <= 2")
            stages = approval.get("allowed_real_stages") or []
            if "final_review" in stages:
                errors.append("pipeline_canary final_review real stage is forbidden")
            if "brief_synthesis" in stages:
                errors.append("pipeline_canary brief_synthesis real stage is forbidden")
            for stage in stages:
                if stage not in ALLOWED_PIPELINE_CANARY_STAGES:
                    errors.append(f"pipeline_canary allowed real stage invalid: {stage!r}")
        if data.get("dry_run") is True and data.get("real_call_executed") is not False:
            errors.append("pipeline_canary dry_run=true requires real_call_executed=false")
        boundary = data.get("runtime_boundary", {})
        if not isinstance(boundary, dict):
            errors.append("pipeline_canary.runtime_boundary must be object")
        else:
            expected_false = (
                "codex_runtime_used",
                "cron_triggered_real_call",
                "api_key_logged",
                "body_logged",
                "messages_logged",
                "reasoning_logged",
                "email_sent",
                "webhook_sent",
            )
            for key in expected_false:
                if boundary.get(key) is not False:
                    errors.append(f"pipeline_canary.runtime_boundary.{key} must be false")
            if boundary.get("openrouter_only") is not True:
                errors.append("pipeline_canary.runtime_boundary.openrouter_only must be true")
        for index, item in enumerate(data.get("real_stage_canaries") or []):
            if not isinstance(item, dict):
                errors.append(f"pipeline_canary.real_stage_canaries[{index}] must be object")
                continue
            if item.get("stage") == "brief_synthesis" and item.get("real_call_executed") is True:
                errors.append("pipeline_canary brief_synthesis real call is forbidden")
            if item.get("stage") == "final_review" and item.get("real_call_executed") is True:
                errors.append("pipeline_canary final_review real call is forbidden")

    if schema.get("title") == "ZYWSourceCandidate":
        _check_no_secret_values(data, errors, "source_candidate")
        if data.get("body_is_untrusted") is not True:
            errors.append("source_candidate.body_is_untrusted must be true")
        if data.get("source_provider") not in ALLOWED_DISCOVERY_PROVIDERS:
            errors.append(f"source_candidate.source_provider invalid: {data.get('source_provider')!r}")
        if data.get("source_tier_hint") not in ALLOWED_SOURCE_TIER_HINTS:
            errors.append(f"source_candidate.source_tier_hint invalid: {data.get('source_tier_hint')!r}")
        if data.get("deep_read_priority_hint") not in ALLOWED_DEEP_READ_HINTS:
            errors.append(f"source_candidate.deep_read_priority_hint invalid: {data.get('deep_read_priority_hint')!r}")
        if data.get("strong_conclusion_allowed") is True:
            errors.append("source_candidate must not allow strong conclusion")

    if schema.get("title") == "ZYWDiscoveryRun":
        _check_no_secret_values(data, errors, "discovery_run")
        boundary = data.get("runtime_boundary", {})
        if not isinstance(boundary, dict):
            errors.append("discovery_run.runtime_boundary must be object")
        else:
            if boundary.get("model_network_used") is not False:
                errors.append("discovery_run.runtime_boundary.model_network_used must be false")
            if boundary.get("openrouter_called") is not False:
                errors.append("discovery_run.runtime_boundary.openrouter_called must be false")
            for key in ("pdf_downloaded", "fulltext_fetched", "paywall_bypassed", "email_sent", "webhook_sent", "codex_runtime_used"):
                if boundary.get(key) is not False:
                    errors.append(f"discovery_run.runtime_boundary.{key} must be false")
        for index, candidate in enumerate(data.get("candidates") or []):
            if isinstance(candidate, dict):
                if candidate.get("body_is_untrusted") is not True:
                    errors.append(f"discovery_run.candidates[{index}].body_is_untrusted must be true")
                if candidate.get("strong_conclusion_allowed") is True:
                    errors.append(f"discovery_run.candidates[{index}] must not allow strong conclusion")

    if schema.get("title") == "CNI72hDryRunPipelineRun":
        _check_no_secret_like(data, errors, "pipeline_run")
        if data.get("dry_run") is not True:
            errors.append("pipeline_run.dry_run must be true")
        if data.get("trigger") not in ALLOWED_PIPELINE_TRIGGERS:
            errors.append(f"pipeline_run.trigger invalid: {data.get('trigger')!r}")
        draft = data.get("draft_delivery", {})
        if not isinstance(draft, dict):
            errors.append("pipeline_run.draft_delivery must be object")
        else:
            if draft.get("mode") != "draft_only":
                errors.append("pipeline_run.draft_delivery.mode must be draft_only")
            if draft.get("requires_human_approval") is not True:
                errors.append("pipeline_run.draft_delivery.requires_human_approval must be true")
            if draft.get("external_delivery_sent") is not False:
                errors.append("pipeline_run.draft_delivery.external_delivery_sent must be false")
        boundary = data.get("runtime_boundary", {})
        if not isinstance(boundary, dict):
            errors.append("pipeline_run.runtime_boundary must be object")
        else:
            expected_false = (
                "codex_runtime_used",
                "real_openrouter_call_executed",
                "canary_real_call_executed",
                "network_request_sent",
                "api_key_read",
                "email_sent",
                "webhook_sent",
            )
            for key in expected_false:
                if boundary.get(key) is not False:
                    errors.append(f"pipeline_run.runtime_boundary.{key} must be false")
            if boundary.get("openrouter_only") is not True:
                errors.append("pipeline_run.runtime_boundary.openrouter_only must be true")
        artifacts = data.get("artifacts", {})
        if not isinstance(artifacts, dict):
            errors.append("pipeline_run.artifacts must be object")
        else:
            if not artifacts.get("brief_json"):
                errors.append("pipeline_run.artifacts.brief_json missing")
            if not artifacts.get("brief_markdown"):
                errors.append("pipeline_run.artifacts.brief_markdown missing")

    if schema.get("title") == "CNIDraftArtifact":
        _check_no_secret_like(data, errors, "draft_artifact")
        if data.get("artifact_type") not in ALLOWED_DRAFT_ARTIFACT_TYPES:
            errors.append(f"draft_artifact.artifact_type invalid: {data.get('artifact_type')!r}")
        if data.get("draft_only") is not True:
            errors.append("draft_artifact.draft_only must be true")
        if data.get("requires_human_approval") is not True:
            errors.append("draft_artifact.requires_human_approval must be true")
        if data.get("external_delivery_sent") is not False:
            errors.append("draft_artifact.external_delivery_sent must be false")

    if schema.get("title") == "ZYWEmailDraft":
        _check_no_secret_values(data, errors, "email_draft")
        if data.get("draft_only") is not True:
            errors.append("email_draft.draft_only must be true")
        if data.get("requires_human_approval") is not True:
            errors.append("email_draft.requires_human_approval must be true")
        if data.get("external_delivery_sent") is not False:
            errors.append("email_draft.external_delivery_sent must be false")
        transport = data.get("transport", {})
        if not isinstance(transport, dict):
            errors.append("email_draft.transport must be object")
        else:
            if transport.get("mode") != "local_artifact_only":
                errors.append("email_draft.transport.mode must be local_artifact_only")
            for key in ("smtp_used", "sendmail_used", "webhook_used", "network_used"):
                if transport.get(key) is not False:
                    errors.append(f"email_draft.transport.{key} must be false")
        approval = data.get("approval", {})
        if not isinstance(approval, dict):
            errors.append("email_draft.approval must be object")
        else:
            if approval.get("approval_required") is not True:
                errors.append("email_draft.approval.approval_required must be true")
            if approval.get("approved") is not False:
                errors.append("email_draft.approval.approved must be false")
        redaction = data.get("redaction", {})
        if not isinstance(redaction, dict):
            errors.append("email_draft.redaction must be object")
        else:
            for key in ("contains_api_key", "contains_token", "contains_secret", "contains_authorization", "contains_env"):
                if redaction.get(key) is not False:
                    errors.append(f"email_draft.redaction.{key} must be false")
        boundary = data.get("runtime_boundary", {})
        if not isinstance(boundary, dict):
            errors.append("email_draft.runtime_boundary must be object")
        else:
            for key in ("email_sent", "webhook_sent", "network_request_sent", "codex_runtime_used", "real_openrouter_call_executed"):
                if boundary.get(key) is not False:
                    errors.append(f"email_draft.runtime_boundary.{key} must be false")

    if schema.get("title") == "ZYWEmailHumanApproval":
        _check_no_secret_values(data, errors, "human_approval")
        if data.get("approval_required") is not True:
            errors.append("human_approval.approval_required must be true")
        if data.get("approved") is not False:
            errors.append("human_approval.approved must be false")
        if data.get("approval_decision") not in ALLOWED_APPROVAL_DECISIONS:
            errors.append(f"human_approval.approval_decision invalid: {data.get('approval_decision')!r}")
        if data.get("approval_decision") != "pending":
            errors.append("human_approval.approval_decision must default to pending")

    if schema.get("title") == "ZYWPreSendReview":
        _check_no_secret_values(data, errors, "pre_send_review")
        if data.get("dry_run") is not True:
            errors.append("pre_send_review.dry_run must be true")
        if data.get("overall_decision") not in ALLOWED_PRE_SEND_DECISIONS:
            errors.append(f"pre_send_review.overall_decision invalid: {data.get('overall_decision')!r}")
        approval = data.get("approval_state", {})
        if not isinstance(approval, dict):
            errors.append("pre_send_review.approval_state must be object")
        else:
            if approval.get("approval_required") is not True:
                errors.append("pre_send_review.approval_state.approval_required must be true")
            if approval.get("approved") is not False:
                errors.append("pre_send_review.approval_state.approved must be false")
            if approval.get("approval_decision") != "pending":
                errors.append("pre_send_review.approval_state.approval_decision must be pending")
        boundary = data.get("runtime_boundary", {})
        if not isinstance(boundary, dict):
            errors.append("pre_send_review.runtime_boundary must be object")
        else:
            for key in ("codex_runtime_used", "model_called", "real_openrouter_call_executed", "network_request_sent", "email_sent", "webhook_sent"):
                if boundary.get(key) is not False:
                    errors.append(f"pre_send_review.runtime_boundary.{key} must be false")
        redaction = data.get("redaction", {})
        if not isinstance(redaction, dict):
            errors.append("pre_send_review.redaction must be object")
        else:
            for key in ("contains_api_key", "contains_token", "contains_secret", "contains_authorization", "contains_env", "contains_raw_source_body"):
                if redaction.get(key) is not False:
                    errors.append(f"pre_send_review.redaction.{key} must be false")
        for container_name in ("reviewer_panel", "hard_rule_violations"):
            container = data.get(container_name, [])
            if not isinstance(container, list):
                errors.append(f"pre_send_review.{container_name} must be array")
                continue
            for index, item in enumerate(container):
                if not isinstance(item, dict):
                    errors.append(f"pre_send_review.{container_name}[{index}] must be object")
                    continue
                severity = item.get("severity")
                if severity is not None and severity not in ALLOWED_CRITIC_SEVERITIES:
                    errors.append(f"pre_send_review.{container_name}[{index}].severity invalid: {severity!r}")
                for finding_index, finding in enumerate(item.get("findings") or []):
                    if isinstance(finding, dict) and finding.get("severity") not in ALLOWED_CRITIC_SEVERITIES:
                        errors.append(f"pre_send_review.{container_name}[{index}].findings[{finding_index}].severity invalid: {finding.get('severity')!r}")

    return errors


def _check_no_secret_like(value: Any, errors: List[str], path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"api_key", "token", "secret", "authorization"}:
                errors.append(f"{path}.{key} must not contain secret-like keys")
            _check_no_secret_like(item, errors, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_no_secret_like(item, errors, f"{path}[{index}]")
    elif isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path} contains possible secret-like string")


def _check_no_forbidden_canary_payload(value: Any, errors: List[str], path: str) -> None:
    forbidden_exact = {"messages", "body", "content", "reasoning", "reasoning_details", "headers", "authorization"}
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in forbidden_exact:
                errors.append(f"{path}.{key} must not contain raw canary payload or model output")
            _check_no_forbidden_canary_payload(item, errors, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_no_forbidden_canary_payload(item, errors, f"{path}[{index}]")
    elif isinstance(value, str):
        if "Authorization" in value or "Bearer " in value:
            errors.append(f"{path} contains forbidden authorization marker")


def _check_no_forbidden_pipeline_canary_payload(value: Any, errors: List[str], path: str) -> None:
    forbidden_exact = {"messages", "body", "content", "reasoning", "reasoning_details", "headers", "authorization"}
    allowed_redacted = {"messages_sha256", "messages_redacted", "content_sha256", "content_length", "content_redacted", "reasoning_sha256", "reasoning_length", "reasoning_redacted", "reasoning_details_sha256", "reasoning_details_length", "reasoning_details_redacted"}
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in forbidden_exact and lowered not in allowed_redacted:
                errors.append(f"{path}.{key} must not contain raw pipeline canary payload")
            _check_no_forbidden_pipeline_canary_payload(item, errors, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_no_forbidden_pipeline_canary_payload(item, errors, f"{path}[{index}]")
    elif isinstance(value, str):
        if "Authorization" in value or "Bearer " in value:
            errors.append(f"{path} contains forbidden authorization marker")


def _check_no_secret_values(value: Any, errors: List[str], path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _check_no_secret_values(item, errors, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_no_secret_values(item, errors, f"{path}[{index}]")
    elif isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path} contains possible secret-like string")


def validate_json(data: Dict[str, Any], schema_path: str | Path) -> bool:
    schema = load_schema(schema_path)
    errors = _minimal_validate(data, schema)
    if errors:
        raise SchemaValidationError(errors)
    return True
