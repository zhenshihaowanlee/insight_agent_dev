from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .analyzer import analyze_source
from .brief import synthesize_brief
from .budget import (
    MODEL_PRICES,
    SCENARIOS,
    budget_mode,
    estimate_monthly_cost,
    estimate_scenario,
    get_budget_status,
    load_budget_policy,
)
from .critic import critique_analysis
from .discovery_pipeline import run_discovery_72h_dry_run
from .email_draft import build_email_draft
from .full_paper_canary import run_full_paper_canary, run_three_paper_fulltext_canary
from .full_paper_consistency_critic import review_full_paper_analysis
from .ingestion import ingest_file
from .model_router import choose_model_for_stage
from .openrouter_adapter import run_adapter_dry_run
from .openrouter_canary import execute_openrouter_canary
from .pipeline import run_72h_dry_run_pipeline
from .pipeline_canary import run_small_pipeline_canary
from .pre_send_review import run_pre_send_review
from .quality_gates import evaluate_analysis, gate_status
from .runtime_guard import check_runtime_config
from .schema_validation import validate_json
from .source_discovery import build_watchlist, discover_sources
from .triage import triage_path


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def cmd_budget(args: argparse.Namespace) -> int:
    rows = []
    if args.model:
        models = [args.model]
    else:
        models = list(MODEL_PRICES)
    for model in models:
        cost = estimate_scenario(model, args.scenario)
        rows.append({"model": model, "scenario": args.scenario, "estimated_usd": round(cost, 2)})
    print(json.dumps({"rows": rows, "mode_at_current_spend": budget_mode(args.current_spend)}, ensure_ascii=False, indent=2))
    return 0


