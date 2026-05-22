from __future__ import annotations

import copy
import re
from typing import Any, Dict

from .schema_validation import SchemaValidationError, validate_json


CNI_TOP_LEVEL_KEYS = [
    "basic_info",
    "one_sentence_conclusion",
    "problem_background",
    "core_idea",
    "contributions",
    "mechanism",
    "process_constraints",
    "constraint_dependency_analysis",
    "degraded_process_counterfactual",
    "network_impact_vector",
    "evidence_quality",
    "comparison_with_existing_technology",
    "hidden_assumptions_and_risks",
    "security_and_operations_impact",
    "reproducibility",
    "technical_insights",
    "strategic_significance",
    "score",
    "recommended_action",
    "follow_up_validation_experiments",
]
NETWORK_KEYS = [
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


def _short_repr(value: Any, limit: int = 120) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _audit(audit: list[Dict[str, Any]], field: str, before: Any, after: Any, rule: str) -> None:
    audit.append(
        {
            "field": field,
            "before_type": type(before).__name__,
            "after_type": type(after).__name__,
            "before_repr_redacted_or_short": _short_repr(before),
            "rule": rule,
        }
    )


def _coerce_score_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if 0 <= number <= 100 else None
    if isinstance(value, str):
        stripped = value.strip()
        if re.fullmatch(r"\d+(\.\d+)?", stripped):
            number = float(stripped)
            return number if 0 <= number <= 100 else None
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*100", stripped)
        if match:
            number = float(match.group(1))
            return number if 0 <= number <= 100 else None
    return None


def normalize_score_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(data)
    audit: list[Dict[str, Any]] = result.setdefault("normalization_audit", [])
    score = result.get("score")
    if not isinstance(score, dict):
        return result

    for field in ("total_score",):
        if field not in score:
            continue
        before = score.get(field)
        after = _coerce_score_number(before)
        if after is not None and not isinstance(before, (int, float)):
            score[field] = after
            _audit(audit, f"score.{field}", before, after, "coerce_numeric_score_string")
        elif isinstance(before, int) and not isinstance(before, bool):
            score[field] = float(before)
            _audit(audit, f"score.{field}", before, score[field], "coerce_int_score_to_float")

    for key, value in list(score.items()):
        if isinstance(value, dict):
            for subkey in ("score", "weight"):
                if subkey in value:
                    before = value[subkey]
                    after = _coerce_score_number(before)
                    if after is not None and not isinstance(before, (int, float)):
                        value[subkey] = after
                        _audit(audit, f"score.{key}.{subkey}", before, after, "coerce_numeric_score_string")
    return result


def normalize_network_impact_vector(data: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(data)
    audit: list[Dict[str, Any]] = result.setdefault("normalization_audit", [])
    vector = result.get("network_impact_vector")
    if not isinstance(vector, dict):
        return result
    aliases = {"positive": "+", "negative": "-", "neutral": "0", "unknown": "?"}
    for key, item in vector.items():
        if not isinstance(item, dict) or "impact" not in item:
            continue
        before = item.get("impact")
        if before in ALLOWED_IMPACTS:
            continue
        if isinstance(before, str):
            after = aliases.get(before.strip().lower())
            if after:
                item["impact"] = after
                _audit(audit, f"network_impact_vector.{key}.impact", before, after, "coerce_unambiguous_impact_alias")
    return result


def normalize_literature_analysis_candidate(data: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(data)
    result.setdefault("normalization_audit", [])
    missing = []
    for key in CNI_TOP_LEVEL_KEYS:
        if key not in result:
            missing.append(key)
            result[key] = {"status": "missing_from_model_output", "normalization_required": True}
    result["missing_cni_top_level_sections"] = missing
    result = normalize_score_fields(result)
    result = normalize_network_impact_vector(result)
    return result


def validate_normalized_literature_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    missing = [key for key in CNI_TOP_LEVEL_KEYS if data.get(key) == {"status": "missing_from_model_output", "normalization_required": True}]
    if missing:
        return {"schema_valid": False, "errors": [f"missing CNI top-level sections: {', '.join(missing)}"], "normalization_audit": data.get("normalization_audit") or []}
    try:
        validate_json(data, "literature_analysis")
        return {"schema_valid": True, "errors": [], "normalization_audit": data.get("normalization_audit") or []}
    except SchemaValidationError as exc:
        return {"schema_valid": False, "errors": exc.errors, "normalization_audit": data.get("normalization_audit") or []}
