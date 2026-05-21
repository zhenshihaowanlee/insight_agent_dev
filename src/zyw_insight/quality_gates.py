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

NETWORK_KEY_ALIASES = {
    "Latency": "latency",
    "Jitter/IPDV": "jitter_ipdv",
    "Bandwidth/Capacity": "bandwidth_capacity",
    "Reliability": "reliability",
    "Security": "security",
    "Operations": "operations",
    "BER/Error": "ber_error",
    "Scalability": "scalability",
    "Cost/Power": "cost_power",
}


def _network_item(network: Dict[str, Any], key: str) -> Dict[str, Any]:
    item = network.get(key)
    if item is None:
        item = network.get(NETWORK_KEY_ALIASES.get(key, ""))
    return item or {}


def _evidence_has_good_grade(evidence: Dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(str(evidence.get(k, "")).upper() in {"A", "B"} for k in keys)


def evaluate_analysis(analysis: Dict[str, Any]) -> List[QualityIssue]:
    """Evaluate CNI hard rules against a literature analysis dict."""
    issues: List[QualityIssue] = []

    evidence = analysis.get("evidence_quality", {}) or {}
    conclusion_strength = str(analysis.get("conclusion_strength", "")).lower()
    recommended_action = analysis.get("recommended_action")
    triage_risks = set((analysis.get("triage_summary") or {}).get("risk_flags", []))

    has_experimental_or_production = _evidence_has_good_grade(evidence, ("real_deployment", "physical_testbed", "simulation"))
    if conclusion_strength == "strong" and not has_experimental_or_production:
        issues.append(QualityIssue("block", "evidence_required", "Strong conclusions require experimental or production evidence."))
        issues.append(QualityIssue("block", "no_experiment_no_strong_conclusion", "No experiment or production signal may support a strong conclusion."))
    elif "no_experiment_signal" in triage_risks:
        issues.append(QualityIssue("warn", "no_experiment_no_strong_conclusion", "No experiment signal detected; strong conclusions remain disallowed."))

    if "vendor_claim" in triage_risks:
        issues.append(QualityIssue("warn", "vendor_claim", "Vendor claim detected; use as signal only until independently validated."))
    if "marketing_language" in triage_risks:
        issues.append(QualityIssue("warn", "marketing_language", "Marketing language detected; downgrade evidence confidence."))
    if "average_only_signal" in triage_risks:
        issues.append(QualityIssue("warn", "average_only_degrades_confidence", "Average-only latency signal detected by triage."))
    if "missing_baseline" in triage_risks:
        issues.append(QualityIssue("warn", "missing_baseline_degrades_confidence", "Missing or negated baseline signal detected by triage."))

    network = analysis.get("network_impact_vector", {}) or {}
    for key in REQUIRED_NETWORK_KEYS:
        if key not in network and NETWORK_KEY_ALIASES.get(key) not in network:
            issues.append(QualityIssue("warn", "missing_network_metric", f"Missing Network Impact Vector metric: {key}"))

    latency_evidence = str(_network_item(network, "Latency").get("evidence", "")).lower()
    if recommended_action in {"S", "A"} and not any(p in latency_evidence for p in ("p95", "p99", "tail", "worst")):
        issues.append(QualityIssue("warn", "tail_latency_missing", "S/A recommendations should discuss p95/p99/tail or worst-case latency."))
        issues.append(QualityIssue("warn", "missing_tail_latency_warning", "Network analysis should include p95/p99/tail or worst-case latency."))
    if "average" in latency_evidence and not any(p in latency_evidence for p in ("p95", "p99", "tail", "worst")):
        issues.append(QualityIssue("warn", "average_only_degrades_confidence", "Average-only latency evidence should downgrade confidence."))

    baseline = str(evidence.get("baseline", "")).upper()
    if recommended_action in {"S", "A"} and baseline not in {"A", "B"}:
        issues.append(QualityIssue("warn", "baseline_fairness", "S/A recommendations require fair baseline evidence."))
        issues.append(QualityIssue("warn", "missing_baseline_degrades_confidence", "Missing fair baseline should downgrade confidence."))

    constraints = analysis.get("constraints") or analysis.get("process_constraints") or []
    if not constraints:
        issues.append(QualityIssue("block", "constraints_missing", "Process/implementation constraints are required."))
        issues.append(QualityIssue("block", "missing_process_constraints_requires_inference", "Missing process constraints require explicit inference before analysis can pass."))
    elif any(not item.get("explicitly_stated", False) for item in constraints if isinstance(item, dict)):
        issues.append(QualityIssue("info", "missing_process_constraints_requires_inference", "Some process constraints are inferred rather than explicitly stated."))

    security_ops = analysis.get("security_and_operations") or analysis.get("security_and_operations_impact") or {}
    if recommended_action in {"S", "A"}:
        for required in ("security", "operations", "reliability"):
            value = str(security_ops.get(required, "")).lower()
            if not value or value in {"unknown", "missing"} or "unknown" in value or "missing" in value or "weak" in value:
                issues.append(QualityIssue("warn", f"{required}_missing", f"{required} analysis is required before production-oriented recommendations."))
        if any(
            not str(security_ops.get(required, "")).lower()
            or "unknown" in str(security_ops.get(required, "")).lower()
            or "missing" in str(security_ops.get(required, "")).lower()
            or "weak" in str(security_ops.get(required, "")).lower()
            for required in ("security", "operations", "reliability")
        ):
            issues.append(QualityIssue("warn", "production_recommendation_requires_ops_security_reliability", "Production-oriented recommendations require operations, security, and reliability analysis."))

    counterfactual = analysis.get("degraded_process_counterfactual", {}) or {}
    if counterfactual.get("verdict") in {"yes", "conditional"} and not counterfactual.get("conditions"):
        issues.append(QualityIssue("block", "counterfactual_conditions_missing", "Worse-process superiority claims require explicit conditions."))
        issues.append(QualityIssue("block", "degraded_process_claim_requires_conditions", "Degraded-process superiority claims require explicit conditions."))

    jitter_evidence = str(_network_item(network, "Jitter/IPDV").get("evidence", "")).lower()
    jitter_risk = str(_network_item(network, "Jitter/IPDV").get("risk", "")).lower()
    if "jitter" in f"{jitter_evidence} {jitter_risk}" and not any(term in f"{jitter_evidence} {jitter_risk}" for term in ("ipdv", "delay variation", "inter-arrival variation")):
        issues.append(QualityIssue("warn", "jitter_should_be_ipdv_or_delay_variation", "Jitter discussion should distinguish IPDV, delay variation, or inter-arrival variation."))

    bandwidth_text = " ".join(
        str(_network_item(network, "Bandwidth/Capacity").get(field, "")).lower()
        for field in ("evidence", "risk")
    )
    if ("bandwidth" in bandwidth_text or "throughput" in bandwidth_text) and not any(term in bandwidth_text for term in ("capacity", "available capacity", "throughput", "goodput")):
        issues.append(QualityIssue("warn", "bandwidth_must_distinguish_capacity_throughput_goodput", "Bandwidth analysis must distinguish capacity, available capacity, throughput, and goodput."))

    return issues


def gate_status(issues: List[QualityIssue]) -> str:
    """Summarize quality gate status."""
    if any(issue.severity == "block" for issue in issues):
        return "block"
    if any(issue.severity == "warn" for issue in issues):
        return "warn"
    return "pass"


def evaluate_critic_rules(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return deterministic CNI critic hard-rule violations for an analyzer output."""
    violations: List[Dict[str, Any]] = []

    def add(rule_id: str, severity: str, message: str, sections: List[str], fix: str) -> None:
        violations.append(
            {
                "rule_id": rule_id,
                "severity": severity,
                "message": message,
                "affected_sections": sections,
                "suggested_fix": fix,
            }
        )

    network = analysis.get("network_impact_vector", {}) or {}
    evidence = analysis.get("evidence_quality", {}) or {}
    triage_risks = set((analysis.get("triage_summary") or {}).get("risk_flags", []))
    recommended_action = str(analysis.get("recommended_action", "D"))
    conclusion_strength = str(analysis.get("conclusion_strength", "")).lower()

    constraints = analysis.get("process_constraints") or analysis.get("constraints") or []
    if not constraints:
        add("process_constraints_missing", "major", "No process or implementation constraints are listed.", ["process_constraints"], "Add explicit manufacturing/device/chip/NIC/protocol/network/ops/security/cost constraints.")
    elif any(str(item.get("type", "unknown")).lower() == "unknown" for item in constraints if isinstance(item, dict)):
        add("process_constraints_inferred", "warning", "Some constraints are inferred or unknown.", ["process_constraints"], "Separate explicit source constraints from inferred constraints and mark uncertainty.")
    if any(not item.get("degradation_consequence") for item in constraints if isinstance(item, dict)):
        add("constraint_degradation_missing", "major", "At least one constraint lacks degradation consequence.", ["process_constraints"], "State what fails when the constraint worsens.")

    present_types = {str(item.get("type", "")).lower() for item in constraints if isinstance(item, dict)}
    expected_types = {"manufacturing", "device", "chip", "nic", "protocol", "network", "operations", "security", "cost"}
    missing_types = sorted(expected_types - present_types)
    if missing_types:
        add("constraint_coverage_incomplete", "warning", "Constraint coverage is incomplete: " + ", ".join(missing_types), ["process_constraints"], "Cover or explicitly mark unknown for all major CNI constraint families.")

    dependencies = analysis.get("constraint_dependency_analysis") or analysis.get("constraint_dependency") or []
    dependency_text = " ".join(str(item).lower() for item in dependencies)
    for target in ("latency", "jitter", "bandwidth", "reliability", "ber", "deploy"):
        if target not in dependency_text:
            add(f"dependency_{target}_missing", "warning", f"Constraint dependency for {target} is not explicit.", ["constraint_dependency_analysis"], f"State which constraints {target} depends on and how strongly.")

    counterfactual = analysis.get("degraded_process_counterfactual", {}) or {}
    verdict = str(counterfactual.get("verdict", "unknown")).lower()
    if verdict in {"yes", "conditional"} and not counterfactual.get("conditions"):
        add("degraded_process_conditions_missing", "major", "Degraded-process superiority claim lacks conditions.", ["degraded_process_counterfactual"], "List necessary conditions for algorithmic/redundancy/protocol compensation.")
    if not counterfactual.get("compensation_mechanisms"):
        add("degraded_process_compensation_missing", "warning", "Counterfactual lacks compensation mechanisms.", ["degraded_process_counterfactual"], "Discuss algorithm, redundancy, coding, scheduling, or protocol compensation.")

    for key in ("latency", "jitter_ipdv", "bandwidth_capacity", "reliability", "security", "operations", "ber_error", "scalability", "cost_power"):
        if key not in network:
            add(f"network_{key}_missing", "major", f"Network Impact Vector missing {key}.", ["network_impact_vector"], "Populate all 9 required Network Impact Vector dimensions.")

    latency = network.get("latency", {}) or {}
    latency_text = " ".join(str(latency.get(field, "")).lower() for field in ("evidence", "risk"))
    if latency.get("impact") == "++" and not any(term in latency_text for term in ("p95", "p99", "p99.9", "tail", "worst")):
        add("latency_strong_without_tail", "major", "Latency is ++ without p95/p99/p99.9 or tail evidence.", ["network_impact_vector.latency"], "Downgrade latency impact or add tail-latency evidence.")
    if "average_only_signal" in triage_risks:
        add("average_only_metric", "warning", "Only average latency/performance signal is detected.", ["network_impact_vector.latency", "evidence_quality"], "Require tail and worst-case metrics before positive action.")

    jitter = network.get("jitter_ipdv", {}) or {}
    jitter_text = " ".join(str(jitter.get(field, "")).lower() for field in ("evidence", "risk"))
    if "jitter" in jitter_text and not any(term in jitter_text for term in ("ipdv", "delay variation", "inter-arrival variation")):
        add("jitter_not_ipdv", "warning", "Jitter wording does not distinguish IPDV/delay variation/inter-arrival variation.", ["network_impact_vector.jitter_ipdv"], "Use IPDV or explicitly define the delay variation metric.")

    bandwidth = network.get("bandwidth_capacity", {}) or {}
    bandwidth_text = " ".join(str(bandwidth.get(field, "")).lower() for field in ("evidence", "risk"))
    if ("bandwidth" in bandwidth_text or "throughput" in bandwidth_text) and not all(term in bandwidth_text for term in ("capacity", "throughput", "goodput")):
        add("bandwidth_capacity_mixed", "warning", "Bandwidth/capacity/throughput/goodput are not fully distinguished.", ["network_impact_vector.bandwidth_capacity"], "Separate capacity, available capacity, throughput, and goodput.")

    reliability = network.get("reliability", {}) or {}
    reliability_text = " ".join(str(reliability.get(field, "")).lower() for field in ("evidence", "risk"))
    if reliability.get("impact") in {"+", "++"} and not any(term in reliability_text for term in ("failure", "loss", "recovery")):
        add("reliability_positive_without_failure", "major", "Reliability is positive without failure/loss/recovery evidence.", ["network_impact_vector.reliability"], "Add failure, loss, recovery, or fault-injection evidence.")

    operations = network.get("operations", {}) or {}
    operations_text = " ".join(str(operations.get(field, "")).lower() for field in ("evidence", "risk"))
    if operations.get("impact") in {"+", "++"} and not any(term in operations_text for term in ("observability", "rollback", "compatibility", "telemetry")):
        add("operations_positive_without_ops_evidence", "major", "Operations is positive without observability/rollback/compatibility evidence.", ["network_impact_vector.operations"], "Add operational evidence or downgrade operations impact.")

    security = network.get("security", {}) or {}
    security_text = " ".join(str(security.get(field, "")).lower() for field in ("evidence", "risk"))
    if security.get("impact") in {"+", "++"} and not any(term in security_text for term in ("threat model", "isolation", "key management", "encryption")):
        add("security_positive_without_security_evidence", "major", "Security is positive without threat model/isolation/key-management evidence.", ["network_impact_vector.security"], "Add concrete security analysis or downgrade security impact.")

    has_experiment = _evidence_has_good_grade(evidence, ("real_deployment", "physical_testbed", "simulation"))
    if conclusion_strength == "strong" and not has_experiment:
        add("strong_conclusion_without_experiment", "critical", "Strong conclusion without deployment, testbed, or simulation evidence.", ["evidence_quality", "one_sentence_conclusion"], "Downgrade conclusion strength until experimental evidence exists.")
    if str(evidence.get("baseline", "")).upper() not in {"A", "B"} or "missing_baseline" in triage_risks:
        add("baseline_fairness_missing", "major", "Baseline fairness is missing or weak.", ["evidence_quality", "comparison_with_existing_technology"], "Add fair baseline comparison before S/A recommendations.")
    for key in ("ablation", "sensitivity_analysis", "failure_analysis", "reproducibility"):
        if str(evidence.get(key, "")).upper() not in {"A", "B"}:
            add(f"evidence_{key}_weak", "warning", f"Evidence quality for {key} is weak.", ["evidence_quality"], f"Add {key.replace('_', ' ')} evidence or keep confidence low.")

    if "vendor_claim" in triage_risks:
        add("vendor_claim", "major", "Vendor claim detected; cannot directly support strong action.", ["triage_summary", "evidence_quality"], "Treat as signal only until independently validated.")
    if "marketing_language" in triage_risks:
        add("marketing_language", "major", "Marketing language detected.", ["triage_summary"], "Downgrade confidence and require independent experiments.")
    if "no_experiment_signal" in triage_risks:
        add("no_experiment_signal", "major", "No experiment signal detected.", ["triage_summary", "evidence_quality"], "Require testbed, simulation, or production evidence.")

    security_ops = analysis.get("security_and_operations_impact") or analysis.get("security_and_operations") or {}
    security_ops_text = " ".join(str(security_ops.get(key, "")).lower() for key in ("security", "operations", "reliability"))
    if recommended_action == "S" and any(term in security_ops_text for term in ("unknown", "missing", "weak")):
        add("production_action_without_ops_security_reliability", "critical", "S recommendation lacks complete operations/security/reliability support.", ["security_and_operations_impact", "recommended_action"], "Cap action below S until ops/security/reliability evidence is complete.")
    elif recommended_action == "A" and any(term in security_ops_text for term in ("unknown", "missing", "weak")):
        add("strong_action_without_ops_security_reliability", "warning", "A recommendation has incomplete operations/security/reliability support.", ["security_and_operations_impact", "recommended_action"], "Keep as review/PoC action, not production-ready.")

    return violations
