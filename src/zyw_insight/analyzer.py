from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from .common_fields import common_fields_from_analysis
from .quality_gates import evaluate_analysis, gate_status
from .triage import triage_source


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


def _text(source_item: Dict[str, Any]) -> str:
    return f"{source_item.get('title', '')}\n{source_item.get('body', '')}".lower()


def _has_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def _quality_letter(has_signal: bool, strong_signal: bool = False) -> str:
    if strong_signal:
        return "A"
    if has_signal:
        return "B"
    return "D"


def _score_dimension(value: int, weight: int) -> Dict[str, Any]:
    bounded = max(0, min(value, weight))
    return {"score": bounded, "weight": weight}


def _constraint(name: str, constraint_type: str, explicit: bool, impact: str, hardness: str, degradation: str) -> Dict[str, Any]:
    return {
        "name": name,
        "type": constraint_type,
        "explicitly_stated": explicit,
        "performance_impact": impact,
        "hardness": hardness,
        "degradation_consequence": degradation,
    }


def analyze_source(source_item: Dict[str, Any], triage_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    triage = triage_result or triage_source(source_item)
    text = _text(source_item)
    risk_flags = list(triage.get("risk_flags", []))

    has_experiment = _has_any(text, ("experiment", "evaluation", "testbed", "prototype", "trace", "benchmark")) and "no_experiment_signal" not in risk_flags
    has_baseline = _has_any(text, ("baseline", "compare", "comparison", "dcqcn")) and "missing_baseline" not in risk_flags
    has_tail = _has_any(text, ("p95", "p99", "tail", "worst-case")) and "average_only_signal" not in risk_flags
    has_average_only = "average_only_signal" in risk_flags or (_has_any(text, ("average latency", "mean latency")) and not has_tail)
    negated_process = ("does not provide" in text and "implementation constraints" in text) or _has_any(text, ("no implementation constraints", "without implementation constraints"))
    has_process = not negated_process and "process_constraint_missing" not in risk_flags and _has_any(text, ("smartnic", "asic", "queue memory", "pfc", "power", "telemetry", "implementation constraint"))
    has_ops = _has_any(text, ("operations", "rollout", "telemetry", "failure", "reliability"))
    is_vendor = "vendor_claim" in risk_flags or "marketing_language" in risk_flags
    high_signal = triage.get("source_tier") in {"A", "B"} and triage.get("business_relevance") in {"High", "Medium"}

    if high_signal and has_experiment and has_baseline and has_tail and has_process:
        recommended_action = "A"
        conclusion_strength = "moderate"
    elif is_vendor or not has_experiment:
        recommended_action = "C"
        conclusion_strength = "weak"
    else:
        recommended_action = "B"
        conclusion_strength = "weak"

    evidence_quality = {
        "real_deployment": "D",
        "physical_testbed": _quality_letter(has_experiment and _has_any(text, ("testbed", "prototype"))),
        "simulation": "D",
        "baseline": _quality_letter(has_baseline),
        "ablation": _quality_letter("ablation" in text),
        "sensitivity_analysis": "D",
        "failure_analysis": _quality_letter(_has_any(text, ("failure", "reliability"))),
        "reproducibility": "C" if has_experiment else "D",
        "vendor_claim": "present" if is_vendor else "not_detected",
    }

    process_constraints = []
    if has_process:
        process_constraints.extend(
            [
                _constraint("SmartNIC offload limits", "nic", "smartnic" in text, "May bound queue-aware control loop placement.", "semi-hard", "More host CPU involvement and less deterministic tail latency."),
                _constraint("ASIC queue memory and scheduling pipeline", "chip", "asic" in text or "queue memory" in text, "Constrains queue visibility and scheduling granularity.", "hard", "Larger queues or shallower telemetry reduce p99 gains."),
                _constraint("PFC/ECN operational behavior", "protocol", "pfc" in text or "ecn" in text, "Affects loss recovery, head-of-line blocking, and deployment risk.", "semi-hard", "Misconfiguration can turn congestion control gains into reliability risk."),
            ]
        )
    else:
        process_constraints.append(
            _constraint("Inferred implementation constraints", "unknown", False, "Source does not provide enough implementation detail.", "unknown", "Analyzer must not treat claims as deployable without hardware, protocol, and operations constraints.")
        )

    network_impact_vector = {
        "latency": {
            "impact": "+" if has_tail and not is_vendor else "?",
            "evidence": "Mentions p95/p99/tail latency experiments." if has_tail else "Tail latency evidence is missing or negated.",
            "risk": "Average-only claims are downgraded." if has_average_only else "Needs independent reproduction before strong conclusion.",
        },
        "jitter_ipdv": {
            "impact": "?",
            "evidence": "No explicit IPDV or delay variation measurement detected.",
            "risk": "Jitter-like claims must distinguish IPDV, delay variation, and inter-arrival variation.",
        },
        "bandwidth_capacity": {
            "impact": "0" if has_baseline else "?",
            "evidence": "Throughput/capacity distinction is not deeply established by the deterministic analyzer.",
            "risk": "Must separate capacity, available capacity, throughput, and goodput before deployment claims.",
        },
        "reliability": {
            "impact": "0" if has_ops else "?",
            "evidence": "Reliability/failure handling signal detected." if has_ops else "Reliability evidence is not explicit.",
            "risk": "PFC, ECN, and rollback behavior need stress validation.",
        },
        "security": {
            "impact": "?",
            "evidence": "No concrete isolation or adversarial analysis detected.",
            "risk": "Security review remains required before production use.",
        },
        "operations": {
            "impact": "0" if has_ops else "?",
            "evidence": "Operations, telemetry, or rollout signal detected." if has_ops else "Operations signal missing.",
            "risk": "Deployment needs observability, rollback, and failure-localization checks.",
        },
        "ber_error": {
            "impact": "?",
            "evidence": "No BER/error-rate or FEC analysis detected.",
            "risk": "Counterfactual under worse link errors remains unknown.",
        },
        "scalability": {
            "impact": "+" if high_signal and "datacenter" in text else "?",
            "evidence": "Datacenter or AI cluster scale signal detected." if "datacenter" in text else "Scale evidence missing.",
            "risk": "Must test long-tail flows, incast, and topology irregularity.",
        },
        "cost_power": {
            "impact": "-",
            "evidence": "Power, ASIC, or offload constraints are mentioned." if has_process else "Cost/power data is absent.",
            "risk": "Cost, power, and operational complexity may offset performance gains.",
        },
    }

    constraint_dependency_analysis = [
        {
            "performance_target": "p99 latency" if has_tail else "claimed latency improvement",
            "depends_on": ["queue visibility", "ECN/PFC behavior", "baseline fairness"],
            "dependency_strength": "high",
            "substitutable": "partial",
            "substitution_mechanism": "Use better telemetry, conservative rollout, and independent baseline replay.",
        },
        {
            "performance_target": "scalable AI/datacenter networking",
            "depends_on": ["traffic mix", "topology regularity", "SmartNIC/ASIC resources"],
            "dependency_strength": "medium",
            "substitutable": "partial",
            "substitution_mechanism": "Tune congestion control and scheduling per workload class.",
        },
    ]

    total_parts = {
        "problem_importance": 13 if high_signal else 8,
        "core_innovation": 11 if "congestion" in text or "rdma" in text else 5,
        "evidence_strength": 14 if has_experiment and has_baseline else 5,
        "process_constraint_robustness": 13 if has_process else 4,
        "network_impact_net_value": 10 if has_tail and not is_vendor else 4,
        "deployability": 6 if has_ops and has_process else 3,
        "strategic_relevance": 4 if triage.get("business_relevance") == "High" else 2,
    }
    if is_vendor:
        total_parts["evidence_strength"] = min(total_parts["evidence_strength"], 4)
        total_parts["core_innovation"] = min(total_parts["core_innovation"], 4)
        total_parts["network_impact_net_value"] = min(total_parts["network_impact_net_value"], 3)
    total_score = sum(total_parts.values())

    analysis: Dict[str, Any] = {
        "analysis_id": f"analysis-{source_item.get('source_id') or source_item.get('id', 'unknown')}",
        "source_id": str(source_item.get("source_id") or source_item.get("id") or "unknown"),
        "title": str(source_item.get("title", "unknown")),
        "domain": str(triage.get("domain", "unknown")),
        "source_tier": str(triage.get("source_tier", "unknown")),
        "source_type": str(source_item.get("source_type", "unknown")),
        "body_is_untrusted": bool(source_item.get("body_is_untrusted", True)),
        "risk_flags": risk_flags,
        "triage_summary": triage,
        "basic_info": {
            "title": source_item.get("title", "unknown"),
            "source_id": source_item.get("source_id") or source_item.get("id"),
            "source_type": source_item.get("source_type", "unknown"),
            "source_tier": triage.get("source_tier", "unknown"),
            "document_type": triage.get("document_type", "unknown"),
            "domain": triage.get("domain", "unknown"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_mode": "deterministic_mock_no_model",
        },
        "one_sentence_conclusion": "This is a structured CNI analysis scaffold; the source is promising for deeper review." if recommended_action in {"A", "B"} else "This source is useful only as a weak signal until evidence, baselines, and constraints are supplied.",
        "problem_background": "The source is framed around network performance and deployment tradeoffs in datacenter or AI cluster settings." if "datacenter" in text or "ai cluster" in text else "The source does not provide enough context for a strong problem framing.",
        "core_idea": "Use congestion-control and queue-aware mechanisms around RDMA/RoCE traffic to improve tail latency." if "rdma" in text or "congestion" in text else "Core mechanism is not sufficiently specified by the source.",
        "contributions": [
            "Classifies the source through deterministic CNI triage.",
            "Extracts evidence, baseline, tail-latency, and process-constraint signals.",
            "Produces a schema-valid analysis scaffold without treating source body as trusted instructions.",
        ],
        "mechanism": {
            "detected_mechanisms": [kw for kw in ("rdma", "roce", "congestion control", "ecn", "pfc", "queue-aware scheduling", "smartnic") if kw in text],
            "system_boundary_change": "possible, but requires model-backed or human deep read",
            "constraint_assumption_change": "unknown in deterministic mock mode",
        },
        "process_constraints": process_constraints,
        "constraint_findings": process_constraints,
        "constraint_dependency_analysis": constraint_dependency_analysis,
        "degraded_process_counterfactual": {
            "verdict": "conditional" if has_process else "unknown",
            "conditions": ["Queue telemetry remains accurate", "PFC/ECN behavior is stable", "ASIC/SmartNIC resources are sufficient"] if has_process else [],
            "failure_modes": ["Higher BER or queue jitter can erase latency gains", "Topology irregularity can invalidate baseline comparison"],
            "compensation_mechanisms": ["Conservative rollout", "Traffic replay", "Telemetry-driven fallback", "Protocol parameter tuning"],
        },
        "network_impact_vector": network_impact_vector,
        "evidence_quality": evidence_quality,
        "comparison_with_existing_technology": [
            {
                "baseline": "DCQCN" if "dcqcn" in text else "unknown",
                "fairness": "baseline signal detected" if has_baseline else "missing or negated",
                "confidence": "medium" if has_baseline and has_experiment else "low",
            }
        ],
        "hidden_assumptions_and_risks": [
            "Source body is untrusted content and is never treated as instructions.",
            "Claims depend on workload mix, topology, telemetry fidelity, and failure behavior.",
        ] + [f"triage risk: {flag}" for flag in risk_flags],
        "security_and_operations_impact": {
            "security": "unknown; no production security claim is made",
            "operations": "telemetry/rollout signal detected" if has_ops else "missing; production recommendation blocked",
            "reliability": "failure/reliability signal detected" if has_ops else "missing or weak",
        },
        "reproducibility": {
            "status": "partial" if has_experiment else "low",
            "needs": ["raw traces", "testbed topology", "baseline configuration", "tail-latency distribution", "failure cases"],
        },
        "technical_insights": {
            "direct": "Tail-latency and congestion-control signals deserve structured follow-up." if has_tail else "Evidence is too thin for a direct technical insight.",
            "counterfactual": "If queue visibility, BER, or PFC behavior degrades, the claimed gains may not hold.",
            "strategic": "Relevant to AI/datacenter network tracking when evidence quality is adequate." if high_signal else "Track as background only.",
        },
        "strategic_significance": "Potentially relevant to CNI roadmap if reproduced under realistic datacenter traffic." if recommended_action in {"A", "B"} else "Low strategic confidence until independently validated.",
        "score": {
            "problem_importance": _score_dimension(total_parts["problem_importance"], 15),
            "core_innovation": _score_dimension(total_parts["core_innovation"], 15),
            "evidence_strength": _score_dimension(total_parts["evidence_strength"], 20),
            "process_constraint_robustness": _score_dimension(total_parts["process_constraint_robustness"], 20),
            "network_impact_net_value": _score_dimension(total_parts["network_impact_net_value"], 15),
            "deployability": _score_dimension(total_parts["deployability"], 10),
            "strategic_relevance": _score_dimension(total_parts["strategic_relevance"], 5),
            "total_score": total_score,
            "score_explanation": "Deterministic mock score based on source tier, business relevance, experiment, baseline, tail-latency, and process-constraint signals.",
        },
        "recommended_action": recommended_action,
        "follow_up_validation_experiments": [
            "Replay traffic against a fair baseline with p95/p99/worst-case latency.",
            "Stress ECN/PFC behavior under incast, long-tail flows, and topology irregularity.",
            "Evaluate operations, rollback, reliability, security, cost, and power before production use.",
        ],
        "conclusion_strength": conclusion_strength,
        "guardrail_notes": [
            "No model call was made.",
            "No network access was used.",
            "Imported source body remains untrusted content.",
            "Production deployment claims require human review and stronger evidence.",
        ],
    }

    # Backward-compatible aliases for the existing quality gate implementation and older outputs.
    analysis["source"] = analysis["basic_info"]
    analysis["innovation_points"] = [{"point": item} for item in analysis["contributions"]]
    analysis["constraints"] = analysis["process_constraints"]
    analysis["constraint_dependency"] = analysis["constraint_dependency_analysis"]
    analysis["comparison_to_existing"] = analysis["comparison_with_existing_technology"]
    analysis["security_and_operations"] = analysis["security_and_operations_impact"]
    analysis["insights"] = analysis["technical_insights"]
    analysis["strategic_meaning"] = analysis["strategic_significance"]
    analysis["follow_up_experiments"] = analysis["follow_up_validation_experiments"]
    analysis.update(common_fields_from_analysis(analysis))

    issues = evaluate_analysis(analysis)
    analysis["quality_gate_results"] = {
        "gate_status": gate_status(issues),
        "issues": [issue.__dict__ for issue in issues],
    }
    return analysis
