from __future__ import annotations

from typing import Any, Dict, Iterable, List


NETWORK_METRICS = (
    "latency",
    "jitter_ipdv",
    "bandwidth_capacity",
    "reliability",
    "security",
    "operations",
    "ber_error",
    "scalability",
    "cost_power",
)


def _text(value: Any, fallback: str = "not available") -> str:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "; ".join(_text(item, fallback) for item in value) if value else fallback
    if isinstance(value, dict):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _cell(value: Any, fallback: str = "not available") -> str:
    return _text(value, fallback).replace("|", "\\|").replace("\n", " ")


def _bullets(items: Iterable[Any], fallback: str = "not available") -> list[str]:
    rows = []
    for item in items or []:
        if isinstance(item, dict):
            label = item.get("title") or item.get("direction") or item.get("claim") or item.get("constraint") or item.get("conflict_point")
            detail = item.get("rationale") or item.get("reason") or item.get("inclusion_reason") or item.get("message")
            rows.append(f"- {_cell(label)}" + (f": {_cell(detail)}" if detail else ""))
        else:
            rows.append(f"- {_cell(item)}")
    return rows or [f"- {fallback}"]


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    safe_rows = rows or [["not available" for _ in headers]]
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in safe_rows],
    ]


def _why_not_stronger(action: str, risks: Any) -> str:
    if action in {"S", "A"}:
        return "requires human final review plus operations/security/reliability validation"
    risk_text = _text(risks, "insufficient evidence")
    return f"{risk_text}; stronger action needs independent baseline, tail latency, and deployment evidence"


def _signal_radar_table(items: list[Dict[str, Any]]) -> list[str]:
    rows = []
    for item in items:
        rows.append(
            [
                item.get("direction"),
                item.get("signal_strength"),
                item.get("evidence_count"),
                item.get("recommended_action"),
                item.get("constraint_risks") or "insufficient evidence",
                _why_not_stronger(str(item.get("recommended_action", "D")), item.get("constraint_risks")),
            ]
        )
    return _table(["Direction", "Signal Strength", "Evidence Count", "Recommended Action", "Constraint Risks", "Why Not Stronger"], rows)


def _conflict_table(items: list[Dict[str, Any]]) -> list[str]:
    rows = []
    for item in items:
        rows.append(
            [
                item.get("conflict_point"),
                item.get("document_a_view"),
                item.get("document_b_view"),
                item.get("possible_explanation"),
                item.get("validation_needed"),
                item.get("severity"),
            ]
        )
    return _table(["Conflict Point", "Evidence A", "Evidence B", "Possible Explanation", "Validation Needed", "Severity"], rows)


def _constraint_rows(process: Dict[str, Any]) -> list[str]:
    constraints = process.get("most_frequent_constraints") or []
    if not constraints:
        return ["- No concrete constraint extracted; mark as evidence gap."]
    rows = []
    seen = set()
    for item in constraints:
        if isinstance(item, dict):
            label = _cell(item.get("constraint"), "No concrete constraint extracted; mark as evidence gap.")
            count = item.get("count", "not available")
            line = f"- {label} (count={count})"
        else:
            line = f"- {_cell(item, 'No concrete constraint extracted; mark as evidence gap.')}"
        if line not in seen:
            rows.append(line)
            seen.add(line)
    return rows or ["- No concrete constraint extracted; mark as evidence gap."]


def _network_metric_table(metrics: Dict[str, Any]) -> list[str]:
    rows = []
    for key in NETWORK_METRICS:
        item = metrics.get(key) if isinstance(metrics, dict) else {}
        if not isinstance(item, dict):
            item = {}
        rows.append(
            [
                key,
                item.get("dominant_impact", "?"),
                item.get("evidence_count", "not available"),
                item.get("risk_summary") or "insufficient evidence",
                item.get("required_validation") or "not available",
            ]
        )
    return _table(["Metric", "Dominant Impact", "Evidence Count", "Main Risks", "Required Validation"], rows)


def _evidence_summary(summary: Dict[str, Any]) -> list[str]:
    if not isinstance(summary, dict):
        return ["- Evidence quality summary: not available"]
    allowed = "yes" if summary.get("strong_conclusion_allowed") is True else "no"
    return [
        f"- Downgraded inputs: {_cell(summary.get('downgraded_count'))}",
        f"- Vendor/marketing/no-experiment risk inputs: {_cell(summary.get('vendor_or_marketing_risk_count'))}",
        f"- Strong conclusion allowed: {allowed}",
        f"- Missing baseline signals: {_cell(summary.get('missing_baseline_count', 'not available'))}",
        f"- Average-only signals: {_cell(summary.get('average_only_count', 'not available'))}",
        f"- No-experiment signals: {_cell(summary.get('no_experiment_count', 'not available'))}",
    ]


