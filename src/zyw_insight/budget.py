from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class ModelPrice:
    """Model token price in USD per 1M tokens."""

    input_per_m: float
    output_per_m: float


MODEL_PRICES: Dict[str, ModelPrice] = {
    "gpt-5.4-nano": ModelPrice(0.20, 1.25),
    "gpt-5.4-mini": ModelPrice(0.75, 4.50),
    "gemini-2.5-pro": ModelPrice(1.25, 10.00),
    "gpt-5.4": ModelPrice(2.50, 15.00),
    "claude-sonnet-4.6": ModelPrice(3.00, 15.00),
    "claude-opus-4.7": ModelPrice(5.00, 25.00),
    "gpt-5.5": ModelPrice(5.00, 30.00),
    "gpt-5.5-pro": ModelPrice(30.00, 180.00),
}

SCENARIOS = {
    "poc": {"input_m": 8.0, "output_m": 1.8},
    "baseline_efficient": {"input_m": 33.0, "output_m": 7.0},
    "baseline_strict": {"input_m": 48.0, "output_m": 10.5},
    "baseline_rigorous": {"input_m": 48.0, "output_m": 10.5},
    "heavy": {"input_m": 105.0, "output_m": 20.0},
}

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
STAGES = ("triage", "literature_analysis", "constraint_critic", "brief_synthesis", "final_review")
FORBIDDEN_PROVIDER_TERMS = ("codex", "coding-agent", "coding_agent", "oauth", "@openai/codex")


def estimate_single_model_cost(model: str, input_m: float, output_m: float, platform_fee_rate: float = 0.055) -> float:
    """Estimate monthly cost for a single model.

    Args:
        model: Key in MODEL_PRICES.
        input_m: Input tokens in millions.
        output_m: Output tokens in millions.
        platform_fee_rate: Platform fee, default 5.5%.

    Returns:
        Cost in USD.
    """
    if model not in MODEL_PRICES:
        raise KeyError(f"Unknown model price key: {model}")
    price = MODEL_PRICES[model]
    raw = input_m * price.input_per_m + output_m * price.output_per_m
    return raw * (1 + platform_fee_rate)


def estimate_scenario(model: str, scenario: str) -> float:
    """Estimate a scenario cost for a single-model baseline."""
    if scenario not in SCENARIOS:
        raise KeyError(f"Unknown scenario: {scenario}")
    s = SCENARIOS[scenario]
    return estimate_single_model_cost(model, s["input_m"], s["output_m"])


def budget_mode(spend_usd: float, soft_limit_usd: float = 300.0, hard_limit_usd: float = 400.0) -> str:
    """Return budget operating mode for current spend."""
    if spend_usd >= hard_limit_usd:
        return "stop_auto_deep_analysis"
    if spend_usd >= soft_limit_usd:
        return "high_restriction"
    if spend_usd >= soft_limit_usd * 0.9:
        return "restrict_to_a_rank_and_manual"
    if spend_usd >= soft_limit_usd * 0.7:
        return "reduce_reasoning_and_critic_scope"
    return "normal"


def load_budget_policy(path_or_environment: str | Path) -> Dict[str, Any]:
    path = Path(path_or_environment)
    if not path.suffix and not path.exists():
        path = CONFIG_DIR / f"budget.{path_or_environment}.json"
    elif not path.is_absolute():
        path = ROOT / path
    with path.open("r", encoding="utf-8") as f:
        policy = json.load(f)
    validate_budget_policy(policy)
    return policy


def _iter_model_ids(policy: Dict[str, Any]):
    for stage_policy in (policy.get("stage_policies") or {}).values():
        for key in ("preferred_model", "fallback_model"):
            value = stage_policy.get(key)
            if isinstance(value, str):
                yield value


