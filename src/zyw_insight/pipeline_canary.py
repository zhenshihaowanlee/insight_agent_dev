from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .budget import get_budget_status, load_budget_policy, resolve_audit_cost
from .budget_ledger import append_pipeline_canary_event
from .ingestion import SUPPORTED_TEXT_EXTENSIONS, ingest_file
from .openrouter_canary import execute_openrouter_canary
from .pipeline import run_72h_dry_run_pipeline
from .schema_validation import validate_json
from .triage import triage_source


DEFAULT_ALLOWED_REAL_STAGES = ["literature_analysis"]
NEVER_REAL_STAGES = {"final_review", "brief_synthesis"}
DEFAULT_INTERNAL_MODEL_ID = "openrouter/example/model-slug"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ts(value: str) -> str:
    return value.replace(":", "").replace("+", "Z")


def _default_output_dir(created_at: str) -> Path:
    return Path(".zyw_insight") / "pipeline_canaries" / f"{_safe_ts(created_at)}-pipeline-canary"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _candidate_paths(input_path: Path) -> list[Path]:
    if input_path.is_file() and input_path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS:
        return [input_path]
    if input_path.is_dir():
        return sorted(path for path in input_path.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS)
    raise ValueError(f"unsupported pipeline canary input: {input_path}")


def _priority_key(item: Dict[str, Any]) -> tuple[int, int, str]:
    triage = item["triage"]
    priority_score = {"High": 0, "Medium": 1, "Low": 2}.get(triage.get("deep_read_priority"), 2)
    tier_score = {"A": 0, "B": 1, "C": 2, "D": 3}.get(triage.get("source_tier"), 3)
    return (priority_score, tier_score, str(item["path"]))


def _document_summary(path: Path, source: Dict[str, Any], triage: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": str(path),
        "source_id": source["source_id"],
        "title": source["title"],
        "source_type": source["source_type"],
        "source_tier": triage["source_tier"],
        "deep_read_priority": triage["deep_read_priority"],
        "content_hash": source["content_hash"],
        "body_is_untrusted": bool(source.get("body_is_untrusted")),
    }


def select_canary_documents(input_dir_or_file: str | Path, max_documents: int = 1) -> list[Dict[str, Any]]:
    if max_documents < 1:
        raise ValueError("max_documents must be >= 1")
    candidates = []
    for path in _candidate_paths(Path(input_dir_or_file)):
        source = ingest_file(path)
        triage = triage_source(source)
        candidates.append({"path": path, "source": source, "triage": triage, "summary": _document_summary(path, source, triage)})
    candidates.sort(key=_priority_key)
    return candidates[:max_documents]


def _normalize_allowed_stages(allowed_real_stages: list[str] | None) -> list[str]:
    stages = allowed_real_stages or list(DEFAULT_ALLOWED_REAL_STAGES)
    normalized = []
    for stage in stages:
        if stage in NEVER_REAL_STAGES:
            raise ValueError(f"{stage} is not allowed for real pipeline canary")
        if stage != "literature_analysis":
            raise ValueError(f"{stage} real pipeline canary is not enabled in this release")
        if stage not in normalized:
            normalized.append(stage)
    return normalized or list(DEFAULT_ALLOWED_REAL_STAGES)


def build_stage_canary_plan(selected_documents: list[Dict[str, Any]], allowed_real_stages: list[str] | None = None) -> list[Dict[str, Any]]:
    stages = _normalize_allowed_stages(allowed_real_stages)
    plan = []
    for doc in selected_documents:
        for stage in stages:
            plan.append(
                {
                    "stage": stage,
                    "source_id": doc["source"]["source_id"],
                    "title": doc["source"]["title"],
                    "triage": {
                        "source_tier": doc["triage"]["source_tier"],
                        "deep_read_priority": doc["triage"]["deep_read_priority"],
                    },
                    "payload": {"source": doc["source"], "triage": doc["triage"]},
                }
            )
    return plan


