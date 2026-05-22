from __future__ import annotations

import copy
from typing import Any, Dict

from .schema_validation import validate_json


CNI_PATCH_KEYS = [
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
STRING_FIELDS = {
    "one_sentence_conclusion",
    "problem_background",
    "core_idea",
    "strategic_significance",
    "recommended_action",
}
LIST_FIELDS = {
    "contributions",
    "process_constraints",
    "constraint_dependency_analysis",
    "comparison_with_existing_technology",
    "hidden_assumptions_and_risks",
    "follow_up_validation_experiments",
}
DICT_FIELDS = {
    "basic_info",
    "mechanism",
    "degraded_process_counterfactual",
    "network_impact_vector",
    "evidence_quality",
    "security_and_operations_impact",
    "reproducibility",
    "technical_insights",
    "score",
}
ALLOWED_ACTIONS = {"S", "A", "B", "C", "D"}
ALLOWED_IMPACTS = {"++", "+", "0", "-", "--", "?"}


def _short(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 160 else text[:160] + "...[truncated]"


def _audit(audit: list[Dict[str, Any]], field: str, action: str, reason: str, value: Any = None) -> None:
    audit.append({"field": field, "action": action, "reason": reason, "value_preview": _short(value)})


def _patch_payload(model_json: Dict[str, Any]) -> Dict[str, Any]:
    payload = model_json.get("cni_content_patch")
    if isinstance(payload, dict):
        return payload
    return model_json


def _valid_network_vector(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for item in value.values():
        if not isinstance(item, dict):
            return False
        if item.get("impact") not in ALLOWED_IMPACTS:
            return False
        if not isinstance(item.get("evidence"), str) or not isinstance(item.get("risk"), str):
            return False
    return True


def assemble_literature_analysis_from_model_patch(base_analysis: Dict[str, Any], model_json: Dict[str, Any]) -> Dict[str, Any]:
    assembled = copy.deepcopy(base_analysis)
    patch = _patch_payload(model_json)
    audit: list[Dict[str, Any]] = []

    for key in CNI_PATCH_KEYS:
        if key not in patch:
            _audit(audit, key, "kept_base", "model patch omitted field")
            continue
        value = patch[key]
        if key in STRING_FIELDS:
            if key == "recommended_action" and value not in ALLOWED_ACTIONS:
                _audit(audit, key, "rejected", "recommended_action must be S/A/B/C/D", value)
                continue
            if isinstance(value, str):
                assembled[key] = value
                _audit(audit, key, "applied", "string field")
            else:
                _audit(audit, key, "rejected", "expected string", value)
        elif key in LIST_FIELDS:
            if isinstance(value, list):
                assembled[key] = value
                _audit(audit, key, "applied", "list field")
            else:
                _audit(audit, key, "rejected", "expected list", value)
        elif key == "network_impact_vector":
            if _valid_network_vector(value):
                merged = dict(assembled.get(key) or {})
                merged.update(value)
                assembled[key] = merged
                _audit(audit, key, "applied", "valid network impact vector patch")
            else:
                _audit(audit, key, "rejected", "invalid network impact vector", value)
        elif key == "score":
            if isinstance(value, dict) and isinstance(value.get("total_score"), (int, float)) and not isinstance(value.get("total_score"), bool):
                merged_score = dict(assembled.get("score") or {})
                for score_key, score_value in value.items():
                    if score_key == "total_score":
                        bounded = max(0.0, min(100.0, float(score_value)))
                        merged_score[score_key] = bounded
                    elif score_key == "score_explanation" and isinstance(score_value, str):
                        merged_score[score_key] = score_value
                assembled["score"] = merged_score
                _audit(audit, key, "applied", "numeric score patch")
            else:
                _audit(audit, key, "rejected", "score.total_score must be numeric", value)
        elif key in DICT_FIELDS:
            if isinstance(value, dict):
                merged = dict(assembled.get(key) or {})
                merged.update(value)
                assembled[key] = merged
                _audit(audit, key, "applied", "object field merge")
            else:
                _audit(audit, key, "rejected", "expected object", value)

    assembled.setdefault("guardrail_notes", [])
    assembled["guardrail_notes"] = list(assembled["guardrail_notes"]) + [
        "Model output was used as a bounded content patch; schema structure was assembled deterministically.",
    ]
    assembled["model_patch_assembly"] = {
        "assembly_applied": True,
        "model_patch_keys": sorted(k for k in patch.keys() if k in CNI_PATCH_KEYS),
        "audit": audit,
    }
    validate_json(assembled, "literature_analysis")
    return assembled