def validate_budget_policy(policy: Dict[str, Any]) -> bool:
    required = {
        "policy_id",
        "name",
        "environment",
        "monthly_budget_usd",
        "soft_cap_usd",
        "hard_cap_usd",
        "daily_document_limit",
        "monthly_document_limit",
        "default_brief_interval_hours",
        "quality_priority",
        "stage_policies",
        "priority_allocation",
        "downgrade_rules",
        "alert_thresholds",
        "delivery_policy",
        "provider_policy",
    }
    missing = required - set(policy)
    if missing:
        raise ValueError(f"budget policy missing: {', '.join(sorted(missing))}")
    stage_policies = policy.get("stage_policies") or {}
    for stage in STAGES:
        if stage not in stage_policies:
            raise ValueError(f"budget policy missing stage: {stage}")
        for key in (
            "preferred_model",
            "fallback_model",
            "max_input_tokens_per_item",
            "max_output_tokens_per_item",
            "reasoning_level",
            "retry_limit",
            "cache_eligible",
            "manual_only",
            "quality_floor",
        ):
            if key not in stage_policies[stage]:
                raise ValueError(f"budget policy stage {stage} missing {key}")
    if policy["soft_cap_usd"] > policy["hard_cap_usd"]:
        raise ValueError("soft_cap_usd must not exceed hard_cap_usd")
    provider = policy.get("provider_policy") or {}
    if provider.get("allowed_provider_prefixes") != ["openrouter/"]:
        raise ValueError("allowed provider prefixes must be only openrouter/")
    forbidden = set(provider.get("forbidden_provider_terms") or [])
    for term in ("codex", "coding-agent", "oauth", "@openai/codex"):
        if term not in forbidden:
            raise ValueError(f"forbidden provider term missing: {term}")
    for model_id in _iter_model_ids(policy):
        lowered = model_id.lower()
        if not model_id.startswith("openrouter/"):
            raise ValueError(f"model id must start with openrouter/: {model_id}")
        if any(term in lowered for term in FORBIDDEN_PROVIDER_TERMS):
            raise ValueError(f"forbidden provider term in model id: {model_id}")
    delivery = policy.get("delivery_policy") or {}
    if delivery.get("draft_only") is not True or delivery.get("requires_human_approval") is not True:
        raise ValueError("delivery policy must be draft-only and require human approval")
    if (policy.get("stage_policies") or {}).get("final_review", {}).get("manual_only") is not True:
        raise ValueError("final_review must be manual_only")
    return True


def estimate_stage_cost(
    input_tokens: int | float,
    output_tokens: int | float,
    input_price_per_m: float,
    output_price_per_m: float,
    platform_fee: float = 0.055,
) -> float:
    raw = (float(input_tokens) / 1_000_000.0) * input_price_per_m + (float(output_tokens) / 1_000_000.0) * output_price_per_m
    return raw * (1 + platform_fee)


def resolve_audit_cost(actual_cost_usd: float | None, estimated_cost_usd: float | None) -> Dict[str, Any]:
    if actual_cost_usd is None:
        return {
            "audit_cost_usd": estimated_cost_usd,
            "actual_cost_source": "estimated_fallback",
        }
    return {
        "audit_cost_usd": actual_cost_usd,
        "actual_cost_source": "openrouter_usage",
    }


