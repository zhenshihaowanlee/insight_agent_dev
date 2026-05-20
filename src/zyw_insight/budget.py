from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


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
    "baseline_rigorous": {"input_m": 48.0, "output_m": 10.5},
    "heavy": {"input_m": 105.0, "output_m": 20.0},
}


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
