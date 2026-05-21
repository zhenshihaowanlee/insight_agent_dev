from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .analyzer import analyze_source
from .brief import synthesize_brief
from .budget import get_budget_status, load_budget_policy, should_reduce_volume
from .critic import critique_analysis
from .draft_renderer import render_brief_markdown
from .ingestion import SUPPORTED_TEXT_EXTENSIONS, ingest_file
from .openrouter_adapter import run_adapter_dry_run
from .schema_validation import validate_json
from .triage import triage_source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id(created_at: str) -> str:
    return "pipe-" + hashlib.sha256(created_at.encode("utf-8")).hexdigest()[:16]


def _default_output_dir(created_at: str) -> Path:
    safe = created_at.replace(":", "").replace("+", "Z")
    return Path(".zyw_insight") / "runs" / f"{safe}-72h-dry-run"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _candidate_paths(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS)


def _priority_key(item: Dict[str, Any]) -> tuple[int, int, str]:
    triage = item["triage"]
    priority_score = {"High": 0, "Medium": 1, "Low": 2}.get(triage.get("deep_read_priority"), 2)
    tier_score = {"A": 0, "B": 1, "C": 2, "D": 3}.get(triage.get("source_tier"), 3)
    return (priority_score, tier_score, str(item["path"]))


def _artifact_path(path: Path) -> str:
    return str(path)