def _redacted_canary_summary(canary_run: Dict[str, Any], path: Path) -> Dict[str, Any]:
    return {
        "stage": canary_run["stage"],
        "source_id": canary_run["request"]["source_id"],
        "internal_model_id": canary_run["internal_model_id"],
        "api_model_slug": canary_run["api_model_slug"],
        "canary_run_id": canary_run["canary_run_id"],
        "real_call_executed": bool(canary_run["real_call_executed"]),
        "redacted_response_path": str(path),
        "ledger_event_id": canary_run["ledger_event"].get("request_id"),
        "usage": canary_run["usage"],
        "cost": canary_run["cost"],
        "validation": {
            "schema_valid": canary_run["validation"].get("schema_valid"),
            "request_id": canary_run["request"]["request_id"],
            "response_id": canary_run["response"].get("response_id"),
            "status": canary_run["response"].get("status"),
        },
    }


def run_stage_canary_or_dry_run(
    plan_item: Dict[str, Any],
    internal_model_id: str,
    environment: str,
    spent_usd: float,
    real_call: bool,
    allow_network: bool,
    confirm_charge: bool,
    max_cost_usd: float | None,
    manual_override: bool,
) -> Dict[str, Any]:
    if plan_item["stage"] in NEVER_REAL_STAGES:
        raise ValueError(f"{plan_item['stage']} is not allowed for real pipeline canary")
    return execute_openrouter_canary(
        plan_item["stage"],
        plan_item["payload"],
        internal_model_id=internal_model_id,
        environment=environment,
        spent_usd=spent_usd,
        triage_result=plan_item["triage"],
        source_id=plan_item["source_id"],
        real_call=real_call,
        allow_network=allow_network,
        confirm_charge=confirm_charge,
        max_cost_usd=max_cost_usd,
        manual_override=manual_override,
        write_ledger=False,
    )


def _prepare_deterministic_input(input_dir_or_file: Path, run_dir: Path) -> Path:
    if input_dir_or_file.is_dir():
        return input_dir_or_file
    selected_dir = run_dir / "selected_inputs"
    selected_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_dir_or_file, selected_dir / input_dir_or_file.name)
    return selected_dir


def write_pipeline_canary_artifacts(canary: Dict[str, Any], output_dir: str | Path | None = None) -> Dict[str, Any]:
    run_dir = Path(output_dir or canary["artifacts"]["output_dir"])
    manifest_path = run_dir / "pipeline_canary_manifest.json"
    _write_json(manifest_path, redact_pipeline_canary_for_manifest(canary))
    canary["artifacts"]["pipeline_canary_manifest"] = str(manifest_path)
    validate_json(canary, "pipeline_canary")
    return canary


def redact_pipeline_canary_for_manifest(canary: Dict[str, Any]) -> Dict[str, Any]:
    # The object is already redacted by construction; keep a copy boundary for future tightening.
    return json.loads(json.dumps(canary, ensure_ascii=False, sort_keys=True, default=str))


