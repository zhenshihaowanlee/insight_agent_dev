from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

from .analyzer import NETWORK_KEYS
from .common_fields import common_fields_from_any


SIGNAL_STRENGTHS = {"high", "medium", "low", "weak", "unclear"}
ACTION_ORDER = ["S", "A", "B", "C", "D"]


def _score_total(score: Dict[str, Any]) -> int:
    try:
        return int(score.get("total_score", score.get("total", 0)))
    except (TypeError, ValueError):
        return 0


def _worst_action(actions: Iterable[str]) -> str:
    valid = [action for action in actions if action in ACTION_ORDER]
    if not valid:
        return "D"
    return max(valid, key=ACTION_ORDER.index)


def _best_action(actions: Iterable[str]) -> str:
    valid = [action for action in actions if action in ACTION_ORDER]
    if not valid:
        return "D"
    return min(valid, key=ACTION_ORDER.index)


def _item_followups(item: Dict[str, Any]) -> List[str]:
    if "critic" in item and isinstance(item["critic"], dict):
        return list(item["critic"].get("suggested_follow_up_experiments") or [])
    return list(item.get("suggested_follow_up_experiments") or item.get("follow_up_validation_experiments") or item.get("follow_up_experiments") or [])


def _direction(item: Dict[str, Any]) -> str:
    common = common_fields_from_any(item)
    domain = common["domain"]
    title = common["title"].lower()
    if domain and domain != "unknown":
        return domain
    for marker, direction in (
        ("rdma", "RDMA / RoCE"),
        ("optical", "optical interconnect"),
        ("smartnic", "SmartNIC / DPU"),
        ("p4", "P4 / programmable data plane"),
    ):
        if marker in title:
            return direction
    return "unknown"


def _signal_strength(count: int, avg_score: float, downgraded_ratio: float, vendor_ratio: float, source_tiers: Iterable[str] = (), serious_downgrade: bool = False) -> str:
    if vendor_ratio >= 0.5:
        return "weak"
    if downgraded_ratio >= 0.5 and count >= 2:
        return "weak"
    if count == 1:
        return "medium" if "A" in set(source_tiers) and not serious_downgrade and avg_score >= 55 else "unclear"
    if count >= 3 and avg_score >= 70:
        return "high"
    if count >= 2 and avg_score >= 55:
        return "medium"
    if count >= 2:
        return "low"
    return "unclear"


