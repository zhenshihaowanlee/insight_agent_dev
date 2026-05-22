from __future__ import annotations

from typing import Any, Dict


ACTION_ORDER = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}


def compute_weighted_score(score_obj: Dict[str, Any]) -> float:
    total = 0.0
    for key, value in score_obj.items():
        if key in {"total_score", "score_explanation"} or not isinstance(value, dict):
            continue
        score = value.get("score")
        weight = value.get("weight")
        if isinstance(score, (int, float)) and not isinstance(score, bool) and isinstance(weight, (int, float)) and not isinstance(weight, bool):
            total += float(score)
    return round(total, 2)


def validate_score_consistency(score_obj: Dict[str, Any]) -> Dict[str, Any]:
    declared = score_obj.get("total_score")
    computed = compute_weighted_score(score_obj)
    valid_total = isinstance(declared, (int, float)) and not isinstance(declared, bool) and 0 <= float(declared) <= 100
    mismatch = bool(valid_total and abs(float(declared) - computed) > 1.0)
    return {
        "declared_total_score": float(declared) if valid_total else None,
        "computed_component_sum": computed,
        "score_total_valid": valid_total,
        "score_total_mismatch": mismatch,
        "delta": round(float(declared) - computed, 2) if valid_total else None,
    }


def map_score_to_action(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def compare_score_action(score: float, recommended_action: Any) -> Dict[str, Any]:
    action = str(recommended_action or "").strip().upper()[:1]
    suggested = map_score_to_action(float(score))
    mismatch = action in ACTION_ORDER and abs(ACTION_ORDER[suggested] - ACTION_ORDER[action]) > 1
    return {
        "recommended_action": action or None,
        "score_suggested_action": suggested,
        "score_action_mismatch": mismatch,
        "guardrail_adjusted_action": action if mismatch else None,
        "downgrade_reason_required": bool(mismatch and ACTION_ORDER.get(action, 0) < ACTION_ORDER.get(suggested, 0)),
    }
