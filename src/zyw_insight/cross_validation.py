from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .schema_validation import NETWORK_IMPACT_KEYS, validate_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score(analysis: Dict[str, Any]) -> float:
    score = analysis.get("score") or {}
    try:
        return float(score.get("total_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def build_cross_validation_report(items: list[Dict[str, Any]], real_call: Dict[str, Any] | None = None) -> Dict[str, Any]:
    created_at = _now()
    seed = json.dumps([item.get("candidate_id") for item in items], sort_keys=True)
    extraction_sufficient = [bool((item.get("fulltext_artifact") or {}).get("section_hints", {}).get("abstract") and (item.get("fulltext_artifact") or {}).get("section_hints", {}).get("method_or_design") and (item.get("fulltext_artifact") or {}).get("section_hints", {}).get("evaluation_or_experiments")) for item in items]
    limitations = []
    if len(items) < 3:
        limitations.append("fewer than three eligible open-access A/B + High papers were available")
    if not items or not all(extraction_sufficient):
        limitations.append("one or more papers have partial or unverified extraction; report is not full-paper cross-validation")

    papers = []
    for item in items:
        analysis = item.get("analysis") or {}
        artifact = item.get("fulltext_artifact") or {}
        papers.append(
            {
                "candidate_id": item.get("candidate_id"),
                "title": analysis.get("title") or item.get("title"),
                "source_tier": analysis.get("source_tier"),
                "domain": analysis.get("domain"),
                "extraction_quality": artifact.get("extraction_quality", "missing"),
                "score": analysis.get("score", {}),
                "recommended_action": analysis.get("recommended_action", "D"),
            }
        )

    network_compare = {}
    for key in NETWORK_IMPACT_KEYS:
        network_compare[key] = [
            {
                "candidate_id": item.get("candidate_id"),
                "impact": (((item.get("analysis") or {}).get("network_impact_vector") or {}).get(key) or {}).get("impact", "?"),
                "risk": (((item.get("analysis") or {}).get("network_impact_vector") or {}).get(key) or {}).get("risk", "not available"),
            }
            for item in items
        ]

    report = {
        "report_id": "cross-" + hashlib.sha256((seed + created_at).encode("utf-8")).hexdigest()[:16],
        "created_at": created_at,
        "papers": papers,
        "common_themes": ["datacenter network performance and constraint-aware validation"] if items else [],
        "conflicting_claims": ["insufficient comparable full-text evidence to assert contradictions"] if len(items) < 2 else [],
        "constraint_comparison": [
            {
                "candidate_id": item.get("candidate_id"),
                "constraints": (item.get("analysis") or {}).get("process_constraints", []),
                "dependency_note": "compare explicit process constraints separately from inferred constraints",
            }
            for item in items
        ],
        "network_impact_comparison": network_compare,
        "evidence_quality_comparison": {
            "scores": [{"candidate_id": item.get("candidate_id"), "score": _score(item.get("analysis") or {})} for item in items],
            "baseline_fairness_required": True,
            "tail_metrics_required": True,
        },
        "degraded_process_counterfactual_comparison": [
            {
                "candidate_id": item.get("candidate_id"),
                "counterfactual": (item.get("analysis") or {}).get("degraded_process_counterfactual", "requires validation"),
            }
            for item in items
        ],
        "baseline_fairness_comparison": {
            "status": "requires_human_review",
            "note": "baseline fairness cannot be proven from partial extraction alone",
        },
        "operations_security_comparison": {
            "status": "requires_human_review",
            "note": "production-like claims require operations, security, reliability, rollback, observability, and failure evidence",
        },
        "strategic_route": "Use these papers as candidates for guarded validation planning, not production decision.",
        "recommended_experiments": [
            "reproduce p95/p99/worst-case latency against a fair baseline",
            "measure IPDV/delay variation explicitly",
            "separate capacity, available capacity, throughput, and goodput",
            "run failure, rollback, observability, and security validation",
        ],
        "action_summary": "full_text_limited_cross_validation" if items else "failed_closed_no_eligible_fulltext_candidates",
        "confidence": "low" if limitations else "medium",
        "limitations": limitations,
        "runtime_boundary": {
            "cross_validation_real_call_executed": bool(real_call and real_call.get("real_call_executed")),
            "final_review_real_call_executed": False,
            "brief_synthesis_real_call_executed": False,
            "email_sent": False,
            "webhook_sent": False,
            "codex_runtime_used": False,
        },
        "redaction": {
            "full_text_in_report": False,
            "model_response_content_stored": False,
            "reasoning_stored": False,
            "messages_stored": False,
        },
        "validation": {
            "schema_valid": True,
            "claims_full_paper_cross_validation": False,
            "analysis_label": "full_text_limited_cross_validation",
            "paper_count": len(items),
        },
    }
    validate_json(report, "cross_validation_report")
    return report


def render_cross_validation_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Three-paper Cross-validation CNI Report",
        "",
        f"Report ID: {report['report_id']}",
        f"Confidence: {report['confidence']}",
        f"Action summary: {report['action_summary']}",
        "",
        "## Papers",
    ]
    for paper in report.get("papers") or []:
        lines.append(f"- {paper.get('candidate_id')}: {paper.get('title')} ({paper.get('extraction_quality')})")
    lines += ["", "## Limitations"]
    for item in report.get("limitations") or ["none"]:
        lines.append(f"- {item}")
    lines += ["", "## Recommended Experiments"]
    for item in report.get("recommended_experiments") or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_cross_validation_artifacts(report: Dict[str, Any], output_dir: str | Path) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "cross_validation_report.json"
    md_path = out / "cross_validation_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_cross_validation_markdown(report), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(md_path)}
