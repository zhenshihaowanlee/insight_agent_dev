from __future__ import annotations

from typing import Any, Dict, List


COMMON_FIELD_KEYS = [
    "source_id",
    "title",
    "domain",
    "source_tier",
    "recommended_action",
    "score",
    "risk_flags",
    "network_impact_vector",
    "constraint_findings",
    "evidence_quality",
]


def empty_common_fields() -> Dict[str, Any]:
    return {
        "source_id": "unknown",
        "title": "unknown",
        "domain": "unknown",
        "source_tier": "unknown",
        "recommended_action": "D",
        "score": {"total_score": 0, "score_explanation": "unknown"},
        "risk_flags": [],
        "network_impact_vector": {},
        "constraint_findings": [],
        "evidence_quality": {},
    }


def common_fields_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    triage = analysis.get("triage_summary") or {}
    basic = analysis.get("basic_info") or {}
    return {
        "source_id": str(analysis.get("source_id") or basic.get("source_id") or "unknown"),
        "title": str(analysis.get("title") or basic.get("title") or "unknown"),
        "domain": str(analysis.get("domain") or triage.get("domain") or basic.get("domain") or "unknown"),
        "source_tier": str(analysis.get("source_tier") or triage.get("source_tier") or basic.get("source_tier") or "unknown"),
        "recommended_action": str(analysis.get("recommended_action", "D")),
        "score": analysis.get("score") or {"total_score": 0, "score_explanation": "missing analyzer score"},
        "risk_flags": list(analysis.get("risk_flags") or triage.get("risk_flags") or []),
        "network_impact_vector": analysis.get("network_impact_vector") or {},
        "constraint_findings": list(analysis.get("constraint_findings") or analysis.get("process_constraints") or analysis.get("constraints") or []),
        "evidence_quality": analysis.get("evidence_quality") or {},
    }


def common_fields_from_critic(critic: Dict[str, Any], analysis: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base = common_fields_from_analysis(analysis) if analysis else empty_common_fields()
    base.update(
        {
            "source_id": str(critic.get("source_id") or base["source_id"]),
            "title": str(critic.get("title") or base["title"]),
            "domain": str(critic.get("domain") or base["domain"]),
            "source_tier": str(critic.get("source_tier") or base["source_tier"]),
            "recommended_action": str(critic.get("recommended_action") or critic.get("recommended_action_after") or base["recommended_action"]),
            "score": critic.get("score") or critic.get("score_after") or base["score"],
            "risk_flags": list(critic.get("risk_flags") or base["risk_flags"]),
            "network_impact_vector": critic.get("network_impact_vector") or base["network_impact_vector"],
            "constraint_findings": list(critic.get("constraint_findings") or base["constraint_findings"]),
            "evidence_quality": critic.get("evidence_quality") or base["evidence_quality"],
        }
    )
    return base


def common_fields_from_any(item: Dict[str, Any]) -> Dict[str, Any]:
    if "critic" in item and isinstance(item.get("critic"), dict):
        analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else None
        return common_fields_from_critic(item["critic"], analysis)
    if "critic_id" in item:
        return common_fields_from_critic(item)
    return common_fields_from_analysis(item)


def missing_common_fields(item: Dict[str, Any]) -> List[str]:
    return [key for key in COMMON_FIELD_KEYS if key not in item]