def _metric_summary(source_items: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    impacts = Counter()
    evidence = []
    risks = []
    for item in source_items:
        metric = (item.get("network_impact_vector") or {}).get(key) or {}
        impact = metric.get("impact", "?")
        impacts[impact] += 1
        if metric.get("evidence"):
            evidence.append(metric["evidence"])
        if metric.get("risk"):
            risks.append(metric["risk"])
    return {
        "dominant_impact": impacts.most_common(1)[0][0] if impacts else "?",
        "impact_counts": dict(impacts),
        "evidence_count": len(evidence),
        "risk_summary": sorted(set(risks))[:5],
        "required_validation": _metric_validation(key),
    }


def _metric_validation(key: str) -> str:
    return {
        "latency": "reproduce p95/p99/p99.9 and worst-case latency against a fair baseline",
        "jitter_ipdv": "measure IPDV or delay variation explicitly, not generic jitter",
        "bandwidth_capacity": "separate capacity, available capacity, throughput, and goodput",
        "reliability": "test loss, failure recovery, rollback, and incast stress",
        "security": "document threat model, isolation, and key/control-plane handling",
        "operations": "validate observability, compatibility, rollback, and incident workflow",
        "ber_error": "stress BER/FEC/error propagation under degraded links",
        "scalability": "test scale-out topology irregularity and long-tail traffic",
        "cost_power": "measure power, cost, operational complexity, and capacity tradeoff",
    }.get(key, "not available")


def _constraint_label(finding: Any) -> str:
    if isinstance(finding, dict):
        for key in ("name", "type", "rule_id", "constraint", "message"):
            if finding.get(key):
                return str(finding[key])
        return "extraction gap"
    text = str(finding).strip()
    return text or "extraction gap"


def _nested(item: Dict[str, Any], name: str) -> Dict[str, Any]:
    value = item.get(name)
    return value if isinstance(value, dict) else {}


def _analysis_id(item: Dict[str, Any]) -> str:
    analysis = _nested(item, "analysis")
    return str(analysis.get("analysis_id") or analysis.get("source_id") or item.get("analysis_id") or item.get("source_id") or "unknown")


def _critic_id(item: Dict[str, Any]) -> str:
    critic = _nested(item, "critic")
    return str(critic.get("critic_id") or item.get("critic_id") or "none")


def _critic_action_after(item: Dict[str, Any], common: Dict[str, Any]) -> str:
    critic = _nested(item, "critic")
    return str(critic.get("recommended_action_after") or item.get("recommended_action_after") or common.get("recommended_action") or "D")


def _critic_score_after(item: Dict[str, Any], common: Dict[str, Any]) -> Dict[str, Any]:
    critic = _nested(item, "critic")
    return critic.get("score_after") or item.get("score_after") or common.get("score") or {"total_score": 0}


def synthesize_brief(items: List[Dict[str, Any]], window_hours: int = 72, budget_mode: str = "quality_first", quality_priority: str = "high") -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    source_items = [common_fields_from_any(item) for item in items]
    input_count = len(source_items)

    domain_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for original, common in zip(items, source_items):
        domain_groups[_direction(original)].append(common)

    downgraded_count = sum(1 for item in items if isinstance(item.get("critic"), dict) and item["critic"].get("recommended_action_after") != item["critic"].get("recommended_action_before"))
    downgraded_count += sum(1 for item in items if "critic_id" in item and item.get("recommended_action_after") != item.get("recommended_action_before"))
    vendor_count = sum(1 for item in source_items if {"vendor_claim", "marketing_language", "no_experiment_signal"} & set(item.get("risk_flags", [])))
    missing_baseline_count = sum(1 for item in source_items if "missing_baseline" in set(item.get("risk_flags", [])))
    average_only_count = sum(1 for item in source_items if "average_only_signal" in set(item.get("risk_flags", [])))
    no_experiment_count = sum(1 for item in source_items if "no_experiment_signal" in set(item.get("risk_flags", [])))
    weak_cross_doc = input_count < 2
    downgraded_majority = input_count > 0 and downgraded_count / input_count > 0.5
    vendor_ratio = vendor_count / input_count if input_count else 0.0

    input_traceability = []
    for original, common in zip(items, source_items):
        score_after = _critic_score_after(original, common)
        included = _score_total(score_after) >= 55 and not ({"vendor_claim", "marketing_language", "no_experiment_signal"} & set(common.get("risk_flags", [])))
        input_traceability.append(
            {
                "source_id": common["source_id"],
                "title": common["title"],
                "analysis_id": _analysis_id(original),
                "critic_id": _critic_id(original),
                "source_tier": common["source_tier"],
                "domain": common["domain"],
                "recommended_action_after": _critic_action_after(original, common),
                "score_after": score_after,
                "included_in_top_conclusions": included,
                "inclusion_reason": "score and critic risk support top-level signal" if included else "kept for risk or contrast, not promoted as strong conclusion",
            }
        )

    radar = []
    for direction, group in sorted(domain_groups.items()):
        avg_score = sum(_score_total(item.get("score", {})) for item in group) / len(group)
        group_vendor_ratio = sum(1 for item in group if {"vendor_claim", "marketing_language", "no_experiment_signal"} & set(item.get("risk_flags", []))) / len(group)
        group_downgraded_ratio = 1.0 if downgraded_majority else 0.0
        strength = _signal_strength(len(group), avg_score, group_downgraded_ratio, group_vendor_ratio, [item.get("source_tier", "") for item in group], downgraded_majority)
        if len(group) >= 2 and avg_score < 65:
            new_evidence = "signal emerging, evidence weak"
        else:
            new_evidence = f"{len(group)} item(s), average score {avg_score:.1f}"
        radar.append(
            {
                "direction": direction,
                "signal_strength": strength,
                "evidence_count": len(group),
                "new_evidence": new_evidence,
                "constraint_risks": sorted({str(f.get("message", f.get("name", f))) for item in group for f in item.get("constraint_findings", [])})[:5],
                "recommended_action": "C" if downgraded_majority or group_vendor_ratio >= 0.5 else _best_action(item.get("recommended_action", "D") for item in group),
            }
        )

    conflicts = []
    for key in NETWORK_KEYS:
        positive = [item for item in source_items if ((item.get("network_impact_vector") or {}).get(key) or {}).get("impact") in {"+", "++"}]
        weak = [item for item in source_items if ((item.get("network_impact_vector") or {}).get(key) or {}).get("impact") in {"?", "-", "--"}]
        if positive and weak:
            conflicts.append(
                {
                    "conflict_point": f"{key} impact differs across sources",
                    "document_a_view": f"{positive[0]['title']} reports positive or promising impact.",
                    "document_b_view": f"{weak[0]['title']} has weak/unknown/negative evidence.",
                    "possible_explanation": "Different evidence quality, baseline fairness, deployment assumptions, or source tier.",
                    "validation_needed": "Replay comparable workloads and measure the same metric definitions.",
                    "severity": "medium" if key in {"latency", "reliability", "security", "operations"} else "low",
                    "impact_on_recommendation": "prevents stronger action until comparable evidence is available",
                    "validation_priority": "high" if key in {"latency", "reliability", "security", "operations"} else "medium",
                }
            )
    if not conflicts:
        conflicts.append(
            {
                "conflict_point": "cross-document signal is weak" if weak_cross_doc else "no direct metric contradiction detected",
                "document_a_view": "insufficient independent documents" if weak_cross_doc else "available documents do not directly conflict",
                "document_b_view": "requires more sources" if weak_cross_doc else "no opposing view found in current batch",
                "possible_explanation": "sample size is too small" if weak_cross_doc else "current deterministic examples are directionally aligned or sparse",
                "validation_needed": "add more independently sourced analyses before strong trend conclusions",
                "severity": "medium" if weak_cross_doc else "low",
                "impact_on_recommendation": "limits confidence and prevents strong trend-level recommendations",
                "validation_priority": "high" if weak_cross_doc else "medium",
            }
        )

    constraints = Counter()
    for item in source_items:
        for finding in item.get("constraint_findings", []):
            constraints[_constraint_label(finding)] += 1

    network_trends = {key: _metric_summary(source_items, key) for key in NETWORK_KEYS}
    evidence_counts = Counter()
    for item in source_items:
        for key, value in (item.get("evidence_quality") or {}).items():
            evidence_counts[f"{key}:{value}"] += 1

    biggest_risks = []
    if weak_cross_doc:
        biggest_risks.append("cross-document signal is weak because input_count < 2")
    if downgraded_majority:
        biggest_risks.append("most inputs were downgraded by critic; do not make strong conclusions")
    if vendor_ratio >= 0.4:
        biggest_risks.append("vendor/marketing/no experiment ratio is high; treat as weak signal")
    if not biggest_risks:
        biggest_risks.append("security, operations, BER/FEC, and reproducibility gaps remain primary risks")

    recommended_decisions = []
    if downgraded_majority or vendor_ratio >= 0.4:
        recommended_decisions.append("No production or major investment decision this cycle; use only for awareness, evidence-gap tracking, or guarded validation scoping.")
    elif input_count >= 2:
        recommended_decisions.append("Consider guarded validation scoping for the strongest non-vendor direction only after baseline, tail-latency, operations, security, and reliability checks.")
    else:
        recommended_decisions.append("Collect more sources before trend-level action; why_not_stronger_action: cross-document support is weak.")

    best_radar = sorted(
        radar,
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2, "weak": 3, "unclear": 4}.get(item["signal_strength"], 4),
            -int(item.get("evidence_count", 0)),
            item["direction"],
        ),
    )
    leading = best_radar[0] if best_radar else None
    top_conclusions = []
    if leading:
        top_conclusions.append(
            f"Strongest current signal is {leading['direction']} with {leading['signal_strength']} strength and action {leading['recommended_action']}; evidence count={leading['evidence_count']}."
        )
    if downgraded_majority or vendor_ratio >= 0.4:
        top_conclusions.append("No decisive technical recommendation this cycle; best use is watchlist update, evidence-gap tracking, or guarded validation scoping.")
    elif leading:
        top_conclusions.append(f"Best near-term use is targeted validation for {leading['direction']}, not production commitment.")
    if any(item["new_evidence"] == "signal emerging, evidence weak" for item in radar):
        top_conclusions.append("Repeated technology direction exists, but evidence remains weak and should be treated as emerging signal.")
    if weak_cross_doc:
        top_conclusions.append("cross-document signal is weak.")
    traceable = [trace for trace in input_traceability if trace["included_in_top_conclusions"]]
    if traceable:
        first = traceable[0]
        top_conclusions.append(f"Traceable leading signal: {first['title']} ({first['domain']}), source_id={first['source_id']}, critic_id={first['critic_id']}.")
    else:
        top_conclusions.append("No source is strong enough for a high-confidence technical claim; use critic findings to scope validation.")

    followups = []
    for item in items:
        for followup in _item_followups(item):
            if followup not in followups:
                followups.append(followup)
    for fallback in (
        "Add at least two independent sources per technology direction.",
        "Normalize p95/p99/p99.9, IPDV, capacity/throughput/goodput, BER/FEC, and operations metrics.",
        "Run degraded-process counterfactual validation before any production recommendation.",
    ):
        if fallback not in followups:
            followups.append(fallback)

    if downgraded_majority or vendor_ratio >= 0.4 or weak_cross_doc:
        overall_confidence = "weak" if vendor_ratio >= 0.4 or weak_cross_doc else "low"
    elif input_count >= 3 and any(item["signal_strength"] in {"high", "medium"} for item in radar):
        overall_confidence = "medium"
    else:
        overall_confidence = "low"

    rejected_strong_claims = []
    if downgraded_majority:
        rejected_strong_claims.append("Rejected strong conclusion because most inputs were downgraded by constraint critic.")
    if vendor_ratio >= 0.4:
        rejected_strong_claims.append("Rejected strong conclusion because vendor/marketing/no-experiment ratio is high.")
    if weak_cross_doc:
        rejected_strong_claims.append("Rejected strong trend conclusion because fewer than two inputs were available.")

    final_recommended_actions = [
        "C" if downgraded_majority or {"vendor_claim", "marketing_language", "no_experiment_signal"} & set(item.get("risk_flags", [])) else item["recommended_action"]
        for item in source_items
    ]
    all_actions_c_or_worse = bool(final_recommended_actions) and all(action in {"C", "D"} for action in final_recommended_actions)

    action_rationale = [
        {
            "action": decision,
            "affected_direction": radar[0]["direction"] if radar else "none",
            "evidence_basis": "critic-adjusted scores, source tiers, evidence quality, and repeated metric signals",
            "constraint_basis": "constraint findings and degraded-process robustness remain gating evidence",
            "risk_basis": "; ".join(biggest_risks),
            "expected_value": "prioritize validation work where evidence quality can change the decision",
            "why_not_stronger_action": "S/A action requires independent operations, security, reliability, baseline, and tail-latency validation",
        }
        for decision in recommended_decisions
    ]

    high_confidence_claims = [
        {
            "title": trace["title"],
            "source_id": trace["source_id"],
            "critic_id": trace["critic_id"],
            "direction": trace["domain"],
            "rationale": f"critic-adjusted action {trace['recommended_action_after']} with score {_score_total(trace['score_after'])}; suitable for scoped validation, not production claim",
        }
        for trace in traceable[:3]
    ]
    if not high_confidence_claims:
        high_confidence_claims = ["No high-confidence technical claim; only low-confidence signals."]

    return {
        "schema_version": "brief.v1.1-quality-first",
        "brief_id": f"brief-{now.strftime('%Y%m%d%H%M%S')}",
        "generated_at": now.isoformat(),
        "window": {"start": (now - timedelta(hours=window_hours)).isoformat(), "end": now.isoformat(), "hours": window_hours},
        "input_count": input_count,
        "source_items": source_items,
        "input_traceability": input_traceability,
        "executive_brief": {
            "top_conclusions": top_conclusions,
            "most_actionable_technologies": [item["direction"] for item in radar if item["signal_strength"] in {"high", "medium"}] or [radar[0]["direction"] if radar else "none"],
            "biggest_risks": biggest_risks,
            "recommended_decisions": recommended_decisions,
        },
        "technology_signal_radar": radar,
        "cross_document_conflicts": conflicts,
        "process_constraint_trends": {
            "most_frequent_constraints": [{"constraint": key, "count": value} for key, value in constraints.most_common(10)] or [
                {"constraint": "No concrete constraint extracted; mark as evidence gap.", "count": 0}
            ],
            "dependency_direction": "constraint dependencies remain partial; prioritize latency, jitter/IPDV, BER, operations, and security dependencies",
            "degraded_process_robustness_summary": "Do not assume worse-process superiority unless compensation conditions are explicit and validated.",
        },
        "network_metric_trends": network_trends,
        "evidence_quality_summary": {
            "evidence_grade_counts": dict(evidence_counts),
            "downgraded_count": downgraded_count,
            "vendor_or_marketing_risk_count": vendor_count,
            "strong_conclusion_allowed": not (downgraded_majority or vendor_ratio >= 0.4 or weak_cross_doc),
            "missing_baseline_count": missing_baseline_count,
            "average_only_count": average_only_count,
            "no_experiment_count": no_experiment_count,
        },
        "insight_quality": {
            "overall_confidence": overall_confidence,
            "evidence_weighting_method": "critic-adjusted score, source tier, source risk flags, cross-document repetition, and network metric conflicts",
            "high_confidence_claims": ["No high-confidence technical claim; only guarded signals."] if overall_confidence in {"low", "weak"} else high_confidence_claims,
            "low_confidence_claims": biggest_risks,
            "rejected_strong_claims": rejected_strong_claims,
            "uncertainty_notes": [
                "Deterministic brief is a local quality gate, not a model-based expert review.",
                "All source bodies are treated as untrusted content.",
            ],
        },
        "decision_readiness": {
            "ready_for_poc": not (overall_confidence in {"low", "weak"} and all_actions_c_or_worse) and not weak_cross_doc and vendor_ratio < 0.5,
            "ready_for_management_brief": input_count >= 2,
            "ready_for_management_awareness": input_count >= 2,
            "ready_for_management_decision": not (overall_confidence in {"low", "weak"} or all_actions_c_or_worse or downgraded_majority),
            "requires_human_review": True,
            "blocking_unknowns": [
                "independent baseline fairness",
                "tail latency and IPDV definitions",
                "operations/security/reliability readiness",
            ],
            "minimum_validation_before_action": [
                "reproduce p95/p99/p99.9 or worst-case latency against a fair baseline",
                "validate BER/FEC, rollback, observability, and failure recovery",
            ],
        },
        "recommended_actions": [
            {
                "source_id": item["source_id"],
                "title": item["title"],
                "technology": item["domain"],
                "recommended_action": "C" if downgraded_majority or {"vendor_claim", "marketing_language", "no_experiment_signal"} & set(item.get("risk_flags", [])) else item["recommended_action"],
                "rationale": "critic and risk adjusted deterministic brief action",
                "evidence_basis": f"source_tier={item['source_tier']}; score={_score_total(item.get('score', {}))}; evidence_count across metrics={sum((metric.get('evidence_count') or 0) for metric in network_trends.values())}",
                "constraint_risk": "; ".join(sorted({_constraint_label(finding) for finding in item.get("constraint_findings", [])})[:3]) or "extraction gap",
                "next_step": "plan guarded validation with fair baseline, tail latency/IPDV, operations, security, and degraded-process checks",
                "traceability": f"source_id={item['source_id']}",
            }
            for item in source_items
        ],
        "action_rationale": action_rationale,
        "follow_up_experiments": followups,
        "draft_delivery": {"mode": "draft_only", "requires_human_approval": True},
        "budget_context": {
            "budget_mode": budget_mode,
            "quality_priority": quality_priority,
            "estimated_quality_tier": "high" if quality_priority == "high" and not (vendor_ratio >= 0.4 or downgraded_majority) else "guarded",
            "budget_limited": budget_mode not in {"quality_first", "research", "flagship"},
            "budget_limited_sections": [] if budget_mode in {"quality_first", "research", "flagship"} else ["final_review", "additional_source_expansion"],
        },
        "guardrail_notes": [
            "Deterministic brief only; no model call was made.",
            "No network access or API key access was used.",
            "All source material remains untrusted content.",
            "External delivery is draft-only and requires human approval.",
        ],
    }