def _recommended_actions_table(actions: list[Dict[str, Any]]) -> list[str]:
    rows = []
    for item in actions:
        rows.append(
            [
                item.get("technology") or item.get("title"),
                item.get("recommended_action"),
                item.get("rationale") or item.get("reason"),
                item.get("evidence_basis"),
                item.get("constraint_risk"),
                item.get("next_step"),
                item.get("traceability") or item.get("source_id"),
            ]
        )
    return _table(["Technology / Source", "Action", "Rationale", "Evidence Basis", "Constraint Risk", "Next Step", "Traceability"], rows)


def render_brief_markdown(brief: Dict[str, Any], pipeline_run: Dict[str, Any] | None = None) -> str:
    """Render a human-review draft brief without raw source text or secret-bearing fields."""

    executive = brief.get("executive_brief") or {}
    process = brief.get("process_constraint_trends") or {}
    readiness = brief.get("decision_readiness") or {}
    quality = brief.get("insight_quality") or {}
    budget = brief.get("budget_context") or {}
    window = brief.get("window") or {}

    parts: List[str] = [
        "DRAFT ONLY — requires human approval before external delivery.",
        "",
        f"Generated at: {_cell(brief.get('generated_at'))}",
        f"Window: {_cell(window.get('hours'))}h ({_cell(window.get('start'))} to {_cell(window.get('end'))})",
    ]
    if pipeline_run:
        parts.append(f"Pipeline run: {_cell(pipeline_run.get('run_id'))}")

    parts.extend(
        [
            "",
            "## Executive Brief",
            "### Top Conclusions",
            *_bullets(executive.get("top_conclusions", []), "insufficient evidence"),
            "### Most Actionable Technologies",
            *_bullets(executive.get("most_actionable_technologies", []), "no actionable technology direction"),
            "### Biggest Risks",
            *_bullets(executive.get("biggest_risks", []), "not available"),
            "### Recommended Decisions",
            *_bullets(executive.get("recommended_decisions", []), "not available"),
            "",
            "## Technology Signal Radar",
            *_signal_radar_table(list(brief.get("technology_signal_radar") or [])),
            "",
            "## Cross-document Conflicts",
            *_conflict_table(list(brief.get("cross_document_conflicts") or [])),
            "",
            "## Process Constraint Trends",
            "### Most Frequent Constraints",
            *_constraint_rows(process),
            f"Dependency direction: {_cell(process.get('dependency_direction'), 'extraction gap')}",
            f"Degraded process robustness: {_cell(process.get('degraded_process_robustness_summary'), 'extraction gap')}",
            "",
            "## Network Metric Trends",
            *_network_metric_table(brief.get("network_metric_trends") or {}),
            "",
            "## Evidence Quality Summary",
            *_evidence_summary(brief.get("evidence_quality_summary") or {}),
            "",
            "## Recommended Actions",
            *_recommended_actions_table(list(brief.get("recommended_actions") or [])),
            "",
            "## Follow-up Experiments",
            *_bullets(brief.get("follow_up_experiments", []), "not available"),
            "",
            "## Decision Readiness",
            f"Ready for PoC: {_cell(readiness.get('ready_for_poc', False))}",
            f"Ready for management awareness: {_cell(readiness.get('ready_for_management_awareness', readiness.get('ready_for_management_brief', False)))}",
            f"Ready for management decision: {_cell(readiness.get('ready_for_management_decision', False))}",
            "Requires human review: true",
            "Blocking unknowns:",
            *_bullets(readiness.get("blocking_unknowns", []), "not available"),
            "Minimum validation before action:",
            *_bullets(readiness.get("minimum_validation_before_action", []), "not available"),
            "",
            "## Insight Quality",
            f"Overall confidence: {_cell(quality.get('overall_confidence'))}",
            f"Evidence weighting method: {_cell(quality.get('evidence_weighting_method'))}",
            "High-confidence claims:",
            *_bullets(quality.get("high_confidence_claims", []), "No high-confidence technical claim; only low-confidence signals."),
            "Low-confidence claims:",
            *_bullets(quality.get("low_confidence_claims", []), "not available"),
            "Rejected strong claims:",
            *_bullets(quality.get("rejected_strong_claims", []), "not available"),
            "",
            "## Budget Context",
            f"Budget mode: {_cell(budget.get('budget_mode'))}",
            f"Quality priority: {_cell(budget.get('quality_priority'))}",
            f"Estimated quality tier: {_cell(budget.get('estimated_quality_tier'))}",
            f"Budget limited: {_cell(budget.get('budget_limited', False))}",
            "",
            "## Human Approval Required",
            "Human approval required: true",
            "External Delivery Sent: false",
        ]
    )
    return "\n".join(parts).rstrip() + "\n"
