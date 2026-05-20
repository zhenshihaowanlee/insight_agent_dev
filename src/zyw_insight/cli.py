from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .budget import MODEL_PRICES, SCENARIOS, budget_mode, estimate_scenario
from .quality_gates import evaluate_analysis, gate_status
from .runtime_guard import check_runtime_config


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


def cmd_analyze(args: argparse.Namespace) -> int:
    source_path = Path(args.input)
    title = source_path.stem
    now = datetime.now(timezone.utc).isoformat()
    payload: Dict[str, Any] = {
        "analysis_id": f"analysis-{title}",
        "source": {"title": title, "local_path": str(source_path), "created_at": now},
        "one_sentence_conclusion": "STUB: replace with model-generated CNI conclusion.",
        "problem_background": "unknown",
        "core_idea": "unknown",
        "innovation_points": [],
        "mechanism": {},
        "constraints": [
            {
                "name": "unknown implementation constraint",
                "type": "unknown",
                "explicitly_stated": False,
                "performance_impact": "unknown",
                "hardness": "unknown",
                "degradation_consequence": "requires analysis",
            }
        ],
        "constraint_dependency": [],
        "degraded_process_counterfactual": {
            "verdict": "unknown",
            "conditions": [],
            "failure_modes": [],
            "compensation_mechanisms": [],
        },
        "network_impact_vector": {
            key: {"impact": "?", "evidence": "unknown", "risk": "requires analysis"}
            for key in [
                "Latency",
                "Jitter/IPDV",
                "Bandwidth/Capacity",
                "Reliability",
                "Security",
                "Operations",
                "BER/Error",
                "Scalability",
                "Cost/Power",
            ]
        },
        "evidence_quality": {
            "real_deployment": "D",
            "physical_testbed": "D",
            "simulation": "D",
            "baseline": "D",
            "ablation": "D",
            "sensitivity_analysis": "D",
            "failure_analysis": "D",
            "reproducibility": "D",
        },
        "comparison_to_existing": [],
        "hidden_assumptions_and_risks": ["STUB output; not suitable for decisions."],
        "security_and_operations": {"security": "unknown", "operations": "unknown", "reliability": "unknown"},
        "reproducibility": {"status": "unknown"},
        "insights": {"direct": "unknown", "counterfactual": "unknown", "strategic": "unknown"},
        "strategic_meaning": "unknown",
        "score": {"total": 0, "dimensions": {}},
        "recommended_action": "C",
        "follow_up_experiments": ["Run full CNI model analysis."],
        "conclusion_strength": "weak",
    }
    _write_json(Path(args.output), payload)
    print(f"wrote {args.output}")
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    analyses = []
    for path in sorted(input_dir.glob("*.json")):
        try:
            analyses.append(_load_json(path))
        except json.JSONDecodeError:
            continue
    lines = ["# ZYW 72h 技术洞察简报草稿", "", f"生成时间：{datetime.now(timezone.utc).isoformat()}", ""]
    if len(analyses) < 3:
        lines.append("样本不足 3 篇，不形成强趋势结论。")
    lines.extend(["", "## 本期样本", ""])
    for item in analyses:
        lines.append(f"- {item.get('analysis_id', 'unknown')}: {item.get('one_sentence_conclusion', '')}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {output}")
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

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("--input", required=True)
    p_analyze.add_argument("--output", required=True)
    p_analyze.set_defaults(func=cmd_analyze)

    p_brief = sub.add_parser("brief")
    p_brief.add_argument("--input-dir", required=True)
    p_brief.add_argument("--output", required=True)
    p_brief.set_defaults(func=cmd_brief)

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
