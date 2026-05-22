from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib import request as urllib_request

from .analyzer import analyze_source
from .cni_schema_normalizer import normalize_literature_analysis_candidate, validate_normalized_literature_analysis
from .cni_model_assembler import assemble_literature_analysis_from_model_patch
from .critic import critique_analysis
from .cross_validation import build_cross_validation_report, write_cross_validation_artifacts
from .fulltext_eligibility import evaluate_fulltext_eligibility, load_fulltext_policy, select_fulltext_candidates
from .fulltext_fetch import fetch_and_extract_fulltext
from .model_router import validate_openrouter_model_id
from .openrouter_canary import execute_openrouter_canary, execute_openrouter_one_shot_fulltext, normalize_internal_model_id
from .schema_validation import validate_json
from .source_discovery import discover_sources
from .token_budget import build_prompt_inclusion_audit, load_fulltext_token_policy, select_fulltext_under_token_cap, validate_one_shot_token_budget
from .triage import triage_source


DEFAULT_MODEL = "openrouter/qwen/qwen3.5-397b-a17b"
CNI_REQUIRED_SECTIONS = [
    "basic_info",
    "one_sentence_conclusion",
    "problem_background",
    "core_idea",
    "contributions",
    "mechanism",
    "process_constraints",
    "constraint_dependency_analysis",
    "degraded_process_counterfactual",
    "network_impact_vector",
    "evidence_quality",
    "comparison_with_existing_technology",
    "hidden_assumptions_and_risks",
    "security_and_operations_impact",
    "reproducibility",
    "technical_insights",
    "strategic_significance",
    "score",
    "recommended_action",
    "follow_up_validation_experiments",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ts(ts: str) -> str:
    return ts.replace(":", "").replace("+", "Z")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _default_one_dir(created_at: str) -> Path:
    return Path(".zyw_insight") / "full_paper_canaries" / f"{_safe_ts(created_at)}-full-paper-canary"


def _default_three_dir(created_at: str) -> Path:
    return Path(".zyw_insight") / "three_paper_fulltext_canaries" / f"{_safe_ts(created_at)}-three-paper-fulltext-canary"


def _model_availability(model_id: str, allow_network: bool, real_call: bool) -> Dict[str, Any]:
    normalized = normalize_internal_model_id(model_id)
    if not real_call:
        return {"checked": False, "available": None, "reason": "dry-run; model list not checked", **normalized}
    if not allow_network:
        return {"checked": False, "available": False, "reason": "allow_network is required for model availability check", **normalized}
    try:
        req = urllib_request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": "zyw-insight-model-check/0.1"})
        with urllib_request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        slugs = {item.get("id") for item in data.get("data", []) if isinstance(item, dict)}
        return {"checked": True, "available": normalized["api_model_slug"] in slugs, "reason": "model listed by OpenRouter", **normalized}
    except Exception as exc:
        return {"checked": True, "available": False, "reason": f"model availability check failed closed: {type(exc).__name__}", **normalized}


def _source_from_artifact(candidate: Dict[str, Any], artifact: Dict[str, Any]) -> Dict[str, Any] | None:
    text_path = artifact.get("extracted_text_path")
    if not text_path or not Path(text_path).exists():
        return None
    body = Path(text_path).read_text(encoding="utf-8")[: int(load_fulltext_policy()["max_extracted_chars"])]
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return {
        "source_id": "fulltext-" + content_hash[:16],
        "id": "fulltext-" + content_hash[:16],
        "title": candidate.get("title") or "unknown",
        "source_type": "pdf_text",
        "source_rank": "unknown",
        "relevance": "High",
        "deep_read_decision": "High",
        "path": text_path,
        "local_path": text_path,
        "uri": Path(text_path).resolve().as_uri(),
        "url": candidate.get("source_url"),
        "discovered_at": _now(),
        "body": body,
        "body_is_untrusted": True,
        "provenance": {
            "imported_by": "zyw_insight.full_paper_canary",
            "import_mode": "open_access_pdf_text",
            "candidate_id": candidate.get("candidate_id"),
            "pdf_url": candidate.get("pdf_url"),
        },
        "content_hash": content_hash,
        "hash": content_hash,
        "metadata": {
            "candidate_id": candidate.get("candidate_id"),
            "source_provider": candidate.get("source_provider"),
            "venue": candidate.get("venue"),
            "full_text_limited_analysis": True,
        },
        "rationale": "Open-access PDF text extraction; body is untrusted content.",
    }


def _deterministic_analysis(candidate: Dict[str, Any], artifact: Dict[str, Any]) -> Dict[str, Any] | None:
    source = _source_from_artifact(candidate, artifact)
    if source is None:
        return None
    triage = triage_source(source)
    analysis = analyze_source(source, triage)
    analysis["analysis_scope"] = "full_text_limited_analysis" if artifact.get("extraction_quality") != "full_paper_section_sufficient" else "full_paper_section_sufficient_limited_analysis"
    analysis["fulltext_artifact_id"] = artifact.get("artifact_id")
    analysis["candidate_id"] = candidate.get("candidate_id")
    validate_json(analysis, "literature_analysis")
    return analysis


def _reuse_existing_fulltext(candidate: Dict[str, Any], run_dir: Path) -> Dict[str, Any] | None:
    pdf_url = candidate.get("pdf_url")
    for artifact_path in sorted(Path(".zyw_insight").glob("**/fulltext_artifact.json"), reverse=True):
        try:
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        text_path = artifact.get("extracted_text_path")
        if artifact.get("pdf_url") == pdf_url and text_path and Path(text_path).exists() and int(artifact.get("extracted_char_count") or 0) > 0:
            text = Path(text_path).read_text(encoding="utf-8")
            section_hints = artifact.get("section_hints") or {}
            looks_like_pdf_bytes = text.lstrip().startswith("%PDF-") or " endobj " in text[:5000]
            has_core_sections = bool(section_hints.get("abstract") and section_hints.get("method_or_design") and section_hints.get("evaluation_or_experiments"))
            if looks_like_pdf_bytes or not has_core_sections:
                continue
            target_dir = run_dir / "fulltext"
            target_dir.mkdir(parents=True, exist_ok=True)
            reused_text = target_dir / f"{artifact.get('artifact_id', 'reused-fulltext')}.txt"
            reused_text.write_text(text, encoding="utf-8")
            reused = dict(artifact)
            reused["status"] = "reused_existing_extraction"
            reused["pdf_path"] = artifact.get("pdf_path")
            reused["extracted_text_path"] = str(reused_text)
            reused["runtime_boundary"] = dict(reused.get("runtime_boundary") or {})
            reused["runtime_boundary"]["network_request_sent"] = False
            reused["runtime_boundary"]["reused_existing_extraction"] = True
            _write_json(target_dir / "fulltext_artifact.json", reused)
            return reused
    return None


def _cni_sections_present(analysis: Dict[str, Any] | None) -> list[str]:
    if not isinstance(analysis, dict):
        return []
    return [key for key in CNI_REQUIRED_SECTIONS if key in analysis]


def _redacted_canary_summary(canary: Dict[str, Any] | None) -> Dict[str, Any]:
    if not canary:
        return {"real_call_executed": False, "status": "not_run"}
    return {
        "canary_run_id": canary.get("canary_run_id"),
        "stage": canary.get("stage"),
        "real_call_executed": canary.get("real_call_executed"),
        "dry_run": canary.get("dry_run"),
        "internal_model_id": canary.get("internal_model_id"),
        "api_model_slug": canary.get("api_model_slug"),
        "response_status": (canary.get("response") or {}).get("status"),
        "usage": canary.get("usage"),
        "cost": canary.get("cost"),
        "runtime_boundary": canary.get("runtime_boundary"),
        "validation": canary.get("validation"),
    }


def _discover(query_profile: str, providers: list[str] | None, max_candidates: int, arxiv_id: str | None = None) -> Dict[str, Any]:
    return discover_sources(query_profile=query_profile, providers=providers, max_candidates=max_candidates, dry_run=False, network_enabled=True, metadata_only=True, arxiv_id=arxiv_id)


def run_full_paper_canary(
    query_profile: str = "datacenter_networking",
    providers: list[str] | None = None,
    max_candidates: int = 20,
    internal_model_id: str = DEFAULT_MODEL,
    environment: str = "quality_first",
    spent_usd: float = 0,
    max_cost_usd: float = 5,
    real_call: bool = False,
    allow_network: bool = False,
    confirm_charge: bool = False,
    output_dir: str | Path | None = None,
    write_ledger: bool = True,
    arxiv_id: str | None = None,
    one_shot_fulltext: bool = False,
    allow_fulltext_prompt: bool = False,
    target_input_tokens: int | None = None,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
    max_total_tokens: int | None = None,
    min_input_tokens_required: int | None = None,
    min_output_tokens_expected: int | None = None,
    fail_if_input_under_min: bool = False,
    fail_if_total_exceeds_context: bool = False,
    require_schema_valid_output: bool = False,
) -> Dict[str, Any]:
    validate_openrouter_model_id(internal_model_id)
    created_at = _now()
    run_dir = Path(output_dir) if output_dir else _default_one_dir(created_at)
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = run_dir / "redacted_ledger.jsonl"
    model_check = _model_availability(internal_model_id, allow_network=allow_network, real_call=real_call)

    discovery = _discover(query_profile, providers, max_candidates, arxiv_id=arxiv_id)
    _write_json(run_dir / "discovery_run.json", discovery)
    policy = load_fulltext_policy()
    selected = select_fulltext_candidates(discovery.get("candidates") or [], 1, policy)
    status = "selected" if selected else "failed_closed_no_eligible_open_access_ab_high_candidate"
    candidate = selected[0]["candidate"] if selected else None
    eligibility = selected[0]["eligibility"] if selected else None
    if candidate is None:
        eligibility = {
            "candidate_id": "none",
            "source_provider": "none",
            "pdf_url": None,
            "source_url": None,
            "open_access": False,
            "eligibility_reason": "no A/B + High open-access candidate found; C/D candidates blocked",
            "fetch_allowed": False,
            "paywall_bypass": False,
            "pdf_download_allowed": False,
            "max_pdf_bytes": int(policy["max_pdf_bytes"]),
            "max_pages": int(policy["max_pages"]),
            "max_extracted_chars": int(policy["max_extracted_chars"]),
            "runtime_boundary": {"open_access_only": True, "arbitrary_url_fetch_enabled": False, "paywall_bypass_enabled": False, "credentials_used": False, "publisher_pdf_fetch_enabled": False, "codex_runtime_used": False},
        }
    _write_json(run_dir / "fulltext_eligibility.json", eligibility)

    fetch_dry_run = (not real_call) and not (one_shot_fulltext and allow_network)
    artifact = fetch_and_extract_fulltext(candidate or {"candidate_id": "none"}, eligibility, run_dir / "fulltext", allow_network=allow_network, dry_run=fetch_dry_run, policy=policy)
    if one_shot_fulltext and candidate and not artifact.get("extracted_text_path"):
        reused = _reuse_existing_fulltext(candidate, run_dir)
        if reused:
            artifact = reused
    analysis = _deterministic_analysis(candidate, artifact) if candidate else None
    if analysis:
        _write_json(run_dir / "full_paper_analysis.json", analysis)
        critic = critique_analysis(analysis)
        validate_json(critic, "constraint_critic")
        _write_json(run_dir / "constraint_critic.json", critic)
    else:
        critic = None

    canary = None
    one_shot_run = None
    prompt_audit = None
    normalized_model_analysis = None
    raw_model_cni_schema_valid = False
    normalized_cni_schema_valid = False
    normalization_applied = False
    normalization_audit_path = None
    schema_failure_reason = None
    raw_response_sha256 = None
    raw_response_length = None
    if one_shot_fulltext and candidate:
        token_policy = load_fulltext_token_policy()
        min_input = int(min_input_tokens_required or token_policy["min_input_tokens_required"])
        target_input = int(target_input_tokens or token_policy["target_input_tokens"])
        max_input = int(max_input_tokens or token_policy["max_input_tokens_hard"])
        max_output = int(max_output_tokens or token_policy["max_output_tokens_hard"])
        min_output = int(min_output_tokens_expected or token_policy["min_output_tokens_expected"])
        max_total = int(max_total_tokens or token_policy["max_total_tokens_hard"])
        text_path = artifact.get("extracted_text_path")
        selected_text = ""
        if text_path and Path(text_path).exists():
            extracted_text = Path(text_path).read_text(encoding="utf-8")
            selection = select_fulltext_under_token_cap(extracted_text, target_input, max_input, internal_model_id)
            selected_text = selection["selected_text"]
            prompt_audit = build_prompt_inclusion_audit(
                artifact.get("extracted_text_sha256") or hashlib.sha256(extracted_text.encode("utf-8")).hexdigest(),
                int(artifact.get("extracted_char_count") or len(extracted_text)),
                selection,
                min_input,
                target_input,
                max_input,
                max_output,
                max_total,
            )
            prompt_audit["token_budget_validation"] = validate_one_shot_token_budget(selection["estimated_input_tokens"], max_output, max_total)
            validate_json(prompt_audit, "fulltext_prompt_audit")
            _write_json(run_dir / "fulltext_prompt_audit.json", prompt_audit)
        planned_under_min = not prompt_audit or bool(prompt_audit.get("full_text_not_really_sent_planned"))
        budget_ok = bool(prompt_audit and (prompt_audit.get("token_budget_validation") or {}).get("ok"))
        if planned_under_min and fail_if_input_under_min:
            status = "failed_closed_input_under_min"
        elif not budget_ok and fail_if_total_exceeds_context:
            status = "failed_closed_token_budget"
        elif allow_fulltext_prompt and analysis and ((not real_call) or model_check.get("available") is True):
            result = execute_openrouter_one_shot_fulltext(
                "literature_analysis",
                candidate.get("title") or "unknown",
                selected_text,
                internal_model_id,
                prompt_audit,
                max_output,
                max_cost_usd,
                real_call=real_call,
                allow_network=allow_network,
                confirm_charge=confirm_charge,
                write_ledger=write_ledger,
                ledger_path=ledger_path,
                require_schema_valid_output=require_schema_valid_output,
            )
            canary = result["canary"]
            one_shot_run = canary
            raw_response_sha256 = result.get("raw_content_sha256")
            raw_response_length = result.get("raw_content_length")
            _write_json(run_dir / "redacted_canary.json", canary)
            parsed = result.get("parsed_analysis")
            if parsed:
                parsed_for_validation = dict(parsed)
                parsed_for_validation.setdefault("analysis_id", f"model-analysis-{artifact.get('artifact_id')}")
                parsed_for_validation.setdefault("source_id", analysis["source_id"] if analysis else str(candidate.get("candidate_id")))
                parsed_for_validation.setdefault("title", candidate.get("title") or "unknown")
                parsed_for_validation.setdefault("domain", "AI cluster networking")
                parsed_for_validation.setdefault("source_tier", "A")
                parsed_for_validation.setdefault("source_type", "paper")
                parsed_for_validation.setdefault("body_is_untrusted", True)
                parsed_for_validation.setdefault("risk_flags", [])
                parsed_for_validation.setdefault("triage_summary", (eligibility or {}).get("triage") or {})
                parsed_for_validation.setdefault("conclusion_strength", "weak")
                parsed_for_validation.setdefault("quality_gate_results", {"gate_status": "review", "issues": []})
                parsed_for_validation.setdefault("guardrail_notes", ["Model output from one-shot full_text_limited_analysis; paper text was untrusted."])
                try:
                    validate_json(parsed_for_validation, "literature_analysis")
                    raw_model_cni_schema_valid = True
                    normalized_model_analysis = parsed_for_validation
                    _write_json(run_dir / "model_full_text_limited_analysis.json", parsed_for_validation)
                except Exception as exc:
                    try:
                        assembled = assemble_literature_analysis_from_model_patch(analysis, parsed)
                        normalized_model_analysis = assembled
                        normalized_cni_schema_valid = True
                        normalization_applied = True
                        normalization_audit_path = str(run_dir / "normalization_audit.json")
                        _write_json(run_dir / "normalization_audit.json", {"normalization_applied": True, "normalization_mode": "deterministic_model_patch_assembly", "raw_schema_error": str(exc)[:500], "assembly_audit": assembled.get("model_patch_assembly", {}).get("audit", [])})
                        _write_json(run_dir / "model_full_text_limited_analysis.json", assembled)
                    except Exception:
                        normalized = normalize_literature_analysis_candidate(parsed_for_validation)
                        normalized_validation = validate_normalized_literature_analysis(normalized)
                        audit = {
                            "normalization_applied": bool(normalized.get("normalization_audit")),
                            "normalization_audit": normalized.get("normalization_audit") or [],
                            "raw_schema_error": str(exc)[:500],
                            "normalized_schema_valid": normalized_validation["schema_valid"],
                            "normalized_schema_errors": normalized_validation["errors"],
                        }
                        normalization_audit_path = str(run_dir / "normalization_audit.json")
                        _write_json(run_dir / "normalization_audit.json", audit)
                        normalization_applied = bool(normalized.get("normalization_audit"))
                        normalized_cni_schema_valid = bool(normalized_validation["schema_valid"])
                        if normalized_cni_schema_valid:
                            normalized_model_analysis = normalized
                            _write_json(run_dir / "model_full_text_limited_analysis.json", normalized)
                        else:
                            schema_failure_reason = "; ".join(normalized_validation["errors"]) or str(exc)[:500]
                            _write_json(run_dir / "model_analysis_parse_failure.json", {"status": "schema_validation_failed", "error": schema_failure_reason[:500], "raw_content_sha256": result.get("raw_content_sha256"), "raw_content_length": result.get("raw_content_length"), "raw_content_redacted": True})
            elif real_call:
                schema_failure_reason = "model response did not parse as JSON"
                _write_json(run_dir / "model_analysis_parse_failure.json", {"status": "json_parse_failed", "error": schema_failure_reason, "raw_content_sha256": result.get("raw_content_sha256"), "raw_content_length": result.get("raw_content_length"), "raw_content_redacted": True})
        else:
            one_shot_run = {
                "response": {"status": "dry_run" if not real_call else "not_executed"},
                "usage": {"actual_input_tokens": None, "actual_output_tokens": None},
                "cost": {"actual_cost_usd": None, "max_cost_usd": max_cost_usd},
            }
            _write_json(run_dir / "redacted_canary.json", {"real_call_executed": False, "status": one_shot_run["response"]["status"], "one_shot_fulltext_attempt": True})
        if canary:
            one_shot_run = canary
        actual_input = (one_shot_run or {}).get("usage", {}).get("actual_input_tokens") if one_shot_run else None
        actual_output = (one_shot_run or {}).get("usage", {}).get("actual_output_tokens") if one_shot_run else None
        sections = _cni_sections_present(normalized_model_analysis if real_call else (normalized_model_analysis or analysis))
        model_sections = _cni_sections_present(normalized_model_analysis)
        full_text_not_really_sent = bool(real_call and ((actual_input is None) or int(actual_input) < 8000))
        analysis_too_short = bool(real_call and ((actual_output is None) or int(actual_output) < 1500) and len(model_sections) < len(CNI_REQUIRED_SECTIONS))
        analysis_run = {
            "analysis_level": "full_text_limited_analysis",
            "one_shot_fulltext_attempt": True,
            "extracted_char_count": int(artifact.get("extracted_char_count") or 0),
            "included_char_count": int((prompt_audit or {}).get("included_char_count") or 0),
            "estimated_input_tokens": int((prompt_audit or {}).get("estimated_input_tokens") or 0),
            "rough_estimated_input_tokens": int((prompt_audit or {}).get("rough_estimated_input_tokens") or 0),
            "conservative_estimated_input_tokens": int((prompt_audit or {}).get("conservative_estimated_input_tokens") or 0),
            "actual_input_tokens": actual_input,
            "requested_max_output_tokens": int(max_output),
            "actual_output_tokens": actual_output,
            "actual_input_over_max_input_hard": bool(real_call and actual_input is not None and int(actual_input) > int(max_input)),
            "expected_actual_input_safe": bool((prompt_audit or {}).get("expected_actual_input_safe")),
            "require_schema_valid_output": bool(require_schema_valid_output),
            "raw_model_cni_schema_valid": bool(raw_model_cni_schema_valid),
            "normalized_cni_schema_valid": bool(normalized_cni_schema_valid),
            "normalization_applied": bool(normalization_applied),
            "normalization_audit_path": normalization_audit_path,
            "model_cni_schema_valid": bool(raw_model_cni_schema_valid or normalized_cni_schema_valid),
            "normalization_required": bool(real_call and not normalized_model_analysis),
            "schema_failure_reason": schema_failure_reason,
            "raw_response_sha256": raw_response_sha256,
            "raw_response_length": raw_response_length,
            "full_paper_analysis_path": str(run_dir / "model_full_text_limited_analysis.json") if normalized_model_analysis else None,
            "full_text_not_really_sent": full_text_not_really_sent,
            "analysis_too_short_for_cni": analysis_too_short,
            "cni_sections_present": sections,
            "cni_section_count": len(sections),
            "redaction": {
                "messages_redacted": True,
                "messages_sha256_present": bool((one_shot_run or {}).get("request", {}).get("messages_sha256")),
                "response_content_redacted": True,
                "reasoning_redacted": True,
                "ledger_redacted": True,
            },
            "runtime_boundary": {
                "openrouter_only": True,
                "codex_runtime_used": False,
                "final_review_real_call_executed": False,
                "brief_synthesis_real_call_executed": False,
                "email_sent": False,
                "webhook_sent": False,
                "paywall_bypassed": False,
            },
            "artifact_paths": {
                "fulltext_prompt_audit": str(run_dir / "fulltext_prompt_audit.json") if prompt_audit else None,
                "redacted_canary": str(run_dir / "redacted_canary.json"),
                "model_full_text_limited_analysis": str(run_dir / "model_full_text_limited_analysis.json") if normalized_model_analysis else None,
                "full_paper_analysis_path": str(run_dir / "model_full_text_limited_analysis.json") if normalized_model_analysis else None,
                "parse_failure_path": str(run_dir / "model_analysis_parse_failure.json") if real_call and not normalized_model_analysis else None,
                "deterministic_full_paper_analysis": str(run_dir / "full_paper_analysis.json") if analysis else None,
            },
        }
        validate_json(analysis_run, "full_paper_analysis_run")
        _write_json(run_dir / "full_paper_analysis_run.json", analysis_run)
    if (not one_shot_fulltext) and real_call and candidate and analysis and model_check.get("available") is True:
        payload = {
            "source_id": analysis["source_id"],
            "title": analysis.get("title"),
            "candidate_id": candidate.get("candidate_id"),
            "fulltext_artifact_id": artifact.get("artifact_id"),
            "extracted_text_sha256": artifact.get("extracted_text_sha256"),
            "extracted_char_count": artifact.get("extracted_char_count"),
            "section_hints": artifact.get("section_hints"),
            "analysis_scope": analysis.get("analysis_scope"),
        }
        canary = execute_openrouter_canary(
            "literature_analysis",
            payload,
            internal_model_id,
            environment=environment,
            spent_usd=spent_usd,
            triage_result={"source_tier": "A", "deep_read_priority": "High"},
            source_id=analysis["source_id"],
            real_call=True,
            allow_network=allow_network,
            confirm_charge=confirm_charge,
            max_cost_usd=max_cost_usd,
            write_ledger=write_ledger,
            ledger_path=ledger_path,
        )
        _write_json(run_dir / "redacted_canary.json", canary)
    elif not one_shot_fulltext:
        if real_call and model_check.get("available") is not True:
            status = "failed_closed_unavailable_model"
        _write_json(run_dir / "redacted_canary.json", _redacted_canary_summary(canary))

    manifest = {
        "run_id": "fullpaper-" + hashlib.sha256(created_at.encode("utf-8")).hexdigest()[:16],
        "created_at": created_at,
        "status": status,
        "analysis_label": "full_text_limited_analysis",
        "query_profile": query_profile,
        "providers": providers or [],
        "model_availability": model_check,
        "selected_candidate": {"candidate_id": candidate.get("candidate_id"), "title": candidate.get("title"), "source_provider": candidate.get("source_provider")} if candidate else None,
        "real_call_requested": bool(real_call),
        "real_call_executed": bool(canary and canary.get("real_call_executed")),
        "artifacts": {
            "output_dir": str(run_dir),
            "discovery_run": str(run_dir / "discovery_run.json"),
            "fulltext_eligibility": str(run_dir / "fulltext_eligibility.json"),
            "fulltext_artifact": str(run_dir / "fulltext" / "fulltext_artifact.json"),
            "full_paper_analysis": str(run_dir / "full_paper_analysis.json") if analysis else None,
            "constraint_critic": str(run_dir / "constraint_critic.json") if critic else None,
            "redacted_canary": str(run_dir / "redacted_canary.json"),
            "redacted_ledger": str(ledger_path),
            "manifest": str(run_dir / "manifest.json"),
        },
        "runtime_boundary": {
            "openrouter_only": True,
            "codex_runtime_used": False,
            "paywall_bypassed": False,
            "credentials_used": False,
            "email_sent": False,
            "webhook_sent": False,
            "final_review_real_call_executed": False,
            "brief_synthesis_real_call_executed": False,
            "fulltext_logged_to_ledger": False,
            "model_response_content_logged": False,
        },
        "limitations": [] if analysis else ["no eligible open-access A/B + High candidate was available or extraction did not complete"],
        "provider_errors": discovery.get("provider_errors") or [],
    }
    _write_json(run_dir / "manifest.json", manifest)
    return manifest


def run_three_paper_fulltext_canary(
    query_profile: str = "datacenter_networking",
    providers: list[str] | None = None,
    max_candidates: int = 30,
    max_papers: int = 3,
    internal_model_id_analysis: str = DEFAULT_MODEL,
    internal_model_id_critic: str = DEFAULT_MODEL,
    internal_model_id_cross_validation: str = DEFAULT_MODEL,
    environment: str = "quality_first",
    spent_usd: float = 0,
    max_cost_usd: float = 20,
    real_call: bool = False,
    allow_network: bool = False,
    confirm_charge: bool = False,
    output_dir: str | Path | None = None,
    arxiv_id: str | None = None,
) -> Dict[str, Any]:
    for model_id in (internal_model_id_analysis, internal_model_id_critic, internal_model_id_cross_validation):
        validate_openrouter_model_id(model_id)
    created_at = _now()
    run_dir = Path(output_dir) if output_dir else _default_three_dir(created_at)
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = run_dir / "redacted_ledger.jsonl"
    analysis_model_check = _model_availability(internal_model_id_analysis, allow_network, real_call)
    cross_model_check = _model_availability(internal_model_id_cross_validation, allow_network, real_call)

    discovery = _discover(query_profile, providers, max_candidates, arxiv_id=arxiv_id)
    _write_json(run_dir / "discovery_run.json", discovery)
    policy = load_fulltext_policy()
    selected = select_fulltext_candidates(discovery.get("candidates") or [], max_papers, policy)
    items = []
    canaries = []
    for index, item in enumerate(selected[:max_papers], start=1):
        paper_dir = run_dir / "papers" / f"paper_{index}"
        candidate = item["candidate"]
        eligibility = item["eligibility"]
        _write_json(paper_dir / "fulltext_eligibility.json", eligibility)
        artifact = fetch_and_extract_fulltext(candidate, eligibility, paper_dir / "fulltext", allow_network=allow_network, dry_run=not real_call, policy=policy)
        analysis = _deterministic_analysis(candidate, artifact)
        critic = None
        if analysis:
            _write_json(paper_dir / "full_paper_analysis.json", analysis)
            critic = critique_analysis(analysis)
            validate_json(critic, "constraint_critic")
            _write_json(paper_dir / "constraint_critic.json", critic)
        if real_call and analysis and analysis_model_check.get("available") is True:
            canary = execute_openrouter_canary(
                "literature_analysis",
                {"source_id": analysis["source_id"], "candidate_id": candidate.get("candidate_id"), "title": analysis.get("title"), "extracted_text_sha256": artifact.get("extracted_text_sha256"), "analysis_scope": analysis.get("analysis_scope")},
                internal_model_id_analysis,
                environment=environment,
                spent_usd=spent_usd,
                triage_result={"source_tier": "A", "deep_read_priority": "High"},
                source_id=analysis["source_id"],
                real_call=True,
                allow_network=allow_network,
                confirm_charge=confirm_charge,
                max_cost_usd=max_cost_usd,
                write_ledger=True,
                ledger_path=ledger_path,
            )
            canaries.append(canary)
            _write_json(paper_dir / "redacted_canary.json", canary)
        items.append({"candidate_id": candidate.get("candidate_id"), "title": candidate.get("title"), "candidate": candidate, "fulltext_artifact": artifact, "analysis": analysis or {}, "critic": critic or {}})

    cross_canary = None
    if real_call and items and cross_model_check.get("available") is True and len(canaries) <= 3:
        cross_payload = {
            "source_id": "three-paper-cross-validation",
            "title": "three-paper cross-validation",
            "paper_count": len(items),
            "analysis_ids": [(item.get("analysis") or {}).get("analysis_id") for item in items],
            "candidate_ids": [item.get("candidate_id") for item in items],
        }
        cross_canary = execute_openrouter_canary(
            "cross_validation",
            cross_payload,
            internal_model_id_cross_validation,
            environment=environment,
            spent_usd=spent_usd,
            triage_result={"source_tier": "A", "deep_read_priority": "High"},
            source_id="three-paper-cross-validation",
            real_call=True,
            allow_network=allow_network,
            confirm_charge=confirm_charge,
            max_cost_usd=max_cost_usd,
            write_ledger=True,
            ledger_path=ledger_path,
        )
        _write_json(run_dir / "redacted_cross_validation_canary.json", cross_canary)

    report = build_cross_validation_report(items, cross_canary)
    report_paths = write_cross_validation_artifacts(report, run_dir)
    manifest = {
        "run_id": "threepaper-" + hashlib.sha256(created_at.encode("utf-8")).hexdigest()[:16],
        "created_at": created_at,
        "status": "completed_with_limitations" if len(items) < 3 else "completed",
        "query_profile": query_profile,
        "providers": providers or [],
        "selected_paper_count": len(items),
        "selected_papers": [{"candidate_id": item.get("candidate_id"), "title": item.get("title"), "extraction_quality": (item.get("fulltext_artifact") or {}).get("extraction_quality")} for item in items],
        "analysis_model_availability": analysis_model_check,
        "cross_validation_model_availability": cross_model_check,
        "real_call_requested": bool(real_call),
        "literature_analysis_real_call_count": sum(1 for c in canaries if c.get("real_call_executed")),
        "cross_validation_real_call_executed": bool(cross_canary and cross_canary.get("real_call_executed")),
        "artifacts": {
            "output_dir": str(run_dir),
            "discovery_run": str(run_dir / "discovery_run.json"),
            "papers_dir": str(run_dir / "papers"),
            "cross_validation_report_json": report_paths["json_path"],
            "cross_validation_report_md": report_paths["markdown_path"],
            "redacted_ledger": str(ledger_path),
            "manifest": str(run_dir / "manifest.json"),
        },
        "runtime_boundary": {
            "openrouter_only": True,
            "codex_runtime_used": False,
            "paywall_bypassed": False,
            "credentials_used": False,
            "email_sent": False,
            "webhook_sent": False,
            "final_review_real_call_executed": False,
            "brief_synthesis_real_call_executed": False,
            "fulltext_logged_to_ledger": False,
            "model_response_content_logged": False,
        },
        "provider_errors": discovery.get("provider_errors") or [],
        "limitations": report.get("limitations") or [],
    }
    _write_json(run_dir / "manifest.json", manifest)
    return manifest
