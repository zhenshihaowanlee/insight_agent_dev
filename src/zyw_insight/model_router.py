from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .budget import get_budget_status, load_budget_policy, should_reduce_volume, should_skip_low_priority


FORBIDDEN_MODEL_MARKERS = ("codex", "coding-agent", "coding_agent", "oauth", "@openai/codex")


@dataclass(frozen=True)
class ModelRequest:
    stage: str
    prompt: str
    budget_tier: str = "poc"
    metadata: Dict[str, Any] | None = None


@dataclass(frozen=True)
class ModelResponse:
    model: str
    content: str
    usage: Dict[str, Any]
    mocked: bool = True


MODEL_PLACEHOLDERS = {
    "triage": "openrouter/low-cost-triage-placeholder",
    "literature_analysis": "openrouter/long-context-analysis-placeholder",
    "constraint_critic": "openrouter/reasoning-critic-placeholder",
    "brief_synthesis": "openrouter/high-quality-brief-placeholder",
    "final_review": "openrouter/premium-final-review-placeholder",
}


class RoutingDecision(dict):
    """Dict result that remains compatible with older string-style tests."""

    def startswith(self, prefix: str) -> bool:
        return str(self.get("selected_model") or self.get("fallback_model") or "").startswith(prefix)


def validate_openrouter_model_id(model_id: str) -> None:
    lowered = model_id.lower()
    if not model_id.startswith("openrouter/"):
        raise ValueError(f"model id must use OpenRouter provider: {model_id}")
    if any(marker in lowered for marker in FORBIDDEN_MODEL_MARKERS):
        raise ValueError(f"forbidden runtime model/provider marker in model id: {model_id}")


def _quality_preserved(triage_result: Dict[str, Any] | None, policy: Dict[str, Any]) -> bool:
    triage_result = triage_result or {}
    allocation = policy.get("priority_allocation") or {}
    return triage_result.get("source_tier") in set(allocation.get("preserve_quality_for_source_tiers") or []) or triage_result.get("deep_read_priority") in set(allocation.get("preserve_quality_for_deep_read_priority") or [])


def choose_model_for_stage(
    stage: str,
    budget_tier: str = "quality_first",
    spent_usd: float = 0,
    policy: Dict[str, Any] | None = None,
    triage_result: Dict[str, Any] | None = None,
    manual_override: bool = False,
) -> RoutingDecision:
    policy = policy or load_budget_policy(budget_tier)
    stage_policies = policy.get("stage_policies") or {}
    if stage not in stage_policies:
        raise ValueError(f"unknown model routing stage: {stage}")
    stage_policy = stage_policies[stage]
    preferred = stage_policy.get("preferred_model") or MODEL_PLACEHOLDERS[stage]
    fallback = stage_policy.get("fallback_model") or preferred
    validate_openrouter_model_id(preferred)
    validate_openrouter_model_id(fallback)

    budget_status = get_budget_status(spent_usd, policy)
    manual_required = stage_policy.get("manual_only") is True
    quality_preserved = _quality_preserved(triage_result, policy)
    low_priority = (triage_result or {}).get("source_tier") in {"C", "D"} or (triage_result or {}).get("deep_read_priority") == "Low"
    processing_allowed = True
    selected = preferred
    reason = "preferred model selected"
    budget_warning = None

    if budget_status == "hard_stop" and not manual_override:
        processing_allowed = False
        selected = None
        reason = "hard cap reached; processing denied without manual override"
        budget_warning = "hard_stop"
    elif manual_required and not manual_override:
        processing_allowed = False
        selected = None
        reason = "stage is manual-only"
    elif budget_status == "stop_100" and not manual_override:
        if quality_preserved:
            processing_allowed = False
            selected = None
            reason = "soft cap reached; high-value item requires manual trigger"
        else:
            processing_allowed = False
            selected = None
            reason = "soft cap reached; nonessential processing stopped"
        budget_warning = "stop_100"
    elif budget_status == "degrade_90":
        budget_warning = "degrade_90"
        if low_priority:
            selected = fallback
            reason = "90% soft-cap reached; C/D or Low priority uses fallback model"
            if should_skip_low_priority(spent_usd, policy, triage_result):
                processing_allowed = False
                selected = None
                reason = "90% soft-cap reached; low-priority processing denied"
        elif quality_preserved:
            selected = preferred
            reason = "90% soft-cap reached; quality preserved for A/B or High priority item"
    elif budget_status == "reduce_volume_80":
        budget_warning = "reduce_volume_80"
        if low_priority and policy["quality_priority"] == "high":
            processing_allowed = False
            selected = None
            reason = "80% soft-cap reached; reduce low-value volume before lowering model quality"
        elif quality_preserved:
            selected = preferred
            reason = "80% soft-cap reached; preferred model preserved for high-value item"
    elif budget_status == "watch_70":
        budget_warning = "watch_70"
        reason = "70% soft-cap reached; watch budget"

    return RoutingDecision(
        {
            "stage": stage,
            "selected_model": selected,
            "fallback_model": fallback,
            "reason": reason,
            "budget_status": budget_status,
            "manual_required": manual_required,
            "processing_allowed": processing_allowed,
            "quality_preserved": quality_preserved,
            "volume_reduction_recommended": should_reduce_volume(spent_usd, policy),
            "budget_warning": budget_warning,
        }
    )


def mock_model_call(request: ModelRequest) -> ModelResponse:
    decision = choose_model_for_stage(request.stage, request.budget_tier)
    model_id = decision["selected_model"] or decision["fallback_model"]
    return ModelResponse(model=model_id, content="", usage={"network_calls": 0, "api_key_read": False}, mocked=True)


def route_decision_to_adapter_context(decision: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "selected_model": decision.get("selected_model"),
        "fallback_model": decision.get("fallback_model"),
        "budget_status": decision.get("budget_status"),
        "manual_required": bool(decision.get("manual_required")),
        "processing_allowed": bool(decision.get("processing_allowed")),
        "quality_preserved": bool(decision.get("quality_preserved")),
        "volume_reduction_recommended": bool(decision.get("volume_reduction_recommended")),
        "budget_warning": decision.get("budget_warning"),
        "reason": decision.get("reason", ""),
    }
