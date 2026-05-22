from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


DEFAULT_LEDGER_PATH = Path(".zyw_insight/budget_ledger.jsonl")
FORBIDDEN_EVENT_KEYS = {
    "body",
    "content",
    "raw_body",
    "messages",
    "api_key",
    "token",
    "secret",
    "authorization",
    "env",
    "headers",
    "reasoning",
    "reasoning_details",
    "selected_text",
}


def _sanitize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    clean = {key: value for key, value in event.items() if key.lower() not in FORBIDDEN_EVENT_KEYS}
    clean.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    clean.setdefault("dry_run", True)
    return clean


def append_budget_event(event: Dict[str, Any], path: str | Path = DEFAULT_LEDGER_PATH) -> Dict[str, Any]:
    clean = _sanitize_event(event)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        f.write(json.dumps(clean, ensure_ascii=False, sort_keys=True) + "\n")
    return clean


def append_adapter_run_event(adapter_run: Dict[str, Any], path: str | Path = DEFAULT_LEDGER_PATH) -> Dict[str, Any]:
    request = adapter_run.get("request") or {}
    response = adapter_run.get("response") or {}
    routing = request.get("routing_decision") or {}
    event = {
        "timestamp": adapter_run.get("created_at"),
        "dry_run": True,
        "stage": adapter_run.get("stage"),
        "source_id": adapter_run.get("source_id"),
        "model_id": request.get("model_id"),
        "budget_environment": request.get("budget_environment"),
        "quality_priority": request.get("quality_priority"),
        "estimated_input_tokens": request.get("estimated_input_tokens"),
        "estimated_output_tokens": request.get("estimated_output_tokens"),
        "estimated_cost_usd": request.get("estimated_cost_usd"),
        "budget_status": response.get("budget_status"),
        "processing_allowed": response.get("processing_allowed"),
        "manual_required": bool(request.get("manual_required") or response.get("manual_required")),
        "quality_preserved": routing.get("quality_preserved"),
        "request_id": request.get("request_id"),
        "response_id": response.get("response_id"),
    }
    return append_budget_event(event, path)


def append_canary_event(canary_run: Dict[str, Any], path: str | Path = DEFAULT_LEDGER_PATH) -> Dict[str, Any]:
    request = canary_run.get("request") or {}
    response = canary_run.get("response") or {}
    usage = canary_run.get("usage") or {}
    cost = canary_run.get("cost") or {}
    event = {
        "timestamp": canary_run.get("created_at"),
        "dry_run": canary_run.get("dry_run"),
        "real_call_executed": canary_run.get("real_call_executed"),
        "stage": canary_run.get("stage"),
        "model_id": canary_run.get("internal_model_id"),
        "api_model_slug": canary_run.get("api_model_slug"),
        "source_id": request.get("source_id") or canary_run.get("source_id"),
        "estimated_input_tokens": usage.get("estimated_input_tokens"),
        "estimated_output_tokens": usage.get("estimated_output_tokens"),
        "actual_input_tokens": usage.get("actual_input_tokens"),
        "actual_output_tokens": usage.get("actual_output_tokens"),
        "estimated_cost_usd": cost.get("estimated_cost_usd"),
        "actual_cost_usd": cost.get("actual_cost_usd"),
        "max_cost_usd": cost.get("max_cost_usd"),
        "budget_status": request.get("budget_status") or response.get("budget_status"),
        "manual_required": bool(request.get("manual_required") or response.get("manual_required")),
        "request_id": request.get("request_id"),
        "response_id": response.get("response_id"),
        "error_status": (response.get("error") or {}).get("status") if isinstance(response.get("error"), dict) else None,
    }
    return append_budget_event(event, path)


def append_pipeline_canary_event(canary: Dict[str, Any], path: str | Path = DEFAULT_LEDGER_PATH) -> Dict[str, Any]:
    budget = canary.get("budget") or {}
    artifacts = canary.get("real_stage_canaries") or []
    request_ids = []
    response_ids = []
    model_id = None
    api_model_slug = None
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        model_id = model_id or item.get("internal_model_id")
        api_model_slug = api_model_slug or item.get("api_model_slug")
        validation = item.get("validation") or {}
        request_id = validation.get("request_id")
        response_id = validation.get("response_id")
        if request_id:
            request_ids.append(request_id)
        if response_id:
            response_ids.append(response_id)
    event = {
        "timestamp": canary.get("created_at"),
        "pipeline_canary_id": canary.get("pipeline_canary_id"),
        "dry_run": canary.get("dry_run"),
        "real_call_executed": canary.get("real_call_executed"),
        "selected_document_count": len((canary.get("input") or {}).get("selected_documents") or []),
        "real_stage_count": len(artifacts),
        "model_id": model_id,
        "api_model_slug": api_model_slug,
        "max_cost_usd": budget.get("max_cost_usd"),
        "estimated_cost_usd": budget.get("estimated_cost_usd"),
        "actual_cost_usd": budget.get("actual_cost_usd"),
        "audit_cost_usd": budget.get("audit_cost_usd"),
        "budget_status": budget.get("budget_status"),
        "request_ids": request_ids,
        "response_ids": response_ids,
        "validation_status": (canary.get("validation") or {}).get("schema_valid"),
    }
    return append_budget_event(event, path)


def load_budget_events(path: str | Path = DEFAULT_LEDGER_PATH) -> List[Dict[str, Any]]:
    ledger = Path(path)
    if not ledger.exists():
        return []
    events = []
    with ledger.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def summarize_budget_events(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    event_list = list(events)
    total = sum(float(event.get("estimated_cost_usd", 0) or 0) for event in event_list)
    by_stage: Dict[str, float] = {}
    count_by_stage: Dict[str, int] = {}
    count_by_budget_status: Dict[str, int] = {}
    count_denied = 0
    count_manual_required = 0
    for event in event_list:
        stage = str(event.get("stage", "unknown"))
        by_stage[stage] = by_stage.get(stage, 0.0) + float(event.get("estimated_cost_usd", 0) or 0)
        count_by_stage[stage] = count_by_stage.get(stage, 0) + 1
        status = str(event.get("budget_status", "unknown"))
        count_by_budget_status[status] = count_by_budget_status.get(status, 0) + 1
        if event.get("processing_allowed") is False:
            count_denied += 1
        if event.get("manual_required") is True:
            count_manual_required += 1
    return {
        "event_count": len(event_list),
        "estimated_cost_usd": round(total, 4),
        "total_estimated_cost_usd": round(total, 4),
        "by_stage": {key: round(value, 4) for key, value in sorted(by_stage.items())},
        "count_by_stage": dict(sorted(count_by_stage.items())),
        "count_by_budget_status": dict(sorted(count_by_budget_status.items())),
        "count_denied": count_denied,
        "count_manual_required": count_manual_required,
        "dry_run_only": all(event.get("dry_run") is True for event in event_list),
        "body_recorded": any(any(key.lower() in FORBIDDEN_EVENT_KEYS for key in event) for event in event_list),
    }