def cmd_quality_check(args: argparse.Namespace) -> int:
    analysis = _load_json(Path(args.path))
    issues = evaluate_analysis(analysis)
    payload = {
        "gate_status": gate_status(issues),
        "issues": [issue.__dict__ for issue in issues],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if payload["gate_status"] == "block" else 0


def cmd_ingest(args: argparse.Namespace) -> int:
    payload = ingest_file(Path(args.path))
    print(json.dumps(payload, ensure_ascii=False, indent=2 if getattr(args, "pretty", False) else None))
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    payload = triage_path(Path(args.path))
    print(json.dumps(payload, ensure_ascii=False, indent=2 if getattr(args, "pretty", False) else None))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    source = ingest_file(Path(args.path))
    triage = triage_path(Path(args.path))
    analysis = analyze_source(source, triage)
    validate_json(analysis, "literature_analysis")

    if args.with_critic:
        critic = critique_analysis(analysis)
        validate_json(critic, "constraint_critic")
        payload: Dict[str, Any] = {"analysis": analysis, "critic": critic}
    else:
        payload = analysis

    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def _analysis_from_path(path: Path) -> Dict[str, Any]:
    if path.suffix.lower() == ".json":
        analysis = _load_json(path)
    else:
        source = ingest_file(path)
        triage = triage_path(path)
        analysis = analyze_source(source, triage)
    validate_json(analysis, "literature_analysis")
    return analysis


def cmd_critique(args: argparse.Namespace) -> int:
    analysis = _analysis_from_path(Path(args.path))
    critic = critique_analysis(analysis)
    validate_json(critic, "constraint_critic")
    payload: Dict[str, Any] = {"analysis": analysis, "critic": critic} if args.with_analysis else critic

    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_full_paper_review(args: argparse.Namespace) -> int:
    payload = review_full_paper_analysis(args.analysis_json, run_audit_path=args.run_audit, output_dir=args.output_dir)
    summary = {
        "canonical_analysis_path": payload["artifacts"]["canonical_full_paper_analysis_json"],
        "canonical_markdown_path": payload["artifacts"]["canonical_full_paper_analysis_md"],
        "consistency_report_json": payload["artifacts"]["consistency_report_json"],
        "consistency_report_md": payload["artifacts"]["consistency_report_md"],
        "ready_for_three_paper_cross_validation": payload["report"]["ready_for_three_paper_cross_validation"],
        "readiness_blockers": payload["report"]["readiness_blockers"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    input_path = Path(args.path_or_dir)
    paths = sorted(input_path.glob("*.json")) if input_path.is_dir() else [input_path]
    items = []
    for path in paths:
        try:
            items.append(_load_json(path))
        except json.JSONDecodeError:
            continue
    payload = synthesize_brief(items, window_hours=args.window_hours, budget_mode=args.budget_mode, quality_priority=args.quality_priority)
    validate_json(payload, "brief")
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_budget_policy(args: argparse.Namespace) -> int:
    payload = load_budget_policy(args.environment_or_path)
    validate_json(payload, "budget_policy")
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def cmd_budget_estimate(args: argparse.Namespace) -> int:
    policy = load_budget_policy(args.environment_or_path)
    payload = estimate_monthly_cost(args.scenario, policy)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def cmd_route_model(args: argparse.Namespace) -> int:
    policy = load_budget_policy(args.environment)
    triage_result = {
        "source_tier": args.source_tier,
        "deep_read_priority": args.deep_read_priority,
    }
    payload = choose_model_for_stage(args.stage, budget_tier=args.environment, spent_usd=args.spent_usd, policy=policy, triage_result=triage_result)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def cmd_budget_status(args: argparse.Namespace) -> int:
    policy = load_budget_policy(args.environment_or_path)
    payload = {
        "budget_status": get_budget_status(args.spent_usd, policy),
        "spent_usd": args.spent_usd,
        "soft_cap_usd": policy["soft_cap_usd"],
        "hard_cap_usd": policy["hard_cap_usd"],
        "environment": policy["environment"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def _adapter_payload_from_path(path: Path, stage: str) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    if path.is_dir():
        items = []
        for item_path in sorted(path.glob("*.json")):
            try:
                items.append(_load_json(item_path))
            except json.JSONDecodeError:
                continue
        return synthesize_brief(items, budget_mode="quality_first", quality_priority="high")
    if suffix == ".json":
        return _load_json(path)
    if suffix in {".md", ".markdown", ".txt"}:
        source = ingest_file(path)
        if stage == "triage":
            return source
        triage = triage_path(path)
        if stage == "literature_analysis":
            return {"source": source, "triage": triage}
        analysis = analyze_source(source, triage)
        validate_json(analysis, "literature_analysis")
        if stage == "constraint_critic":
            return analysis
        critic = critique_analysis(analysis)
        validate_json(critic, "constraint_critic")
        return {"analysis": analysis, "critic": critic}
    raise ValueError(f"unsupported adapter payload path: {path}")


def cmd_adapter_dry_run(args: argparse.Namespace) -> int:
    payload = _adapter_payload_from_path(Path(args.payload_path), args.stage)
    triage_result = {
        "source_tier": args.source_tier,
        "deep_read_priority": args.deep_read_priority,
    }
    adapter_run = run_adapter_dry_run(
        args.stage,
        payload,
        environment=args.environment,
        spent_usd=args.spent_usd,
        triage_result=triage_result,
        source_id=args.source_id,
        write_ledger=args.write_ledger,
        ledger_path=args.ledger_path,
        manual_override=args.manual_override,
    )
    validate_json(adapter_run, "adapter_run")
    text = json.dumps(adapter_run, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_openrouter_canary(args: argparse.Namespace) -> int:
    if args.real_call and not args.internal_model_id:
        raise SystemExit("--internal-model-id is required for --real-call")
    payload = _adapter_payload_from_path(Path(args.payload_path), args.stage)
    triage_result = {
        "source_tier": args.source_tier,
        "deep_read_priority": args.deep_read_priority,
    }
    internal_model_id = args.internal_model_id or "openrouter/example/model-slug"
    canary_run = execute_openrouter_canary(
        args.stage,
        payload,
        internal_model_id=internal_model_id,
        environment=args.environment,
        spent_usd=args.spent_usd,
        triage_result=triage_result,
        source_id=args.source_id,
        real_call=args.real_call,
        allow_network=args.allow_network,
        confirm_charge=args.confirm_openrouter_charge,
        max_cost_usd=args.max_cost_usd,
        manual_override=args.manual_override,
        write_ledger=args.write_ledger,
        ledger_path=args.ledger_path,
    )
    validate_json(canary_run, "openrouter_canary")
    text = json.dumps(canary_run, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_run_72h_dry_run(args: argparse.Namespace) -> int:
    payload = run_72h_dry_run_pipeline(
        args.input_dir,
        output_dir=args.output_dir,
        environment=args.environment,
        spent_usd=args.spent_usd,
        window_hours=args.window_hours,
        max_documents=args.max_documents,
        write_ledger=not args.no_ledger,
        trigger=args.trigger,
    )
    validate_json(payload, "pipeline_run")
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_pipeline_canary(args: argparse.Namespace) -> int:
    allowed_stages = args.allowed_real_stage or None
    payload = run_small_pipeline_canary(
        args.input_dir_or_file,
        environment=args.environment,
        spent_usd=args.spent_usd,
        internal_model_id=args.internal_model_id,
        real_call=args.real_call,
        allow_network=args.allow_network,
        confirm_charge=args.confirm_openrouter_charge,
        max_cost_usd=args.max_cost_usd,
        max_documents=args.max_documents,
        allowed_real_stages=allowed_stages,
        write_ledger=args.write_ledger,
        ledger_path=args.ledger_path,
        output_dir=args.output_dir,
        manual_override=args.manual_override,
    )
    validate_json(payload, "pipeline_canary")
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_full_paper_canary(args: argparse.Namespace) -> int:
    payload = run_full_paper_canary(
        query_profile=args.query_profile,
        providers=args.provider,
        max_candidates=args.max_candidates,
        internal_model_id=args.internal_model_id,
        environment=args.environment,
        spent_usd=args.spent_usd,
        max_cost_usd=args.max_cost_usd,
        real_call=args.real_call,
        allow_network=args.allow_network,
        confirm_charge=args.confirm_openrouter_charge,
        output_dir=args.output_dir,
        arxiv_id=args.arxiv_id,
        one_shot_fulltext=args.one_shot_fulltext,
        allow_fulltext_prompt=args.allow_fulltext_prompt,
        target_input_tokens=args.target_input_tokens,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_total_tokens=args.max_total_tokens,
        min_input_tokens_required=args.min_input_tokens_required,
        min_output_tokens_expected=args.min_output_tokens_expected,
        fail_if_input_under_min=args.fail_if_input_under_min,
        fail_if_total_exceeds_context=args.fail_if_total_exceeds_context,
        require_schema_valid_output=args.require_schema_valid_output,
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_three_paper_fulltext_canary(args: argparse.Namespace) -> int:
    payload = run_three_paper_fulltext_canary(
        query_profile=args.query_profile,
        providers=args.provider,
        max_candidates=args.max_candidates,
        max_papers=args.max_papers,
        internal_model_id_analysis=args.internal_model_id_analysis,
        internal_model_id_critic=args.internal_model_id_critic,
        internal_model_id_cross_validation=args.internal_model_id_cross_validation,
        environment=args.environment,
        spent_usd=args.spent_usd,
        max_cost_usd=args.max_cost_usd,
        real_call=args.real_call,
        allow_network=args.allow_network,
        confirm_charge=args.confirm_openrouter_charge,
        output_dir=args.output_dir,
        arxiv_id=args.arxiv_id,
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_email_draft(args: argparse.Namespace) -> int:
    payload = build_email_draft(
        args.run_dir_or_brief_path,
        output_dir=args.output_dir,
        to=args.to,
        cc=args.cc,
        bcc=args.bcc,
        subject=args.subject,
        allow_real_recipient=args.allow_real_recipient,
        include_attachments=not args.no_attachments,
    )
    validate_json(payload, "email_draft")
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_pre_send_review(args: argparse.Namespace) -> int:
    payload = run_pre_send_review(args.email_draft_dir_or_manifest, output_dir=args.output_dir)
    validate_json(payload, "pre_send_review")
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_discover_sources(args: argparse.Namespace) -> int:
    payload = discover_sources(
        query_profile=args.query_profile,
        providers=args.provider,
        max_candidates=args.max_candidates,
        dry_run=args.dry_run,
        network_enabled=not args.no_network,
        metadata_only=True,
        arxiv_id=args.arxiv_id,
    )
    validate_json(payload, "discovery_run")
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_discovery_triage(args: argparse.Namespace) -> int:
    payload = _load_json(Path(args.discovery_run_json))
    candidates = payload.get("candidates") or []
    watchlist = build_watchlist(candidates, payload.get("triage_preview") or [])
    selected = watchlist.get("selected_for_deep_read", [])[: args.max_selected]
    result = {
        "discovery_run_id": payload.get("discovery_run_id"),
        "watchlist": watchlist,
        "selected_for_deep_read": selected,
        "selected_for_deep_read_count": len(selected),
        "strong_conclusion_allowed": False,
        "notes": ["discovery triage is metadata-only and does not call models"],
    }
    text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_run_discovery_72h_dry_run(args: argparse.Namespace) -> int:
    payload = run_discovery_72h_dry_run(
        query_profile=args.query_profile,
        providers=args.provider,
        max_candidates=args.max_candidates,
        max_selected=args.max_selected,
        output_dir=args.output_dir,
        environment=args.environment,
        spent_usd=args.spent_usd,
        window_hours=args.window_hours,
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_runtime_guard(args: argparse.Namespace) -> int:
    result = check_runtime_config(Path(args.path))
    payload = {
        "ok": result.ok,
        "path": result.path,
        "failures": result.failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zyw-insight")
    sub = parser.add_subparsers(dest="command", required=True)

    p_budget = sub.add_parser("budget")
    p_budget.add_argument("--scenario", choices=sorted(SCENARIOS), default="baseline_efficient")
    p_budget.add_argument("--model", choices=sorted(MODEL_PRICES), default=None)
    p_budget.add_argument("--current-spend", type=float, default=0.0)
    p_budget.set_defaults(func=cmd_budget)

    p_quality = sub.add_parser("quality-check")
    p_quality.add_argument("path")
    p_quality.set_defaults(func=cmd_quality_check)

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("path")
    p_ingest.add_argument("--pretty", action="store_true")
    p_ingest.set_defaults(func=cmd_ingest)

    p_triage = sub.add_parser("triage")
    p_triage.add_argument("path")
    p_triage.add_argument("--pretty", action="store_true")
    p_triage.set_defaults(func=cmd_triage)

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("path")
    p_analyze.add_argument("--pretty", action="store_true")
    p_analyze.add_argument("--output")
    p_analyze.add_argument("--with-critic", action="store_true")
    p_analyze.set_defaults(func=cmd_analyze)

    p_critique = sub.add_parser("critique")
    p_critique.add_argument("path")
    p_critique.add_argument("--pretty", action="store_true")
    p_critique.add_argument("--output")
    p_critique.add_argument("--with-analysis", action="store_true")
    p_critique.set_defaults(func=cmd_critique)

    p_brief = sub.add_parser("brief")
    p_brief.add_argument("path_or_dir")
    p_brief.add_argument("--pretty", action="store_true")
    p_brief.add_argument("--output")
    p_brief.add_argument("--window-hours", type=int, default=72)
    p_brief.add_argument("--budget-mode", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_brief.add_argument("--quality-priority", choices=["high", "balanced", "cost_saving"], default="high")
    p_brief.set_defaults(func=cmd_brief)

    p_budget_policy = sub.add_parser("budget-policy")
    p_budget_policy.add_argument("environment_or_path")
    p_budget_policy.add_argument("--pretty", action="store_true")
    p_budget_policy.set_defaults(func=cmd_budget_policy)

    p_budget_estimate = sub.add_parser("budget-estimate")
    p_budget_estimate.add_argument("environment_or_path")
    p_budget_estimate.add_argument("--scenario", choices=sorted(SCENARIOS), default="baseline_efficient")
    p_budget_estimate.add_argument("--pretty", action="store_true")
    p_budget_estimate.set_defaults(func=cmd_budget_estimate)

    p_route = sub.add_parser("route-model")
    p_route.add_argument("stage")
    p_route.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_route.add_argument("--spent-usd", type=float, default=0.0)
    p_route.add_argument("--source-tier", choices=["A", "B", "C", "D"], default="B")
    p_route.add_argument("--deep-read-priority", choices=["High", "Medium", "Low"], default="Medium")
    p_route.add_argument("--pretty", action="store_true")
    p_route.set_defaults(func=cmd_route_model)

    p_budget_status = sub.add_parser("budget-status")
    p_budget_status.add_argument("environment_or_path")
    p_budget_status.add_argument("--spent-usd", type=float, required=True)
    p_budget_status.add_argument("--pretty", action="store_true")
    p_budget_status.set_defaults(func=cmd_budget_status)

    p_adapter = sub.add_parser("adapter-dry-run")
    p_adapter.add_argument("stage", choices=["triage", "literature_analysis", "constraint_critic", "brief_synthesis", "final_review"])
    p_adapter.add_argument("payload_path")
    p_adapter.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_adapter.add_argument("--spent-usd", type=float, default=0.0)
    p_adapter.add_argument("--source-tier", choices=["A", "B", "C", "D"], default="B")
    p_adapter.add_argument("--deep-read-priority", choices=["High", "Medium", "Low"], default="Medium")
    p_adapter.add_argument("--source-id")
    p_adapter.add_argument("--write-ledger", action="store_true")
    p_adapter.add_argument("--ledger-path")
    p_adapter.add_argument("--manual-override", action="store_true")
    p_adapter.add_argument("--pretty", action="store_true")
    p_adapter.add_argument("--output")
    p_adapter.set_defaults(func=cmd_adapter_dry_run)

    p_canary = sub.add_parser("openrouter-canary")
    p_canary.add_argument("stage", choices=["triage", "literature_analysis", "constraint_critic", "brief_synthesis", "final_review"])
    p_canary.add_argument("payload_path")
    p_canary.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_canary.add_argument("--spent-usd", type=float, default=0.0)
    p_canary.add_argument("--source-tier", choices=["A", "B", "C", "D"], default="B")
    p_canary.add_argument("--deep-read-priority", choices=["High", "Medium", "Low"], default="Medium")
    p_canary.add_argument("--source-id")
    p_canary.add_argument("--internal-model-id")
    p_canary.add_argument("--real-call", action="store_true")
    p_canary.add_argument("--allow-network", action="store_true")
    p_canary.add_argument("--confirm-openrouter-charge", action="store_true")
    p_canary.add_argument("--max-cost-usd", type=float)
    p_canary.add_argument("--manual-override", action="store_true")
    p_canary.add_argument("--write-ledger", action="store_true")
    p_canary.add_argument("--ledger-path")
    p_canary.add_argument("--pretty", action="store_true")
    p_canary.add_argument("--output")
    p_canary.set_defaults(func=cmd_openrouter_canary)

    p_pipeline = sub.add_parser("run-72h-dry-run")
    p_pipeline.add_argument("input_dir")
    p_pipeline.add_argument("--output-dir")
    p_pipeline.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_pipeline.add_argument("--spent-usd", type=float, default=0.0)
    p_pipeline.add_argument("--window-hours", type=int, default=72)
    p_pipeline.add_argument("--max-documents", type=int)
    p_pipeline.add_argument("--no-ledger", action="store_true")
    p_pipeline.add_argument("--trigger", choices=["manual", "openclaw_cron_dry_run"], default="manual")
    p_pipeline.add_argument("--pretty", action="store_true")
    p_pipeline.add_argument("--output")
    p_pipeline.set_defaults(func=cmd_run_72h_dry_run)

    p_pipeline_canary = sub.add_parser("pipeline-canary")
    p_pipeline_canary.add_argument("input_dir_or_file")
    p_pipeline_canary.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_pipeline_canary.add_argument("--spent-usd", type=float, default=0.0)
    p_pipeline_canary.add_argument("--internal-model-id", default="openrouter/example/model-slug")
    p_pipeline_canary.add_argument("--real-call", action="store_true")
    p_pipeline_canary.add_argument("--allow-network", action="store_true")
    p_pipeline_canary.add_argument("--confirm-openrouter-charge", action="store_true")
    p_pipeline_canary.add_argument("--max-cost-usd", type=float, default=5.0)
    p_pipeline_canary.add_argument("--max-documents", type=int, default=1)
    p_pipeline_canary.add_argument("--allowed-real-stage", action="append", choices=["literature_analysis"], default=None)
    p_pipeline_canary.add_argument("--manual-override", action="store_true")
    p_pipeline_canary.add_argument("--write-ledger", action="store_true")
    p_pipeline_canary.add_argument("--ledger-path")
    p_pipeline_canary.add_argument("--output-dir")
    p_pipeline_canary.add_argument("--pretty", action="store_true")
    p_pipeline_canary.add_argument("--output")
    p_pipeline_canary.set_defaults(func=cmd_pipeline_canary)

    p_full_paper = sub.add_parser("full-paper-canary")
    p_full_paper.add_argument("--query-profile", default="datacenter_networking")
    p_full_paper.add_argument("--provider", action="append", choices=["arxiv", "openalex", "crossref", "semantic_scholar", "ietf"])
    p_full_paper.add_argument("--arxiv-id")
    p_full_paper.add_argument("--max-candidates", type=int, default=20)
    p_full_paper.add_argument("--internal-model-id", default="openrouter/qwen/qwen3.5-397b-a17b")
    p_full_paper.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_full_paper.add_argument("--spent-usd", type=float, default=0.0)
    p_full_paper.add_argument("--max-cost-usd", type=float, default=5.0)
    p_full_paper.add_argument("--real-call", action="store_true")
    p_full_paper.add_argument("--allow-network", action="store_true")
    p_full_paper.add_argument("--confirm-openrouter-charge", action="store_true")
    p_full_paper.add_argument("--output-dir")
    p_full_paper.add_argument("--one-shot-fulltext", action="store_true")
    p_full_paper.add_argument("--allow-fulltext-prompt", action="store_true")
    p_full_paper.add_argument("--target-input-tokens", type=int)
    p_full_paper.add_argument("--max-input-tokens", type=int)
    p_full_paper.add_argument("--max-output-tokens", type=int)
    p_full_paper.add_argument("--max-total-tokens", type=int)
    p_full_paper.add_argument("--min-input-tokens-required", type=int)
    p_full_paper.add_argument("--min-output-tokens-expected", type=int)
    p_full_paper.add_argument("--fail-if-input-under-min", action="store_true")
    p_full_paper.add_argument("--fail-if-total-exceeds-context", action="store_true")
    p_full_paper.add_argument("--require-schema-valid-output", action="store_true")
    p_full_paper.add_argument("--pretty", action="store_true")
    p_full_paper.add_argument("--output")
    p_full_paper.set_defaults(func=cmd_full_paper_canary)

    p_full_paper_review = sub.add_parser("full-paper-review")
    p_full_paper_review.add_argument("analysis_json")
    p_full_paper_review.add_argument("--run-audit")
    p_full_paper_review.add_argument("--output-dir")
    p_full_paper_review.add_argument("--pretty", action="store_true")
    p_full_paper_review.set_defaults(func=cmd_full_paper_review)

    p_three_fulltext = sub.add_parser("three-paper-fulltext-canary")
    p_three_fulltext.add_argument("--query-profile", default="datacenter_networking")
    p_three_fulltext.add_argument("--provider", action="append", choices=["arxiv", "openalex", "crossref", "semantic_scholar", "ietf"])
    p_three_fulltext.add_argument("--arxiv-id")
    p_three_fulltext.add_argument("--max-candidates", type=int, default=30)
    p_three_fulltext.add_argument("--max-papers", type=int, default=3)
    p_three_fulltext.add_argument("--internal-model-id-analysis", default="openrouter/qwen/qwen3.5-397b-a17b")
    p_three_fulltext.add_argument("--internal-model-id-critic", default="openrouter/qwen/qwen3.5-397b-a17b")
    p_three_fulltext.add_argument("--internal-model-id-cross-validation", default="openrouter/qwen/qwen3.5-397b-a17b")
    p_three_fulltext.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_three_fulltext.add_argument("--spent-usd", type=float, default=0.0)
    p_three_fulltext.add_argument("--max-cost-usd", type=float, default=20.0)
    p_three_fulltext.add_argument("--real-call", action="store_true")
    p_three_fulltext.add_argument("--allow-network", action="store_true")
    p_three_fulltext.add_argument("--confirm-openrouter-charge", action="store_true")
    p_three_fulltext.add_argument("--output-dir")
    p_three_fulltext.add_argument("--pretty", action="store_true")
    p_three_fulltext.add_argument("--output")
    p_three_fulltext.set_defaults(func=cmd_three_paper_fulltext_canary)

    p_email = sub.add_parser("email-draft")
    p_email.add_argument("run_dir_or_brief_path")
    p_email.add_argument("--output-dir")
    p_email.add_argument("--to")
    p_email.add_argument("--cc")
    p_email.add_argument("--bcc")
    p_email.add_argument("--subject")
    p_email.add_argument("--allow-real-recipient", action="store_true")
    p_email.add_argument("--no-attachments", action="store_true")
    p_email.add_argument("--pretty", action="store_true")
    p_email.add_argument("--output")
    p_email.set_defaults(func=cmd_email_draft)

    p_review = sub.add_parser("pre-send-review")
    p_review.add_argument("email_draft_dir_or_manifest")
    p_review.add_argument("--output-dir")
    p_review.add_argument("--pretty", action="store_true")
    p_review.add_argument("--output")
    p_review.set_defaults(func=cmd_pre_send_review)

    p_discover = sub.add_parser("discover-sources")
    p_discover.add_argument("--query-profile", default="datacenter_networking")
    p_discover.add_argument("--provider", action="append", choices=["arxiv", "openalex", "crossref", "semantic_scholar", "ietf"])
    p_discover.add_argument("--arxiv-id")
    p_discover.add_argument("--max-candidates", type=int)
    p_discover.add_argument("--dry-run", action="store_true")
    p_discover.add_argument("--no-network", action="store_true")
    p_discover.add_argument("--pretty", action="store_true")
    p_discover.add_argument("--output")
    p_discover.set_defaults(func=cmd_discover_sources)

    p_discovery_triage = sub.add_parser("discovery-triage")
    p_discovery_triage.add_argument("discovery_run_json")
    p_discovery_triage.add_argument("--max-selected", type=int, default=10)
    p_discovery_triage.add_argument("--pretty", action="store_true")
    p_discovery_triage.add_argument("--output")
    p_discovery_triage.set_defaults(func=cmd_discovery_triage)

    p_discovery_pipeline = sub.add_parser("run-discovery-72h-dry-run")
    p_discovery_pipeline.add_argument("--query-profile", default="datacenter_networking")
    p_discovery_pipeline.add_argument("--provider", action="append", choices=["arxiv", "openalex", "crossref", "semantic_scholar", "ietf"])
    p_discovery_pipeline.add_argument("--max-candidates", type=int, default=20)
    p_discovery_pipeline.add_argument("--max-selected", type=int, default=5)
    p_discovery_pipeline.add_argument("--output-dir")
    p_discovery_pipeline.add_argument("--environment", choices=["poc", "production", "quality_first", "research", "flagship"], default="quality_first")
    p_discovery_pipeline.add_argument("--spent-usd", type=float, default=0.0)
    p_discovery_pipeline.add_argument("--window-hours", type=int, default=72)
    p_discovery_pipeline.add_argument("--pretty", action="store_true")
    p_discovery_pipeline.add_argument("--output")
    p_discovery_pipeline.set_defaults(func=cmd_run_discovery_72h_dry_run)

    p_runtime_guard = sub.add_parser("runtime-guard")
    p_runtime_guard.add_argument("path")
    p_runtime_guard.set_defaults(func=cmd_runtime_guard)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
