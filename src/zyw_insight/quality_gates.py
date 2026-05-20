from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class QualityIssue:
    severity: str  # info | warn | block
    rule: str
    message: str


REQUIRED_NETWORK_KEYS = [
    "Latency",
    "Jitter/IPDV",
    "Bandwidth/Capacity",
    "Reliability",
    "Security",
    "Operations",
    "BER/Error",
    "Scalability",
    "Cost/Power",
]


def evaluate_analysis(analysis: Dict[str, Any]) -> List[QualityIssue]:
    """Evaluate CNI hard rules against a literature analysis dict."""
    issues: List[QualityIssue] = []

    evidence = analysis.get("evidence_quality", {}) or {}
    conclusion_strength = str(analysis.get("conclusion_strength", "")).lower()
    recommended_action = analysis.get("recommended_action")

    has_experimental_or_production = any(
        str(evidence.get(k, "")).upper() in {"A", "B"}
        for k in ("real_deployment", "physical_testbed", "simulation")
    )
    if conclusion_strength == "strong" and not has_experimental_or_production:
        issues.append(QualityIssue("block", "evidence_required", "Strong conclusions require experimental or production evidence."))

    network = analysis.get("network_impact_vector", {}) or {}
    for key in REQUIRED_NETWORK_KEYS:
        if key not in network:
            issues.append(QualityIssue("warn", "missing_network_metric", f"Missing Network Impact Vector metric: {key}"))

    latency_evidence = str((network.get("Latency") or {}).get("evidence", "")).lower()
    if recommended_action in {"S", "A"} and not any(p in latency_evidence for p in ("p95", "p99", "tail", "worst")):
        issues.append(QualityIssue("warn", "tail_latency_missing", "S/A recommendations should discuss p95/p99/tail or worst-case latency."))

    baseline = str(evidence.get("baseline", "")).upper()
    if recommended_action in {"S", "A"} and baseline not in {"A", "B"}:
        issues.append(QualityIssue("warn", "baseline_fairness", "S/A recommendations require fair baseline evidence."))

    constraints = analysis.get("constraints") or []
    if not constraints:
        issues.append(QualityIssue("block", "constraints_missing", "Process/implementation constraints are required."))

    security_ops = analysis.get("security_and_operations", {}) or {}
    if recommended_action in {"S", "A"}:
        for required in ("security", "operations", "reliability"):
            if not security_ops.get(required):
                issues.append(QualityIssue("warn", f"{required}_missing", f"{required} analysis is required before production-oriented recommendations."))

    counterfactual = analysis.get("degraded_process_counterfactual", {}) or {}
    if counterfactual.get("verdict") in {"yes", "conditional"} and not counterfactual.get("conditions"):
        issues.append(QualityIssue("block", "counterfactual_conditions_missing", "Worse-process superiority claims require explicit conditions."))

    return issues


def gate_status(issues: List[QualityIssue]) -> str:
    """Summarize quality gate status."""
    if any(issue.severity == "block" for issue in issues):
        return "block"
    if any(issue.severity == "warn" for issue in issues):
        return "warn"
    return "pass"
