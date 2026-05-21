from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

from .source_registry import domain_keywords, source_tier_rules, venue_keywords


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(title).lower())).strip()


def title_hash(title: str) -> str:
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()[:16]


def extract_dedup_keys(candidate: Dict[str, Any]) -> Dict[str, str]:
    keys = {"title_hash": title_hash(candidate.get("title", ""))}
    for field in ("doi", "arxiv_id", "openalex_id", "semantic_scholar_id", "ietf_id"):
        value = candidate.get(field)
        if value:
            keys[field] = str(value).lower()
    return keys


def _text(candidate_or_text: Dict[str, Any] | str) -> str:
    if isinstance(candidate_or_text, dict):
        parts = [
            candidate_or_text.get("title", ""),
            candidate_or_text.get("abstract", ""),
            candidate_or_text.get("venue", ""),
            " ".join(candidate_or_text.get("authors") or []),
        ]
        return " ".join(str(p) for p in parts).lower()
    return str(candidate_or_text).lower()


def detect_domain_hints(text: Dict[str, Any] | str) -> list[str]:
    lowered = _text(text)
    hits = []
    for domain, keywords in domain_keywords().items():
        if any(keyword.lower() in lowered for keyword in keywords):
            hits.append(domain)
    return hits


def detect_source_tier_hint(candidate: Dict[str, Any]) -> str:
    text = _text(candidate)
    provider = candidate.get("source_provider")
    doc_type = candidate.get("document_type")
    if provider == "ietf" or doc_type in {"rfc", "standard"}:
        return "A"
    for keyword in venue_keywords():
        if keyword.lower() in text:
            return "A"
    rules = source_tier_rules()
    for tier in ("A", "B", "C", "D"):
        if any(term.lower() in text for term in rules.get(tier, [])):
            return tier
    if provider == "arxiv":
        return "C"
    return "unknown"


def detect_credibility_hints(candidate: Dict[str, Any]) -> list[str]:
    tier = detect_source_tier_hint(candidate)
    hints = [f"tier_hint_{tier}"]
    text = _text(candidate)
    if any(term in text for term in ("experiment", "baseline", "measurement", "production", "rfc", "standard")):
        hints.append("evidence_signal")
    if detect_vendor_or_marketing(candidate):
        hints.append("vendor_or_marketing_risk")
    if detect_weak_source(candidate):
        hints.append("weak_source")
    return hints


def detect_vendor_or_marketing(candidate: Dict[str, Any]) -> bool:
    text = _text(candidate)
    return any(term in text for term in ("vendor", "whitepaper", "breakthrough", "best-in-class", "press release", "product"))


def detect_weak_source(candidate: Dict[str, Any]) -> bool:
    text = _text(candidate)
    return any(term in text for term in ("news", "summary", "overview", "medium")) or candidate.get("document_type") == "news"


def _priority(candidate: Dict[str, Any]) -> str:
    tier = candidate.get("source_tier_hint") or detect_source_tier_hint(candidate)
    domains = candidate.get("domain_hints") or detect_domain_hints(candidate)
    credibility = candidate.get("credibility_hints") or detect_credibility_hints(candidate)
    if tier in {"A", "B"} and domains and "evidence_signal" in credibility and not detect_vendor_or_marketing(candidate):
        return "High"
    if tier in {"A", "B"} and domains:
        return "Medium"
    return "Low"


def _score(candidate: Dict[str, Any]) -> tuple[int, int, int, str]:
    tier = candidate.get("source_tier_hint") or "unknown"
    priority = candidate.get("deep_read_priority_hint") or _priority(candidate)
    tier_score = {"A": 0, "B": 1, "C": 2, "D": 3, "unknown": 4}.get(tier, 4)
    priority_score = {"High": 0, "Medium": 1, "Low": 2, "unknown": 3}.get(priority, 3)
    domain_score = 0 if candidate.get("domain_hints") else 1
    return (tier_score, priority_score, domain_score, normalize_title(candidate.get("title", "")))


def rank_candidates(candidates: List[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return sorted(candidates, key=_score)


def select_for_triage(candidates: List[Dict[str, Any]], max_selected: int) -> list[Dict[str, Any]]:
    return rank_candidates(candidates)[:max_selected]


def select_for_deep_read(candidates: List[Dict[str, Any]], max_selected: int) -> list[Dict[str, Any]]:
    eligible = [
        c
        for c in rank_candidates(candidates)
        if c.get("source_tier_hint") in {"A", "B"} and c.get("deep_read_priority_hint") == "High"
    ]
    return eligible[:max_selected]
