from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .full_paper_canonicalizer import canonicalize_full_paper_analysis
from .schema_validation import validate_json


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _finding(check: str, severity: str, message: str, status: str = "fail") -> Dict[str, str]:
    return {"check": check, "severity": severity, "status": status, "message": message}


def build_consistency_report(canonical: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    provenance = canonical["provenance"]
    if provenance["real_call_executed"] and provenance["analysis_mode"] != "model_backed_full_text_limited_analysis":
        findings.append(_finding("provenance", "major", "real-call provenance is inconsistent"))
    else:
        findings.append(_finding("provenance", "info", "model-backed full-text provenance is canonicalized", "pass"))
    if canonical["domains"]["primary_domain"] != "AI cluster networking":
        findings.append(_finding("domain", "major", "primary domain is not AI cluster networking"))
    else:
        findings.append(_finding("domain", "info", "primary domain corrected to AI cluster networking", "pass"))
    if "vendor_claim" in canonical.get("risk_flags", []):
        findings.append(_finding("risk_flags", "warning", "vendor_claim remains on an A-tier paper"))
    score_consistency = canonical["validation"]["score_consistency"]
    if score_consistency["score_total_mismatch"]:
        findings.append(_finding("score", "major", "score.total_score does not match component sum"))
    action_consistency = canonical["validation"]["action_consistency"]
    if action_consistency["score_action_mismatch"]:
        findings.append(_finding("action", "major", "recommended action is inconsistent with score band"))
    cost_power = canonical["network_impact_vector"].get("cost_power", {})
    if cost_power.get("impact") == "--" and "cost reduction" in str(cost_power.get("evidence", "")).lower():
        findings.append(_finding("network_impact_vector", "major", "cost reduction evidence has negative cost_power impact"))
    else:
        findings.append(_finding("network_impact_vector", "info", "cost_power direction is canonicalized", "pass"))
    for flag in ["failure_analysis_missing", "security_analysis_missing", "operations_evidence_incomplete", "reproducibility_incomplete"]:
        if flag in canonical.get("risk_flags", []):
            findings.append(_finding("missing_evidence", "warning", flag))
    ready = bool(canonical["validation"]["ready_for_three_paper_cross_validation"])
    return {
        "report_id": "consistency-" + canonical["canonical_analysis_id"],
        "canonical_analysis_id": canonical["canonical_analysis_id"],
        "title": canonical["source"]["title"],
        "ready_for_three_paper_cross_validation": ready,
        "readiness_blockers": canonical["validation"]["readiness_blockers"],
        "findings": findings,
        "hard_rule_violations": [item for item in findings if item["severity"] in {"major", "critical"} and item["status"] != "pass"],
        "runtime_boundary": {
            "network_used": False,
            "openrouter_called": False,
            "api_key_read": False,
            "email_sent": False,
            "webhook_sent": False,
            "codex_runtime_used": False,
        },
    }


def render_canonical_markdown(canonical: Dict[str, Any], report: Dict[str, Any]) -> str:
    niv = canonical["network_impact_vector"]
    rows = "\n".join(f"| {key} | {item.get('impact')} | {item.get('evidence')} | {item.get('risk')} |" for key, item in niv.items())
    findings = "\n".join(f"- [{item['severity']}] {item['check']}: {item['message']}" for item in report["findings"])
    experiments = canonical["cni_sections"].get("follow_up_validation_experiments", [])
    if isinstance(experiments, list):
        exp_text = "\n".join(f"- {item}" for item in experiments)
    else:
        exp_text = str(experiments)
    return f"""# {canonical['source']['title']}

## Provenance

- analysis_mode: {canonical['provenance']['analysis_mode']}
- model_backed: {canonical['provenance']['model_backed']}
- real_call_executed: {canonical['provenance']['real_call_executed']}
- normalization_applied: {canonical['provenance']['normalization_applied']}
- model_patch_assembly_applied: {canonical['provenance']['model_patch_assembly_applied']}

## Domains

- primary: {canonical['domains']['primary_domain']}
- secondary: {', '.join(canonical['domains']['secondary_domains'])}

## One-Sentence Conclusion

{canonical['cni_sections'].get('one_sentence_conclusion')}

## Mechanism

{canonical['cni_sections'].get('mechanism')}

## Process Constraints

{canonical['cni_sections'].get('process_constraints')}

## Constraint Dependency

{canonical['cni_sections'].get('constraint_dependency_analysis')}

## Degraded-Process Counterfactual

{canonical['cni_sections'].get('degraded_process_counterfactual')}

## Network Impact Vector

| Dimension | Impact | Evidence | Risk |
| --- | --- | --- | --- |
{rows}

## Evidence Quality

{canonical['evidence_quality']}

## Score And Action

- total_score: {canonical['score'].get('total_score')}
- component_sum_score: {canonical['validation']['score_consistency'].get('computed_component_sum')}
- score_action_mismatch: {canonical['action'].get('score_action_mismatch')}
- recommended_action: {canonical['action'].get('recommended_action')}
- score_suggested_action: {canonical['action'].get('score_suggested_action')}
- downgrade_reason: {canonical['action'].get('downgrade_reason')}

## Follow-Up Validation Experiments

{exp_text}

## Critic Findings

{findings}

## Three-Paper Cross-Validation Readiness

- ready_for_three_paper_cross_validation: {report['ready_for_three_paper_cross_validation']}
- blockers: {', '.join(report['readiness_blockers']) if report['readiness_blockers'] else 'none'}
"""


def review_full_paper_analysis(analysis_path: str | Path, run_audit_path: str | Path | None = None, output_dir: str | Path | None = None) -> Dict[str, Any]:
    analysis_path = Path(analysis_path)
    if not analysis_path.exists():
        raise FileNotFoundError(f"analysis JSON not found: {analysis_path}")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    run_audit = json.loads(Path(run_audit_path).read_text(encoding="utf-8")) if run_audit_path else None
    canonical = canonicalize_full_paper_analysis(analysis, run_audit)
    report = build_consistency_report(canonical)
    validate_json(canonical, "canonical_full_paper_analysis")
    out_dir = Path(output_dir) if output_dir else analysis_path.parent / "full_paper_review"
    out_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = out_dir / "canonical_full_paper_analysis.json"
    report_json_path = out_dir / ".full_paper_consistency_report.json"
    report_md_path = out_dir / ".full_paper_consistency_report.md"
    canonical_md_path = out_dir / "canonical_full_paper_analysis.md"
    canonical["artifact_paths"] = {
        "canonical_full_paper_analysis_json": str(canonical_path),
        "canonical_full_paper_analysis_md": str(canonical_md_path),
        "consistency_report_json": str(report_json_path),
        "consistency_report_md": str(report_md_path),
    }
    _write_json(canonical_path, canonical)
    _write_json(report_json_path, report)
    md = render_canonical_markdown(canonical, report)
    canonical_md_path.write_text(md, encoding="utf-8")
    report_md_path.write_text(md, encoding="utf-8")
    return {"canonical": canonical, "report": report, "artifacts": canonical["artifact_paths"]}
