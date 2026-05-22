from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List

from .schema_validation import NETWORK_IMPACT_KEYS, validate_json
from .score_consistency import compare_score_action, compute_weighted_score, validate_score_consistency


CANONICAL_CNI_KEYS = [
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

DEPRECATED_FIELDS = {
    "analysis_mode",
    "analysis_scope",
    "triage_summary",
    "quality_gate_results",
    "guardrail_notes",
    "model_patch_assembly",
}


def _audit(field: str, before: Any, after: Any, rule: str) -> Dict[str, Any]:
    return {
        "field": field,
        "before": before,
        "after": after,
        "rule": rule,
    }


def _has_megascale_title(analysis: Dict[str, Any]) -> bool:
    return "megascale-infer" in str(analysis.get("title", "")).lower()


def fix_model_provenance(analysis: Dict[str, Any], run_audit: Dict[str, Any] | None = None) -> Dict[str, Any]:
    run_audit = run_audit or {}
    real_call = bool(run_audit.get("actual_input_tokens") or run_audit.get("model_cni_schema_valid"))
    guardrail_notes = [
        note
        for note in analysis.get("guardrail_notes", [])
        if "No model call was made" not in str(note) and "No network access was used" not in str(note)
    ]
    return {
        "analysis_mode": "model_backed_full_text_limited_analysis" if real_call else "deterministic_review_only",
        "model_backed": real_call,
        "real_call_executed": real_call,
        "analysis_level": "full_text_limited_analysis",
        "normalization_applied": bool(run_audit.get("normalization_applied")),
        "model_patch_assembly_applied": bool(analysis.get("model_patch_assembly")),
        "actual_input_tokens": run_audit.get("actual_input_tokens"),
        "actual_output_tokens": run_audit.get("actual_output_tokens"),
        "source_analysis_id": analysis.get("analysis_id"),
        "guardrail_notes": guardrail_notes,
    }


def normalize_domain(analysis: Dict[str, Any]) -> Dict[str, Any]:
    original = analysis.get("domain")
    if _has_megascale_title(analysis):
        related = []
        if original and str(original).lower() not in {"ai cluster networking", "distributed inference", "datacenter systems"}:
            related.append(original)
        return {
            "primary_domain": "AI cluster networking",
            "secondary_domains": ["distributed inference", "GPU communication", "datacenter systems", "MoE serving"],
            "related_domains": related,
        }
    return {
        "primary_domain": original or "unknown",
        "secondary_domains": [],
        "related_domains": [],
    }


def normalize_risk_flags(analysis: Dict[str, Any]) -> Dict[str, Any]:
    source_tier = analysis.get("source_tier")
    source_type = analysis.get("source_type")
    flags = [str(item) for item in analysis.get("risk_flags", [])]
    replacements: List[str] = []
    if "vendor_claim" in flags and source_tier == "A" and source_type in {"paper", "pdf_text"}:
        flags = [item for item in flags if item != "vendor_claim"]
        replacements.append("vendor_claim_removed_for_a_tier_paper")
    for item in [
        "deployment_claim_requires_validation",
        "failure_analysis_missing",
        "security_analysis_missing",
        "operations_evidence_incomplete",
        "reproducibility_incomplete",
    ]:
        if item not in flags:
            flags.append(item)
    return {"risk_flags": flags, "risk_flag_audit": replacements}


def normalize_score_consistency(analysis: Dict[str, Any]) -> Dict[str, Any]:
    score = copy.deepcopy(analysis.get("score") or {})
    consistency = validate_score_consistency(score)
    computed = consistency["computed_component_sum"]
    declared = consistency["declared_total_score"]
    if consistency["score_total_mismatch"] and declared is not None:
        score["declared_total_score_before_canonicalization"] = declared
        score["component_sum_score"] = computed
        score["score_consistency_warning"] = "declared total does not match component sum; keeping declared model score and exposing audit"
    return {"score": score, "score_consistency": consistency}


def normalize_recommended_action(analysis: Dict[str, Any]) -> Dict[str, Any]:
    score = analysis.get("score") or {}
    total = score.get("total_score")
    total = float(total) if isinstance(total, (int, float)) and not isinstance(total, bool) else compute_weighted_score(score)
    comparison = compare_score_action(total, analysis.get("recommended_action"))
    action = {
        "recommended_action": str(analysis.get("recommended_action") or "").strip().upper()[:1] or "C",
        "score_suggested_action": comparison["score_suggested_action"],
        "score_action_mismatch": comparison["score_action_mismatch"],
        "guardrail_adjusted_action": comparison["guardrail_adjusted_action"],
        "downgrade_reason": "Evidence gaps in failure analysis, security, operations, and independent reproducibility justify a more conservative action than the score alone suggests."
        if comparison["downgrade_reason_required"]
        else None,
    }
    return {"action": action, "action_consistency": comparison}


def normalize_network_impact_direction(analysis: Dict[str, Any]) -> Dict[str, Any]:
    vector = copy.deepcopy(analysis.get("network_impact_vector") or {})
    audit: List[Dict[str, Any]] = []
    cost_power = vector.get("cost_power")
    if isinstance(cost_power, dict):
        evidence = str(cost_power.get("evidence", "")).lower()
        before = cost_power.get("impact")
        if before == "--" and any(term in evidence for term in ("cost reduction", "reduced cost", "lower cost", "cost-effective")):
            cost_power["impact"] = "+"
            cost_power["metric_direction"] = "improvement_positive"
            audit.append(_audit("network_impact_vector.cost_power.impact", before, "+", "cost reduction evidence should map to positive impact when metric direction is improvement_positive"))
        else:
            cost_power.setdefault("metric_direction", "improvement_positive")
        vector["cost_power"] = cost_power
    for key in NETWORK_IMPACT_KEYS:
        vector.setdefault(key, {"impact": "?", "evidence": "insufficient evidence", "risk": "insufficient evidence"})
    return {"network_impact_vector": vector, "network_impact_audit": audit}


def remove_or_mark_deprecated_fields(analysis: Dict[str, Any]) -> Dict[str, Any]:
    deprecated = {key: analysis.get(key) for key in sorted(DEPRECATED_FIELDS) if key in analysis}
    return {"deprecated_fields": deprecated}


def canonicalize_full_paper_analysis(analysis: Dict[str, Any], run_audit: Dict[str, Any] | None = None) -> Dict[str, Any]:
    run_audit = run_audit or {}
    consistency_audit: List[Dict[str, Any]] = []
    provenance = fix_model_provenance(analysis, run_audit)
    domains = normalize_domain(analysis)
    if analysis.get("domain") != domains["primary_domain"]:
        consistency_audit.append(_audit("domain", analysis.get("domain"), domains["primary_domain"], "MegaScale-Infer canonical domain"))
    risk = normalize_risk_flags(analysis)
    if risk.get("risk_flag_audit"):
        consistency_audit.append(_audit("risk_flags", analysis.get("risk_flags"), risk["risk_flags"], "A-tier paper risk flag normalization"))
    score = normalize_score_consistency(analysis)
    if score["score_consistency"]["score_total_mismatch"]:
        consistency_audit.append(_audit("score.total_score", score["score_consistency"]["computed_component_sum"], score["score_consistency"]["declared_total_score"], "declared total and component sum mismatch exposed"))
    action = normalize_recommended_action(analysis)
    if action["action"]["score_action_mismatch"]:
        consistency_audit.append(_audit("recommended_action", analysis.get("recommended_action"), action["action"], "score/action mismatch exposed with guardrail action"))
    network = normalize_network_impact_direction(analysis)
    consistency_audit.extend(network["network_impact_audit"])
    deprecated = remove_or_mark_deprecated_fields(analysis)

    cni_sections = {key: copy.deepcopy(analysis.get(key, {"status": "missing"})) for key in CANONICAL_CNI_KEYS if key not in {"network_impact_vector", "score", "recommended_action"}}
    canonical = {
        "canonical_analysis_id": "canonical-" + hashlib.sha256(str(analysis.get("analysis_id", analysis.get("title", ""))).encode("utf-8")).hexdigest()[:16],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "analysis_id": analysis.get("analysis_id"),
            "source_id": analysis.get("source_id"),
            "title": analysis.get("title"),
            "source_tier": analysis.get("source_tier"),
            "source_type": analysis.get("source_type"),
            "body_is_untrusted": bool(analysis.get("body_is_untrusted", True)),
        },
        "provenance": provenance,
        "domains": domains,
        "risk_flags": risk["risk_flags"],
        "cni_sections": cni_sections,
        "network_impact_vector": network["network_impact_vector"],
        "evidence_quality": analysis.get("evidence_quality", {}),
        "score": score["score"],
        "action": action["action"],
        "consistency_audit": consistency_audit,
        "deprecated_fields": deprecated["deprecated_fields"],
        "validation": {
            "canonical_schema_valid": True,
            "score_consistency": score["score_consistency"],
            "action_consistency": action["action_consistency"],
            "ready_for_three_paper_cross_validation": False,
            "readiness_blockers": [],
        },
        "artifact_paths": {},
    }
    blockers: List[str] = []
    if score["score_consistency"]["score_total_mismatch"]:
        blockers.append("score_total_mismatch_requires_human_review")
    if action["action"]["score_action_mismatch"]:
        blockers.append("score_action_mismatch_requires_human_review")
    if provenance["model_patch_assembly_applied"]:
        blockers.append("model_patch_assembly_provenance_requires_review")
    canonical["validation"]["readiness_blockers"] = blockers
    canonical["validation"]["ready_for_three_paper_cross_validation"] = not blockers
    validate_json(canonical, "canonical_full_paper_analysis")
    return canonical
