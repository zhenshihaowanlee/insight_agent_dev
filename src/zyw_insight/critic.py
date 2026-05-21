from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from .common_fields import common_fields_from_analysis, common_fields_from_critic
from .quality_gates import evaluate_critic_rules


ACTION_ORDER = ["S", "A", "B", "C", "D"]
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


def _analysis_hash(analysis: Dict[str, Any]) -> str:
    encoded = json.dumps(analysis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cap_action(action: str, cap: str) -> str:
    action = action if action in ACTION_ORDER else "D"
    return action if ACTION_ORDER.index(action) >= ACTION_ORDER.index(cap) else cap


def _score_total(score: Dict[str, Any]) -> int:
    total = score.get("total_score", score.get("total", 0))
    try:
        return max(0, min(100, int(total)))
    except (TypeError, ValueError):
        return 0


def _finding(rule: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rule_id": rule["rule_id"],
        "severity": rule["severity"],
        "message": rule["message"],
        "suggested_fix": rule["suggested_fix"],
    }


def _findings_for(violations: List[Dict[str, Any]], prefixes: tuple[str, ...]) -> List[Dict[str, Any]]:
    return [_finding(rule) for rule in violations if rule["rule_id"].startswith(prefixes)]


def critique_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    common = common_fields_from_analysis(analysis)
    violations = evaluate_critic_rules(analysis)
    triage_risks = set((analysis.get("triage_summary") or {}).get("risk_flags", []))
    before_action = str(analysis.get("recommended_action", "D"))
    before_score = analysis.get("score", {}) or {}
    before_total = _score_total(before_score)

    critical_count = sum(1 for item in violations if item["severity"] == "critical")
    major_count = sum(1 for item in violations if item["severity"] == "major")
    warning_count = sum(1 for item in violations if item["severity"] == "warning")

    action_after = before_action if before_action in ACTION_ORDER else "D"
    score_cap = 100
    score_penalty = 0
    downgrade_reasons: List[str] = []

    if critical_count:
        action_after = _cap_action(action_after, "B")
        score_cap = min(score_cap, 60)
        score_penalty += 15 * critical_count
        downgrade_reasons.append("critical violation: action capped at B and score capped at 60")
    if major_count:
        action_after = _cap_action(action_after, "A")
        score_cap = min(score_cap, 70)
        score_penalty += min(20, 5 * major_count)
        downgrade_reasons.append("major violations: action capped at A and score capped at 70")
    if warning_count >= 2:
        score_penalty += min(15, 5 + warning_count * 2)
        downgrade_reasons.append("multiple warnings: score reduced")
    if {"vendor_claim", "marketing_language", "no_experiment_signal"} <= triage_risks or ({"vendor_claim", "no_experiment_signal"} <= triage_risks):
        action_after = _cap_action(action_after, "C")
        score_cap = min(score_cap, 50)
        score_penalty += 10
        downgrade_reasons.append("vendor marketing plus no experiment: action capped at C")
    if {"missing_baseline", "average_only_signal"} <= triage_risks:
        action_after = _cap_action(action_after, "B")
        score_cap = min(score_cap, 65)
        score_penalty += 8
        downgrade_reasons.append("missing baseline plus average-only signal: action capped at B")

    after_total = max(0, min(score_cap, before_total - score_penalty))
    if after_total < 55:
        action_after = _cap_action(action_after, "C")
    elif after_total < 70:
        action_after = _cap_action(action_after, "B")
    if after_total < before_total - 15 or ACTION_ORDER.index(action_after) > ACTION_ORDER.index(before_action if before_action in ACTION_ORDER else "D") + 1:
        confidence_adjustment = "severe_downgrade"
    elif after_total < before_total or action_after != before_action:
        confidence_adjustment = "downgrade"
    else:
        confidence_adjustment = "keep"

    if not downgrade_reasons:
        downgrade_reasons.append("no deterministic downgrade beyond existing analyzer guardrails")

    score_after = dict(before_score)
    score_after["total_score"] = after_total
    score_after["score_explanation"] = (
        f"Critic adjusted score from {before_total} to {after_total}; "
        f"critical={critical_count}, major={major_count}, warning={warning_count}."
    )

    follow_ups = list(analysis.get("follow_up_validation_experiments") or analysis.get("follow_up_experiments") or [])
    for item in (
        "Add fair baseline replay with p95/p99/p99.9 and worst-case latency.",
        "Run degraded-process counterfactual tests for queue jitter, BER, topology irregularity, and long-tail traffic.",
        "Document operations, rollback, compatibility, isolation, and reliability evidence before production use.",
    ):
        if item not in follow_ups:
            follow_ups.append(item)

    overall = "critic found no major blockers"
    if critical_count:
        overall = "critical issues require action cap and score cap"
    elif major_count:
        overall = "major CNI evidence or constraint gaps require downgrade"
    elif warning_count:
        overall = "warnings require follow-up before stronger confidence"

    critic = {
        "critic_id": f"critic-{analysis.get('source_id', 'unknown')}-{_analysis_hash(analysis)[:12]}",
        "source_id": common["source_id"],
        "title": common["title"],
        "domain": common["domain"],
        "source_tier": common["source_tier"],
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "input_analysis_hash": _analysis_hash(analysis),
        "overall_assessment": overall,
        "confidence_adjustment": confidence_adjustment,
        "recommended_action_before": before_action,
        "recommended_action_after": action_after,
        "recommended_action": action_after,
        "score_before": before_score,
        "score_after": score_after,
        "score": score_after,
        "risk_flags": common["risk_flags"],
        "network_impact_vector": common["network_impact_vector"],
        "evidence_quality": common["evidence_quality"],
        "downgrade_reasons": downgrade_reasons,
        "constraint_findings": _findings_for(violations, ("process_constraints", "constraint_", "dependency_")),
        "counterfactual_findings": _findings_for(violations, ("degraded_process",)),
        "network_impact_findings": _findings_for(violations, ("network_", "latency_", "jitter_", "bandwidth_", "reliability_", "operations_", "security_", "average_only")),
        "evidence_quality_findings": _findings_for(violations, ("strong_conclusion", "baseline_", "evidence_", "vendor_", "marketing_", "no_experiment")),
        "deployment_risk_findings": _findings_for(violations, ("production_", "strong_action")),
        "security_ops_findings": _findings_for(violations, ("security_", "operations_", "production_", "strong_action")),
        "hard_rule_violations": violations,
        "suggested_follow_up_experiments": follow_ups,
        "final_critic_notes": [
            "Deterministic critic only; no model call was made.",
            "No network access or API key access was used.",
            "Source body remains untrusted content inherited through analyzer output.",
            "Critic output should feed later 72h brief synthesis as a quality and risk input.",
        ],
    }
    critic.update(common_fields_from_critic(critic, analysis))
    return critic