def estimate_monthly_cost(scenario: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    if scenario not in SCENARIOS:
        raise KeyError(f"Unknown scenario: {scenario}")
    s = SCENARIOS[scenario]
    input_tokens = s["input_m"] * 1_000_000
    output_tokens = s["output_m"] * 1_000_000
    # Conservative quality-first placeholder blend: long-context analysis + reasoning critic + brief synthesis.
    estimated = (
        estimate_stage_cost(input_tokens * 0.60, output_tokens * 0.55, 1.25, 10.0)
        + estimate_stage_cost(input_tokens * 0.25, output_tokens * 0.30, 2.5, 15.0)
        + estimate_stage_cost(input_tokens * 0.15, output_tokens * 0.15, 3.0, 15.0)
    )
    status = get_budget_status(estimated, policy)
    return {
        "policy_id": policy["policy_id"],
        "environment": policy["environment"],
        "scenario": scenario,
        "estimated_monthly_cost_usd": round(estimated, 2),
        "monthly_budget_usd": policy["monthly_budget_usd"],
        "soft_cap_usd": policy["soft_cap_usd"],
        "hard_cap_usd": policy["hard_cap_usd"],
        "budget_status": status,
        "quality_priority": policy["quality_priority"],
    }


def estimate_document_cost(
    source_item: Dict[str, Any],
    triage_result: Dict[str, Any] | None = None,
    analysis: Dict[str, Any] | None = None,
    critic: Dict[str, Any] | None = None,
    policy: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    policy = policy or load_budget_policy("quality_first")
    body = str(source_item.get("body", ""))
    rough_input_tokens = max(500, len(body) // 4)
    priority = (triage_result or {}).get("deep_read_priority", "Medium")
    multiplier = 1.25 if priority == "High" else 0.75 if priority == "Low" else 1.0
    total = 0.0
    details = []
    for stage in ("triage", "literature_analysis", "constraint_critic"):
        stage_policy = policy["stage_policies"][stage]
        input_tokens = min(int(rough_input_tokens * multiplier), stage_policy["max_input_tokens_per_item"])
        output_tokens = min(stage_policy["max_output_tokens_per_item"], 1000 if stage == "triage" else 6000)
        cost = estimate_stage_cost(input_tokens, output_tokens, 1.25, 10.0)
        total += cost
        details.append({"stage": stage, "estimated_cost_usd": round(cost, 4)})
    return {"source_id": source_item.get("source_id", "unknown"), "estimated_cost_usd": round(total, 4), "stages": details}


def get_budget_status(spent_usd: float, policy: Dict[str, Any]) -> str:
    spent = float(spent_usd)
    soft = float(policy["soft_cap_usd"])
    hard = float(policy["hard_cap_usd"])
    if spent >= hard:
        return "hard_stop"
    if spent >= soft:
        return "stop_100"
    if spent >= soft * 0.90:
        return "degrade_90"
    if spent >= soft * 0.80:
        return "reduce_volume_80"
    if spent >= soft * 0.70:
        return "watch_70"
    return "ok"


def should_degrade_model(spent_usd: float, policy: Dict[str, Any]) -> bool:
    return get_budget_status(spent_usd, policy) in {"degrade_90", "stop_100", "hard_stop"}


def should_reduce_volume(spent_usd: float, policy: Dict[str, Any]) -> bool:
    return get_budget_status(spent_usd, policy) in {"reduce_volume_80", "degrade_90", "stop_100", "hard_stop"}


def _is_low_priority(triage_result: Dict[str, Any] | None) -> bool:
    triage_result = triage_result or {}
    return triage_result.get("source_tier") in {"C", "D"} or triage_result.get("deep_read_priority") == "Low"


def _is_quality_preserved(triage_result: Dict[str, Any] | None, policy: Dict[str, Any]) -> bool:
    triage_result = triage_result or {}
    allocation = policy.get("priority_allocation") or {}
    return triage_result.get("source_tier") in set(allocation.get("preserve_quality_for_source_tiers") or []) or triage_result.get("deep_read_priority") in set(allocation.get("preserve_quality_for_deep_read_priority") or [])


def should_skip_low_priority(spent_usd: float, policy: Dict[str, Any], triage_result: Dict[str, Any] | None = None) -> bool:
    status = get_budget_status(spent_usd, policy)
    return status in {"degrade_90", "stop_100", "hard_stop"} and _is_low_priority(triage_result)


def should_stop_processing(spent_usd: float, policy: Dict[str, Any]) -> bool:
    return get_budget_status(spent_usd, policy) in {"stop_100", "hard_stop"}


def should_require_manual_review(stage: str, estimated_cost: float, policy: Dict[str, Any], reason_flags: list[str] | None = None) -> bool:
    if (policy.get("stage_policies") or {}).get(stage, {}).get("manual_only") is True:
        return True
    if estimated_cost >= max(10.0, policy["monthly_budget_usd"] * 0.05):
        return True
    return bool(set(reason_flags or []) & {"premium_model", "hard_stop_override", "production_delivery"})


def recommend_budget_action(spent_usd: float, estimated_next_cost: float, policy: Dict[str, Any], triage_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    next_spend = spent_usd + estimated_next_cost
    status = get_budget_status(next_spend, policy)
    preserved = _is_quality_preserved(triage_result, policy)
    low = _is_low_priority(triage_result)
    action = "process"
    if status == "hard_stop":
        action = "hard_stop"
    elif status == "stop_100":
        action = "manual_only_for_high_value" if preserved else "stop_nonessential"
    elif status == "degrade_90":
        action = "preserve_quality_reduce_other_volume" if preserved else "fallback_or_skip"
    elif status == "reduce_volume_80":
        action = "reduce_low_priority_volume" if low else "process_with_budget_warning"
    elif status == "watch_70":
        action = "watch"
    return {
        "budget_status": status,
        "recommended_action": action,
        "quality_preserved": preserved,
        "volume_reduction_recommended": should_reduce_volume(next_spend, policy),
        "manual_review_required": should_require_manual_review("final_review", estimated_next_cost, policy, []),
    }