def run_72h_dry_run_pipeline(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    environment: str = "quality_first",
    spent_usd: float = 0,
    window_hours: int = 72,
    max_documents: int | None = None,
    write_ledger: bool = True,
    trigger: str = "manual",
) -> Dict[str, Any]:
    if trigger not in {"manual", "openclaw_cron_dry_run"}:
        raise ValueError(f"unsupported trigger: {trigger}")
    source_dir = Path(input_dir)
    if not source_dir.is_dir():
        raise NotADirectoryError(source_dir)

    created_at = _now()
    run_id = _run_id(created_at)
    run_dir = Path(output_dir) if output_dir else _default_output_dir(created_at)
    analyses_dir = run_dir / "analyses"
    critics_dir = run_dir / "critics"
    brief_dir = run_dir / "brief"
    adapters_dir = run_dir / "adapter_runs"
    ledger_path = run_dir / "redacted_ledger.jsonl"
    manifest_path = run_dir / "run_manifest.json"

    policy = load_budget_policy(environment)
    budget_status = get_budget_status(spent_usd, policy)
    limit = max_documents if max_documents is not None else int(policy["daily_document_limit"])
    if should_reduce_volume(spent_usd, policy):
        limit = min(limit, int(policy["daily_document_limit"]))

    pretriaged: list[Dict[str, Any]] = []
    skipped: list[Dict[str, Any]] = []
    for path in _candidate_paths(source_dir):
        source = ingest_file(path)
        triage = triage_source(source)
        pretriaged.append({"path": path, "source": source, "triage": triage})

    pretriaged.sort(key=_priority_key)
    selected = pretriaged[:limit]
    for item in pretriaged[limit:]:
        skipped.append(
            {
                "path": str(item["path"]),
                "source_id": item["source"]["source_id"],
                "source_tier": item["triage"]["source_tier"],
                "deep_read_priority": item["triage"]["deep_read_priority"],
                "reason": "skipped by document limit or budget volume reduction",
            }
        )

    analyses: list[Dict[str, Any]] = []
    critics: list[Dict[str, Any]] = []
    combined_items: list[Dict[str, Any]] = []
    analysis_paths: list[str] = []
    critic_paths: list[str] = []

    for item in selected:
        source = item["source"]
        triage = item["triage"]
        analysis = analyze_source(source, triage)
        validate_json(analysis, "literature_analysis")
        critic = critique_analysis(analysis)
        validate_json(critic, "constraint_critic")

        stem = source["source_id"].replace("/", "_")
        analysis_path = analyses_dir / f"{stem}.analysis.json"
        critic_path = critics_dir / f"{stem}.critic.json"
        _write_json(analysis_path, analysis)
        _write_json(critic_path, critic)
        analyses.append(analysis)
        critics.append(critic)
        combined_items.append({"analysis": analysis, "critic": critic})
        analysis_paths.append(_artifact_path(analysis_path))
        critic_paths.append(_artifact_path(critic_path))

    brief = synthesize_brief(combined_items, window_hours=window_hours, budget_mode=environment, quality_priority="high")
    validate_json(brief, "brief")
    brief_json_path = brief_dir / "brief.json"
    _write_json(brief_json_path, brief)

    adapter_run = run_adapter_dry_run(
        "brief_synthesis",
        brief,
        environment=environment,
        spent_usd=spent_usd,
        triage_result={"source_tier": "A", "deep_read_priority": "High"},
        source_id=brief["brief_id"],
        write_ledger=False,
    )
    validate_json(adapter_run, "adapter_run")
    adapter_path = adapters_dir / "brief_synthesis.adapter_run.json"
    _write_json(adapter_path, adapter_run)
    if write_ledger:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_event = {
            "timestamp": adapter_run["created_at"],
            "dry_run": True,
            "stage": adapter_run["stage"],
            "source_id": adapter_run["source_id"],
            "model_id": adapter_run["request"]["model_id"],
            "budget_mode": environment,
            "quality_priority": "high",
            "estimated_cost_usd": adapter_run["request"]["estimated_cost_usd"],
            "budget_status": adapter_run["response"]["budget_status"],
            "processing_allowed": adapter_run["response"]["processing_allowed"],
            "manual_required": adapter_run["response"]["manual_required"],
            "quality_preserved": adapter_run["response"]["metadata"]["quality_preserved"],
            "request_id": adapter_run["request"]["request_id"],
            "response_id": adapter_run["response"]["response_id"],
        }
        ledger_path.write_text(json.dumps(ledger_event, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    pipeline_run: Dict[str, Any] = {
        "run_id": run_id,
        "created_at": created_at,
        "dry_run": True,
        "trigger": trigger,
        "input": {
            "input_dir": str(source_dir),
            "document_count": len(pretriaged),
            "processed_document_count": len(selected),
            "max_documents": limit,
            "skipped_documents": skipped,
        },
        "environment": environment,
        "quality_priority": "high",
        "budget_context": {
            "spent_usd": spent_usd,
            "budget_status": budget_status,
            "policy_id": policy["policy_id"],
            "volume_reduction_recommended": should_reduce_volume(spent_usd, policy),
        },
        "stages": {
            "ingestion": {"status": "completed", "count": len(selected)},
            "triage": {"status": "completed", "count": len(selected)},
            "analysis": {"status": "completed", "count": len(analyses)},
            "critique": {"status": "completed", "count": len(critics)},
            "brief": {"status": "completed", "count": 1},
            "adapter_dry_run": {"status": "completed", "count": 1},
        },
        "artifacts": {
            "output_dir": _artifact_path(run_dir),
            "analyses": analysis_paths,
            "critics": critic_paths,
            "brief_json": _artifact_path(brief_json_path),
            "brief_markdown": _artifact_path(brief_dir / "brief.md"),
            "adapter_runs": [_artifact_path(adapter_path)],
            "ledger_path": _artifact_path(ledger_path),
            "manifest_path": _artifact_path(manifest_path),
        },
        "draft_delivery": {
            "mode": "draft_only",
            "requires_human_approval": True,
            "external_delivery_sent": False,
        },
        "runtime_boundary": {
            "openrouter_only": True,
            "codex_runtime_used": False,
            "real_openrouter_call_executed": False,
            "canary_real_call_executed": False,
            "network_request_sent": False,
            "api_key_read": False,
            "email_sent": False,
            "webhook_sent": False,
        },
        "guardrail_results": [
            {"rule_id": "draft_only", "status": "pass"},
            {"rule_id": "adapter_dry_run_only", "status": "pass"},
            {"rule_id": "redacted_ledger", "status": "pass" if write_ledger else "not_written"},
            {"rule_id": "volume_reduction", "status": "applied" if skipped else "not_needed"},
        ],
        "validation": {
            "brief_schema_valid": True,
            "adapter_run_schema_valid": True,
            "pipeline_run_schema_valid": True,
        },
        "notes": [
            "Local 72h pipeline dry-run only; no model call, canary execution, network request, or external delivery occurred.",
            "Source bodies were processed as untrusted content and were not written to ledger or manifest.",
        ],
    }

    brief_markdown = render_brief_markdown(brief, pipeline_run)
    brief_md_path = brief_dir / "brief.md"
    brief_md_path.parent.mkdir(parents=True, exist_ok=True)
    brief_md_path.write_text(brief_markdown, encoding="utf-8")

    validate_json(pipeline_run, "pipeline_run")
    _write_json(manifest_path, pipeline_run)
    return pipeline_run
