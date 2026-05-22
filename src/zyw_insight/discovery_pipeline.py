from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .pipeline import run_72h_dry_run_pipeline
from .schema_validation import validate_json
from .source_discovery import build_watchlist, discover_sources
from .triage import triage_candidate_metadata


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return lowered[:96] or "candidate"


def _run_id(created_at: str, query_profile: str) -> str:
    seed = f"{created_at}:{query_profile}"
    return "discpipe-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _default_output_dir(created_at: str, query_profile: str) -> Path:
    safe_ts = created_at.replace(":", "").replace("+", "Z")
    return Path(".zyw_insight") / "discovery_pipeline_runs" / f"{safe_ts}-{_safe_name(query_profile)}"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _candidate_by_id(discovery_run: Dict[str, Any]) -> dict[str, Dict[str, Any]]:
    return {str(candidate.get("candidate_id")): candidate for candidate in discovery_run.get("candidates") or []}


def _eligible_for_stub(candidate: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
    triage = triage_candidate_metadata(candidate)
    return triage.get("source_tier") in {"A", "B"} and triage.get("deep_read_priority") == "High", triage


def _stub_text(candidate: Dict[str, Any], triage: Dict[str, Any]) -> str:
    title = str(candidate.get("title") or "Untitled metadata candidate")
    abstract = str(candidate.get("abstract") or "No abstract provided by metadata provider.")
    provider = str(candidate.get("source_provider") or "unknown")
    source_url = str(candidate.get("source_url") or "")
    venue = str(candidate.get("venue") or "")
    domain_hints = ", ".join(candidate.get("domain_hints") or [])
    authors = ", ".join(candidate.get("authors") or [])
    provenance = candidate.get("provenance") or {}
    metadata = {
        "candidate_id": candidate.get("candidate_id"),
        "provider_record_id": candidate.get("provider_record_id"),
        "doi": candidate.get("doi"),
        "arxiv_id": candidate.get("arxiv_id"),
        "openalex_id": candidate.get("openalex_id"),
        "semantic_scholar_id": candidate.get("semantic_scholar_id"),
        "ietf_id": candidate.get("ietf_id"),
        "published_at": candidate.get("published_at"),
        "updated_at": candidate.get("updated_at"),
    }
    return f"""# {title}

UNTRUSTED METADATA ONLY.
No full text fetched.
No PDF downloaded.
Not sufficient for strong conclusion.
body_is_untrusted: true

## CNI Discovery Triage

- document_type: {triage.get("document_type", "unknown")}
- source_tier: {triage.get("source_tier", "unknown")}
- domain: {triage.get("domain", "unknown")}
- credibility: {triage.get("credibility", "unknown")}
- business_relevance: {triage.get("business_relevance", "unknown")}
- deep_read_priority: {triage.get("deep_read_priority", "unknown")}
- selected_for_deep_read: true
- strong_conclusion_allowed: false

## Metadata

- provider: {provider}
- venue: {venue}
- source_url: {source_url}
- authors: {authors}
- domain_hints: {domain_hints}
- provenance: metadata_only={bool(provenance.get("metadata_only", True))}, pdf_downloaded=false, fulltext_fetched=false, paywall_bypassed=false

## Abstract

{abstract}

## Provider Metadata

```json
{json.dumps(metadata, ensure_ascii=False, indent=2)}
```

## Handling Constraints

This local file is an analysis-ready metadata stub, not a paper body. It exists only to let the deterministic CNI dry-run pipeline exercise ingestion, triage, analysis, critic, brief synthesis, adapter dry-run, email draft, and pre-send review. Any future strong conclusion requires human-approved full-source review and quality gates.
"""


def materialize_selected_candidates(
    discovery_run: Dict[str, Any],
    watchlist: Dict[str, Any] | None,
    output_dir: str | Path,
    max_selected: int,
) -> Dict[str, Any]:
    candidates = _candidate_by_id(discovery_run)
    selected_entries = list((watchlist or {}).get("selected_for_deep_read") or [])[:max_selected]
    stubs_dir = Path(output_dir)
    stubs_dir.mkdir(parents=True, exist_ok=True)

    materialized = []
    blocked = []
    for entry in selected_entries:
        candidate_id = str(entry.get("candidate_id"))
        candidate = candidates.get(candidate_id)
        if not candidate:
            blocked.append({"candidate_id": candidate_id, "reason": "candidate metadata missing"})
            continue
        eligible, triage = _eligible_for_stub(candidate)
        if not eligible:
            blocked.append(
                {
                    "candidate_id": candidate_id,
                    "source_tier": triage.get("source_tier"),
                    "deep_read_priority": triage.get("deep_read_priority"),
                    "reason": "only A/B + High candidates may be materialized",
                }
            )
            continue
        path = stubs_dir / f"{_safe_name(candidate_id)}-{_safe_name(candidate.get('title', 'metadata-stub'))}.md"
        path.write_text(_stub_text(candidate, triage), encoding="utf-8")
        materialized.append(
            {
                "candidate_id": candidate_id,
                "stub_path": str(path),
                "title": candidate.get("title"),
                "source_provider": candidate.get("source_provider"),
                "source_url": candidate.get("source_url"),
                "source_tier": triage.get("source_tier"),
                "deep_read_priority": triage.get("deep_read_priority"),
                "domain": triage.get("domain"),
                "body_is_untrusted": True,
                "metadata_only": True,
                "pdf_downloaded": False,
                "fulltext_fetched": False,
                "paywall_bypassed": False,
                "strong_conclusion_allowed": False,
            }
        )

    return {
        "selected_candidate_stubs_dir": str(stubs_dir),
        "materialized_count": len(materialized),
        "materialized": materialized,
        "blocked": blocked,
        "policy": {
            "metadata_only": True,
            "eligible_source_tiers": ["A", "B"],
            "eligible_deep_read_priority": "High",
            "signal_only_tiers": ["C"],
            "background_only_tiers": ["D"],
            "pdf_download_enabled": False,
            "fulltext_fetch_enabled": False,
            "paywall_bypass_enabled": False,
            "strong_conclusion_allowed": False,
        },
    }


def run_discovery_72h_dry_run(
    query_profile: str = "datacenter_networking",
    providers: list[str] | None = None,
    max_candidates: int | None = None,
    max_selected: int = 5,
    output_dir: str | Path | None = None,
    environment: str = "quality_first",
    spent_usd: float = 0,
    window_hours: int = 72,
) -> Dict[str, Any]:
    created_at = _now()
    run_id = _run_id(created_at, query_profile)
    run_dir = Path(output_dir) if output_dir else _default_output_dir(created_at, query_profile)
    selected_root = Path(".zyw_insight") / "discovery_selected" / run_id
    selected_stubs_dir = run_dir / "selected_candidate_stubs"

    discovery_run = discover_sources(
        query_profile=query_profile,
        providers=providers,
        max_candidates=max_candidates,
        dry_run=False,
        network_enabled=True,
        metadata_only=True,
    )
    validate_json(discovery_run, "discovery_run")
    discovery_path = run_dir / "discovery_run.json"
    _write_json(discovery_path, discovery_run)

    watchlist = build_watchlist(discovery_run.get("candidates") or [], discovery_run.get("triage_preview") or [])
    selected = list(watchlist.get("selected_for_deep_read") or [])[:max_selected]
    triage_result = {
        "discovery_run_id": discovery_run.get("discovery_run_id"),
        "watchlist": watchlist,
        "selected_for_deep_read": selected,
        "selected_for_deep_read_count": len(selected),
        "strong_conclusion_allowed": False,
        "notes": ["discovery triage is metadata-only and does not call models"],
    }
    triage_path = run_dir / "discovery_triage.json"
    _write_json(triage_path, triage_result)

    materialized = materialize_selected_candidates(discovery_run, {"selected_for_deep_read": selected}, selected_stubs_dir, max_selected)
    mirror = materialize_selected_candidates(discovery_run, {"selected_for_deep_read": selected}, selected_root, max_selected)
    materialized["canonical_selected_dir"] = str(selected_root)
    materialized["canonical_materialized"] = mirror["materialized"]
    materialized_path = run_dir / "materialized_candidates.json"
    _write_json(materialized_path, materialized)

    pipeline_run = run_72h_dry_run_pipeline(
        selected_stubs_dir,
        output_dir=run_dir / "pipeline",
        environment=environment,
        spent_usd=spent_usd,
        window_hours=window_hours,
        max_documents=max_selected,
        write_ledger=True,
        trigger="manual",
    )
    pipeline_path = run_dir / "pipeline_run.json"
    _write_json(pipeline_path, pipeline_run)

    brief_json_src = Path(pipeline_run["artifacts"]["brief_json"])
    brief_md_src = Path(pipeline_run["artifacts"]["brief_markdown"])
    brief_json_path = run_dir / "brief.json"
    brief_md_path = run_dir / "brief.md"
    compatible_brief_dir = run_dir / "brief"
    compatible_brief_json_path = compatible_brief_dir / "brief.json"
    compatible_brief_md_path = compatible_brief_dir / "brief.md"
    if brief_json_src.exists():
        brief_json_text = brief_json_src.read_text(encoding="utf-8")
        brief_json_path.write_text(brief_json_text, encoding="utf-8")
        compatible_brief_json_path.parent.mkdir(parents=True, exist_ok=True)
        compatible_brief_json_path.write_text(brief_json_text, encoding="utf-8")
    if brief_md_src.exists():
        brief_md_text = brief_md_src.read_text(encoding="utf-8")
        brief_md_path.write_text(brief_md_text, encoding="utf-8")
        compatible_brief_md_path.parent.mkdir(parents=True, exist_ok=True)
        compatible_brief_md_path.write_text(brief_md_text, encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "created_at": created_at,
        "query_profile": query_profile,
        "providers": providers or discovery_run.get("providers_requested") or [],
        "max_candidates": max_candidates,
        "max_selected": max_selected,
        "discovery_run_id": discovery_run.get("discovery_run_id"),
        "artifact_paths": {
            "output_dir": str(run_dir),
            "discovery_run": str(discovery_path),
            "discovery_triage": str(triage_path),
            "selected_candidate_stubs": str(selected_stubs_dir),
            "canonical_discovery_selected_dir": str(selected_root),
            "materialized_candidates": str(materialized_path),
            "pipeline_run": str(pipeline_path),
            "pipeline_output_dir": pipeline_run["artifacts"]["output_dir"],
            "brief_json": str(brief_json_path),
            "brief_markdown": str(brief_md_path),
            "compatible_brief_json": str(compatible_brief_json_path),
            "compatible_brief_markdown": str(compatible_brief_md_path),
            "adapter_dry_run_artifacts": pipeline_run["artifacts"]["adapter_runs"],
            "redacted_ledger": pipeline_run["artifacts"]["ledger_path"],
        },
        "candidate_to_pipeline_input": [
            {
                "candidate_id": item["candidate_id"],
                "stub_path": item["stub_path"],
                "pipeline_input_dir": str(selected_stubs_dir),
                "metadata_only": True,
                "body_is_untrusted": True,
                "strong_conclusion_allowed": False,
            }
            for item in materialized["materialized"]
        ],
        "blocked_candidates": materialized["blocked"],
        "provider_errors": discovery_run.get("provider_errors") or [],
        "runtime_boundary": {
            "real_metadata_discovery": True,
            "model_network_used": False,
            "openrouter_called": False,
            "api_key_read": False,
            "pdf_downloaded": False,
            "fulltext_fetched": False,
            "paywall_bypassed": False,
            "email_sent": False,
            "webhook_sent": False,
            "deterministic_pipeline_only": True,
            "adapter_dry_run_only": True,
        },
    }
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(run_dir / "run_manifest.json", manifest)

    return {
        "run_id": run_id,
        "created_at": created_at,
        "dry_run": True,
        "output_dir": str(run_dir),
        "discovery_run": discovery_run,
        "discovery_triage": triage_result,
        "materialized_candidates": materialized,
        "pipeline_run": pipeline_run,
        "manifest": manifest,
        "artifacts": manifest["artifact_paths"] | {"manifest": str(manifest_path)},
        "provider_errors": discovery_run.get("provider_errors") or [],
        "runtime_boundary": manifest["runtime_boundary"],
        "notes": [
            "Real metadata discovery may contact approved metadata providers only.",
            "Selected stubs are metadata-only, untrusted, and not sufficient for strong conclusions.",
            "The 72h pipeline remains deterministic and does not call OpenRouter.",
        ],
    }
