from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from .schema_validation import validate_json
from .triage import triage_candidate_metadata


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "configs" / "fulltext_policy.json"


def load_fulltext_policy(path: str | Path | None = None) -> Dict[str, Any]:
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH
    if not policy_path.is_absolute():
        policy_path = ROOT / policy_path
    return json.loads(policy_path.read_text(encoding="utf-8"))


def _host(url: str | None) -> str:
    if not url:
        return ""
    return (urlparse(url).hostname or "").lower()


def _is_arxiv_pdf(url: str | None) -> bool:
    host = _host(url)
    return host.endswith("arxiv.org") and "/pdf/" in str(url)


def _provider_allowed(candidate: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    return str(candidate.get("source_provider") or "") in set(policy.get("provider_allowlist") or [])


def evaluate_fulltext_eligibility(candidate: Dict[str, Any], policy: Dict[str, Any] | None = None, manual_override: bool = False) -> Dict[str, Any]:
    policy = policy or load_fulltext_policy()
    triage = triage_candidate_metadata(candidate)
    pdf_url = candidate.get("pdf_url")
    source_url = candidate.get("source_url")
    provider = str(candidate.get("source_provider") or "unknown")

    reasons = []
    provider_allowed = _provider_allowed(candidate, policy)
    url_open_access = _is_arxiv_pdf(pdf_url)
    tier_allowed = triage.get("source_tier") in set(policy.get("eligible_source_tiers") or [])
    priority_allowed = triage.get("deep_read_priority") == policy.get("eligible_deep_read_priority")

    if not provider_allowed:
        reasons.append("source provider is not in open-access fulltext allowlist")
    if not url_open_access:
        reasons.append("pdf_url is not an explicitly allowed open-access arXiv PDF URL")
    if not tier_allowed or not priority_allowed:
        reasons.append("only A/B + High candidates are eligible for full-paper canary")
    if triage.get("source_tier") in {"C", "D"} and not manual_override:
        reasons.append("C/D candidates cannot enter fulltext analysis")

    open_access = bool(provider_allowed and url_open_access)
    fetch_allowed = bool(open_access and tier_allowed and priority_allowed and triage.get("source_tier") not in {"C", "D"})
    result = {
        "candidate_id": str(candidate.get("candidate_id") or "unknown"),
        "source_provider": provider,
        "pdf_url": pdf_url,
        "source_url": source_url,
        "open_access": open_access,
        "eligibility_reason": "eligible open-access A/B + High candidate" if fetch_allowed else "; ".join(reasons) or "not eligible",
        "fetch_allowed": fetch_allowed,
        "paywall_bypass": False,
        "pdf_download_allowed": fetch_allowed,
        "max_pdf_bytes": int(policy["max_pdf_bytes"]),
        "max_pages": int(policy["max_pages"]),
        "max_extracted_chars": int(policy["max_extracted_chars"]),
        "triage": triage,
        "runtime_boundary": {
            "open_access_only": True,
            "provider_allowlist_enforced": True,
            "arbitrary_url_fetch_enabled": False,
            "paywall_bypass_enabled": False,
            "credentials_used": False,
            "publisher_pdf_fetch_enabled": False,
            "codex_runtime_used": False,
        },
    }
    validate_json(result, "fulltext_eligibility")
    return result


def select_fulltext_candidates(candidates: list[Dict[str, Any]], max_papers: int, policy: Dict[str, Any] | None = None) -> list[Dict[str, Any]]:
    policy = policy or load_fulltext_policy()
    selected = []
    for candidate in candidates:
        eligibility = evaluate_fulltext_eligibility(candidate, policy)
        if eligibility["fetch_allowed"]:
            selected.append({"candidate": candidate, "eligibility": eligibility})
        if len(selected) >= max_papers:
            break
    return selected