def run_small_pipeline_canary(
    input_dir_or_file: str | Path,
    environment: str = "quality_first",
    spent_usd: float = 0,
    internal_model_id: str | None = None,
    real_call: bool = False,
    allow_network: bool = False,
    confirm_charge: bool = False,
    max_cost_usd: float = 5.0,
    max_documents: int = 1,
    allowed_real_stages: list[str] | None = None,
    write_ledger: bool = True,
    ledger_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    manual_override: bool = False,
) -> Dict[str, Any]:
    if max_documents > 2 and not manual_override:
        raise ValueError("max_documents > 2 requires manual_override")
    selected_limit = min(max_documents, 2 if not manual_override else max_documents)
    stages = _normalize_allowed_stages(allowed_real_stages)
    if real_call and len(stages) * selected_limit > 1 and not manual_override:
        raise ValueError("real pipeline canary allows at most one real call unless manual_override=true")

    created_at = _now()
    canary_id = "pipe-canary-" + hashlib.sha256(created_at.encode("utf-8")).hexdigest()[:16]
    run_dir = Path(output_dir) if output_dir else _default_output_dir(created_at)
    run_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_dir_or_file)
    deterministic_input = _prepare_deterministic_input(input_path, run_dir)
    selected = select_canary_documents(deterministic_input, selected_limit)
    deterministic_run_dir = run_dir / "deterministic_run"
    deterministic = run_72h_dry_run_pipeline(
        deterministic_input,
        output_dir=deterministic_run_dir,
        environment=environment,
        spent_usd=spent_usd,
        max_documents=selected_limit,
        write_ledger=True,
        trigger="manual",
    )

    plan = build_stage_canary_plan(selected, stages)
    canary_runs_dir = run_dir / "redacted_stage_canaries"
    stage_summaries = []
    estimated_total = 0.0
    actual_total = 0.0
    audit_total = 0.0
    any_real = False
    for plan_item in plan:
        canary_run = run_stage_canary_or_dry_run(
            plan_item,
            internal_model_id or DEFAULT_INTERNAL_MODEL_ID,
            environment,
            spent_usd,
            real_call,
            allow_network,
            confirm_charge,
            max_cost_usd,
            manual_override,
        )
        validate_json(canary_run, "openrouter_canary")
        path = canary_runs_dir / f"{canary_run['canary_run_id']}.json"
        _write_json(path, canary_run)
        stage_summaries.append(_redacted_canary_summary(canary_run, path))
        estimated_total += float(canary_run["cost"].get("estimated_cost_usd") or 0)
        actual_total += float(canary_run["cost"].get("actual_cost_usd") or 0)
        audit_total += float(canary_run["cost"].get("audit_cost_usd") or 0)
        any_real = any_real or bool(canary_run["real_call_executed"])

    policy = load_budget_policy(environment)
    audit = resolve_audit_cost(actual_total if any_real else None, estimated_total)
    ledger = Path(ledger_path) if ledger_path else run_dir / "pipeline_canary_ledger.real.jsonl"
    canary: Dict[str, Any] = {
        "pipeline_canary_id": canary_id,
        "created_at": created_at,
        "dry_run": not any_real,
        "real_call_requested": bool(real_call),
        "real_call_executed": any_real,
        "manual_approval": {
            "real_call_flag": bool(real_call),
            "allow_network_flag": bool(allow_network),
            "confirm_charge_flag": bool(confirm_charge),
            "max_cost_usd": max_cost_usd,
            "max_documents": selected_limit,
            "allowed_real_stages": stages,
            "manual_override": bool(manual_override),
        },
        "input": {
            "input_dir_or_file": str(input_path),
            "selected_documents": [doc["summary"] for doc in selected],
            "skipped_documents": [],
            "max_documents": selected_limit,
        },
        "environment": environment,
        "quality_priority": policy["quality_priority"],
        "stages": {
            "deterministic_pipeline_run": "completed",
            "real_stage_canaries": "completed",
            "adapter_dry_runs": "completed",
            "brief_artifacts": "completed",
            "email_draft_allowed": False,
        },
        "real_stage_canaries": stage_summaries,
        "artifacts": {
            "output_dir": str(run_dir),
            "deterministic_run_manifest": deterministic["artifacts"]["manifest_path"],
            "deterministic_brief_json": deterministic["artifacts"]["brief_json"],
            "deterministic_brief_md": deterministic["artifacts"]["brief_markdown"],
            "redacted_canary_runs": [item["redacted_response_path"] for item in stage_summaries],
            "redacted_ledger_path": str(ledger),
            "pipeline_canary_manifest": str(run_dir / "pipeline_canary_manifest.json"),
        },
        "runtime_boundary": {
            "openrouter_only": True,
            "codex_runtime_used": False,
            "cron_triggered_real_call": False,
            "network_request_sent": any_real,
            "api_key_logged": False,
            "body_logged": False,
            "messages_logged": False,
            "reasoning_logged": False,
            "email_sent": False,
            "webhook_sent": False,
        },
        "budget": {
            "max_cost_usd": max_cost_usd,
            "estimated_cost_usd": round(estimated_total, 6),
            "actual_cost_usd": round(actual_total, 6) if any_real else None,
            "audit_cost_usd": round(float(audit["audit_cost_usd"] or audit_total or estimated_total), 6),
            "budget_status": get_budget_status(spent_usd, policy),
        },
        "validation": {
            "schema_valid": True,
            "deterministic_pipeline_schema_valid": True,
            "real_outputs_replace_deterministic_outputs": False,
        },
        "notes": [
            "Small pipeline canary keeps deterministic pipeline artifacts as the primary output.",
            "OpenRouter stage canary output is a redacted validation artifact only.",
            "Cron, email, brief_synthesis, and final_review real calls are not allowed.",
        ],
    }
    if write_ledger:
        canary["ledger_event"] = append_pipeline_canary_event(canary, ledger)
    validate_json(canary, "pipeline_canary")
    return write_pipeline_canary_artifacts(canary, run_dir)
