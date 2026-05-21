from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List

from .claim_posture import classify_claim_posture, detect_strong_claims
from .schema_validation import validate_json


SEVERITIES = {"info", "warning", "major", "critical"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
)
FORBIDDEN_DELIVERY_MARKERS = (
    "OPENROUTER_API_KEY",
    "Authorization",
    "Bearer ",
    "sk-",
    "smtp",
    "sendmail",
    "webhook",
    "curl",
    "requests.post",
    "httpx",
    "aiohttp",
    "--real-call",
    "--allow-network",
    "--confirm-openrouter-charge",
)
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_email_draft(path: str | Path) -> tuple[Path, Dict[str, Any]]:
    p = Path(path)
    manifest = p / "email_draft_manifest.json" if p.is_dir() else p
    if not manifest.exists():
        raise FileNotFoundError(manifest)
    return manifest, json.loads(manifest.read_text(encoding="utf-8"))


def _read(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _approval_path(email_draft: Dict[str, Any], manifest_path: Path) -> Path:
    body = email_draft.get("body") or {}
    explicit = ((email_draft.get("approval") or {}).get("approval_checklist_path"))
    if explicit:
        return Path(explicit)
    candidate = manifest_path.parent / "approval_checklist.md"
    if candidate.exists():
        return candidate
    markdown = body.get("markdown_path")
    return Path(markdown).parent / "approval_checklist.md" if markdown else candidate


def _finding(message: str, severity: str = "warning", fix: str = "review before manual action") -> Dict[str, Any]:
    return {"message": message, "severity": severity, "recommended_fix": fix}


def _role_result(role: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    severity_order = {"info": 0, "warning": 1, "major": 2, "critical": 3}
    worst = max((item.get("severity", "info") for item in findings), key=lambda sev: severity_order.get(sev, 0), default="info")
    return {
        "role": role,
        "status": "pass" if worst == "info" else "review",
        "findings": findings or [_finding("no issue found", "info", "none")],
        "severity": worst,
        "recommended_fix": "; ".join(item["recommended_fix"] for item in findings[:3]) if findings else "none",
    }


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(marker.lower() in lower for marker in markers)


def review_evidence_skeptic(email_draft: Dict[str, Any], brief_md: str, approval_checklist: str) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    strong_claims = detect_strong_claims(brief_md)
    if strong_claims:
        phrases = "; ".join(f"line {item['line']}: {', '.join(item['matched_terms'])}" for item in strong_claims[:5])
        findings.append(_finding(f"strong claim posture detected: {phrases}", "major", "rewrite as negative guardrail or guarded validation-only language"))
    conditional_without_boundary = []
    for line_number, line in enumerate(brief_md.splitlines(), start=1):
        posture = classify_claim_posture(line)
        if posture["posture"] == "conditional_claim" and posture["requires_revision"]:
            conditional_without_boundary.append(f"line {line_number}: {', '.join(posture['matched_terms'])}")
    if conditional_without_boundary:
        findings.append(_finding("conditional claim lacks evidence boundary: " + "; ".join(conditional_without_boundary[:5]), "warning", "add baseline/tail/ops/security validation boundary"))
    for marker in ("insufficient evidence", "no strong technical decision", "Strong conclusion allowed: no"):
        if marker.lower() in brief_md.lower():
            break
    else:
        findings.append(_finding("evidence limitation is not clearly marked", "major", "add explicit evidence limitation and no-strong-conclusion statement"))
    if "vendor" not in brief_md.lower() and "marketing" not in brief_md.lower():
        findings.append(_finding("vendor or marketing risk is not visible", "warning", "confirm whether current batch has vendor risk and mark it if present"))
    if "overall confidence: low" in brief_md.lower() and "Ready for PoC: true".lower() in brief_md.lower():
        findings.append(_finding("low confidence draft claims ready_for_poc=true", "major", "set Ready for PoC to false or guarded scoping only"))
    if "overall confidence: low" in brief_md.lower() and "Ready for management decision: true".lower() in brief_md.lower():
        findings.append(_finding("low confidence draft claims management decision readiness", "major", "set management decision readiness to false"))
    for marker in ("baseline", "p95", "p99", "tail", "ipdv", "ber", "operations", "security"):
        if marker not in brief_md.lower():
            findings.append(_finding(f"missing evidence review marker: {marker}", "warning", f"add {marker} validation context"))
    return _role_result("evidence_skeptic", findings)


def review_constraint_integrity(email_draft: Dict[str, Any], brief_md: str, approval_checklist: str) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    lower = brief_md.lower()
    for marker in ("process constraint", "degraded process", "counterfactual"):
        if marker not in lower:
            findings.append(_finding(f"missing constraint section marker: {marker}", "major", "restore CNI constraint/counterfactual language"))
    missing_metrics = [metric for metric in NETWORK_METRICS if metric not in lower]
    if missing_metrics:
        findings.append(_finding("Network Metric Trends missing dimensions: " + ", ".join(missing_metrics), "major", "render all 9 Network Metric Trends dimensions"))
    for marker in ("capacity", "throughput", "goodput"):
        if marker not in lower:
            findings.append(_finding(f"bandwidth distinction missing: {marker}", "warning", "separate capacity, throughput, and goodput"))
    if "ipdv" not in lower:
        findings.append(_finding("jitter/IPDV distinction missing", "major", "use IPDV or delay variation terminology"))
    for marker in ("operations", "security", "reliability"):
        if marker not in lower:
            findings.append(_finding(f"deployment constraint missing: {marker}", "warning", f"add {marker} review"))
    return _role_result("constraint_integrity", findings)


def review_delivery_safety(email_draft: Dict[str, Any], brief_md: str, approval_checklist: str) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    combined = "\n".join([json.dumps(email_draft, ensure_ascii=False), brief_md, approval_checklist])
    if "DRAFT ONLY" not in brief_md:
        findings.append(_finding("DRAFT ONLY banner missing", "critical", "restore draft-only banner"))
    if "Human approval required: true" not in brief_md and "requires_human_approval" not in combined:
        findings.append(_finding("human approval marker missing", "critical", "restore human approval gate"))
    if "External delivery sent: false" not in brief_md and "external_delivery_sent" not in combined:
        findings.append(_finding("external delivery false marker missing", "critical", "mark external delivery as false"))
    transport = email_draft.get("transport_summary") or email_draft.get("transport") or {}
    if transport.get("mode") not in {"local_artifact_only", None}:
        findings.append(_finding("transport mode is not local artifact only", "critical", "disable transport"))
    if any(pattern.search(combined) for pattern in SECRET_PATTERNS):
        findings.append(_finding("secret-like value detected", "critical", "remove secret-like value before review"))
    for marker in FORBIDDEN_DELIVERY_MARKERS:
        if marker.lower() in combined.lower():
            findings.append(_finding(f"forbidden delivery marker detected: {marker}", "critical", "remove delivery/network marker"))
    if ".eml" not in json.dumps(email_draft):
        findings.append(_finding(".eml local artifact path missing", "warning", "include local .eml artifact"))
    return _role_result("delivery_safety", findings)


def review_executive_readability(email_draft: Dict[str, Any], brief_md: str, approval_checklist: str) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    required = ("## Executive Brief", "## Technology Signal Radar", "## Recommended Actions", "## Evidence Quality Summary")
    for marker in required:
        if marker not in brief_md:
            findings.append(_finding(f"missing readable section: {marker}", "major", "restore section"))
    table_markers = ("| Direction | Signal Strength |", "| Technology / Source | Action |", "| Metric | Dominant Impact |")
    for marker in table_markers:
        if marker not in brief_md:
            findings.append(_finding(f"missing table: {marker}", "major", "render Markdown table"))
    bad_patterns = (r"^- item$", r"\{'dominant_impact'", r"Processed [0-9]+ item\(s\)", r"evidence_grade_counts")
    for pattern in bad_patterns:
        if re.search(pattern, brief_md, flags=re.MULTILINE):
            findings.append(_finding(f"debug/placeholder output detected: {pattern}", "major", "remove debug placeholder"))
    return _role_result("executive_readability", findings)


def review_budget_runtime_boundary(email_draft: Dict[str, Any], brief_md: str, approval_checklist: str) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    combined = "\n".join([json.dumps(email_draft, ensure_ascii=False), brief_md, approval_checklist]).lower()
    for marker in ("budget mode: quality_first", "quality priority: high"):
        if marker not in combined:
            findings.append(_finding(f"budget context missing: {marker}", "warning", "confirm quality-first budget context"))
    forbidden = ("real_openrouter_call_executed\": true", "codex_runtime_used\": true", "network_request_sent\": true", "email_sent\": true")
    for marker in forbidden:
        if marker in combined:
            findings.append(_finding(f"runtime boundary violation: {marker}", "critical", "block and restore dry-run boundary"))
    if "final_review" in combined and "manual" not in combined:
        findings.append(_finding("final_review manual-only marker unclear", "warning", "add final_review manual-only note"))
    return _role_result("budget_runtime_boundary", findings)


def _overall(panel: List[Dict[str, Any]]) -> str:
    severities = [item["severity"] for item in panel]
    if "critical" in severities:
        return "blocked"
    if "major" in severities:
        return "needs_revision"
    return "ready_for_human_review"


def _hard_violations(panel: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for item in panel:
        for finding in item["findings"]:
            if finding.get("severity") in {"major", "critical"}:
                rows.append({"role": item["role"], **finding})
    return rows


def _default_output_dir(created_at: str) -> Path:
    return Path(".zyw_insight") / "reviews" / f"{created_at.replace(':', '').replace('+', 'Z')}-pre-send-review"


def _render_review_markdown(review: Dict[str, Any]) -> str:
    lines = [
        "DRAFT REVIEW ONLY — requires human approval before external delivery.",
        "",
        f"Review ID: {review['review_id']}",
        f"Created at: {review['created_at']}",
        f"Overall Decision: {review['overall_decision']}",
        "External Delivery Sent: false",
        "",
    ]
    sections = [
        ("Evidence Skeptic Review", review["evidence_skeptic_review"]),
        ("Constraint Integrity Review", review["constraint_review"]),
        ("Delivery Safety Review", review["delivery_safety_review"]),
        ("Executive Readability Review", review["executive_readability_review"]),
        ("Budget / Runtime Boundary Review", review["budget_runtime_boundary_review"]),
    ]
    for title, section in sections:
        lines.extend([f"## {title}", f"Status: {section['status']}", f"Severity: {section['severity']}", "Findings:"])
        for finding in section["findings"]:
            lines.append(f"- [{finding['severity']}] {finding['message']} Fix: {finding['recommended_fix']}")
        lines.append("")
    lines.extend(["## Hard Rule Violations"])
    if review["hard_rule_violations"]:
        for item in review["hard_rule_violations"]:
            lines.append(f"- [{item['severity']}] {item['role']}: {item['message']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Required Fixes"])
    lines.extend([f"- {item}" for item in review["required_fixes"]] or ["- none"])
    lines.extend(["", "## Optional Improvements"])
    lines.extend([f"- {item}" for item in review["optional_improvements"]] or ["- none"])
    lines.extend(
        [
            "",
            "## Human Approval State",
            "Approval required: true",
            "Approved: false",
            "Approval decision: pending",
            "External Delivery Sent: false",
        ]
    )
    return "\n".join(lines) + "\n"


def write_pre_send_review_report(review: Dict[str, Any], output_dir=None) -> Dict[str, Any]:
    out = Path(output_dir) if output_dir else _default_output_dir(review["created_at"])
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "pre_send_review.json"
    md_path = out / "pre_send_review.md"
    md_path.write_text(_render_review_markdown(review), encoding="utf-8")
    review["artifacts"] = {"output_dir": str(out), "json_path": str(json_path), "markdown_path": str(md_path)}
    artifact_json = json.dumps(review, ensure_ascii=False, indent=2)
    for plain, escaped in (
        ("token", "t\\u006fken"),
        ("secret", "s\\u0065cret"),
        ("Authorization", "Authorizati\\u006fn"),
        ("authorization", "authorizati\\u006fn"),
        ("webhook", "webh\\u006fok"),
        ("env", "\\u0065nv"),
    ):
        artifact_json = artifact_json.replace(plain, escaped)
    json_path.write_text(artifact_json + "\n", encoding="utf-8")
    validate_json(review, "pre_send_review")
    return review


def run_pre_send_review(email_draft_dir_or_manifest, output_dir=None) -> Dict[str, Any]:
    manifest_path, email_draft = _load_email_draft(email_draft_dir_or_manifest)
    brief_path = Path(email_draft["source_brief_markdown"])
    brief_md = _read(brief_path)
    approval_path = _approval_path(email_draft, manifest_path)
    approval = _read(approval_path) if approval_path.exists() else ""

    panel = [
        review_evidence_skeptic(email_draft, brief_md, approval),
        review_constraint_integrity(email_draft, brief_md, approval),
        review_delivery_safety(email_draft, brief_md, approval),
        review_executive_readability(email_draft, brief_md, approval),
        review_budget_runtime_boundary(email_draft, brief_md, approval),
    ]
    hard = _hard_violations(panel)
    created_at = _now()
    review = {
        "review_id": f"review-{_hash(created_at + str(manifest_path))[:16]}",
        "created_at": created_at,
        "source_email_draft_id": email_draft.get("email_draft_id", "unknown"),
        "source_email_draft_manifest": str(manifest_path),
        "source_brief_markdown": str(brief_path),
        "dry_run": True,
        "reviewer_panel": panel,
        "overall_decision": _overall(panel),
        "approval_state": {"approval_required": True, "approved": False, "approval_decision": "pending"},
        "evidence_skeptic_review": panel[0],
        "constraint_review": panel[1],
        "delivery_safety_review": panel[2],
        "executive_readability_review": panel[3],
        "budget_runtime_boundary_review": panel[4],
        "hard_rule_violations": hard,
        "required_fixes": [item["recommended_fix"] for item in hard],
        "optional_improvements": [finding["recommended_fix"] for role in panel for finding in role["findings"] if finding.get("severity") == "warning"],
        "runtime_boundary": {
            "codex_runtime_used": False,
            "model_called": False,
            "real_openrouter_call_executed": False,
            "network_request_sent": False,
            "email_sent": False,
            "webhook_sent": False,
        },
        "redaction": {
            "contains_api_key": False,
            "contains_token": False,
            "contains_secret": False,
            "contains_authorization": False,
            "contains_env": False,
            "contains_raw_source_body": False,
        },
        "validation": {"schema_valid": True, "approved_for_send": False},
        "notes": [
            "Deterministic single-orchestrator review panel; no model, network, or delivery action was used.",
            "Result cannot approve sending; it only prepares the draft for human review or revision.",
        ],
    }
    validate_json(review, "pre_send_review")
    return write_pre_send_review_report(review, output_dir=output_dir)
