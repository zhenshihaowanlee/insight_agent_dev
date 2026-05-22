from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List

from .discovery_filters import (
    detect_credibility_hints,
    detect_domain_hints,
    detect_source_tier_hint,
    extract_dedup_keys,
    rank_candidates,
    select_for_deep_read,
    select_for_triage,
)
from .schema_validation import validate_json
from .source_registry import PROVIDER_ALLOWLIST, load_source_discovery_config, provider_endpoints, query_profiles, user_agent
from .triage import triage_candidate_metadata


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(provider: str, record_id: str, title: str) -> str:
    seed = f"{provider}:{record_id}:{title}"
    return "cand-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _request_json(url: str, config: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent(config), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=int(config["timeout_seconds"])) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _request_text(url: str, config: Dict[str, Any]) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent(config), "Accept": "application/atom+xml, application/json"})
    with urllib.request.urlopen(req, timeout=int(config["timeout_seconds"])) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _query(query_profile: str, config: Dict[str, Any]) -> str:
    profiles = query_profiles(config)
    if query_profile not in profiles:
        raise ValueError(f"unknown query profile: {query_profile}")
    return profiles[query_profile]


def _candidate(provider: str, record_id: str, title: str, abstract: str = "", authors: list[str] | None = None, published_at: str | None = None, updated_at: str | None = None, venue: str = "", source_url: str | None = None, pdf_url: str | None = None, doi: str | None = None, arxiv_id: str | None = None, openalex_id: str | None = None, semantic_scholar_id: str | None = None, ietf_id: str | None = None, document_type: str = "unknown", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    discovered_at = _now()
    item = {
        "candidate_id": _id(provider, record_id, title),
        "discovered_at": discovered_at,
        "source_provider": provider,
        "provider_record_id": record_id or "",
        "title": title or "untitled",
        "abstract": abstract or "",
        "authors": authors or [],
        "published_at": published_at,
        "updated_at": updated_at,
        "venue": venue or "",
        "source_url": source_url,
        "pdf_url": pdf_url,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "openalex_id": openalex_id,
        "semantic_scholar_id": semantic_scholar_id,
        "ietf_id": ietf_id,
        "document_type": document_type,
        "source_tier_hint": "unknown",
        "domain_hints": [],
        "credibility_hints": [],
        "business_relevance_hints": [],
        "deep_read_priority_hint": "unknown",
        "keyword_matches": [],
        "dedup_keys": {},
        "body_is_untrusted": True,
        "provenance": {"provider": provider, "metadata_only": True, "pdf_downloaded": False, "fulltext_fetched": False},
        "metadata": metadata or {},
    }
    return classify_candidate_metadata(item)


def enrich_candidate_metadata(candidate: Dict[str, Any]) -> Dict[str, Any]:
    title = str(candidate.get("title") or "").lower()
    arxiv_id = str(candidate.get("arxiv_id") or candidate.get("provider_record_id") or "")
    metadata = dict(candidate.get("metadata") or {})
    if "megascale-infer" in title or arxiv_id.startswith("2504.02263"):
        candidate["venue"] = "SIGCOMM 2025"
        candidate["source_tier_hint"] = "A"
        enriched_domains = [
            "AI cluster networking",
            "datacenter systems",
            "distributed inference",
            "GPU communication / M2N communication",
        ]
        existing = list(candidate.get("domain_hints") or [])
        candidate["domain_hints"] = sorted(set(existing + enriched_domains))
        metadata.update(
            {
                "venue_enrichment": "manual_sigcomm_2025_accepted_metadata",
                "accepted_venue": "SIGCOMM 2025",
                "title_rule": "MegaScale-Infer",
                "metadata_only": True,
            }
        )
        candidate["metadata"] = metadata
    return candidate


def classify_candidate_metadata(candidate: Dict[str, Any]) -> Dict[str, Any]:
    candidate = enrich_candidate_metadata(candidate)
    candidate["domain_hints"] = detect_domain_hints(candidate)
    candidate = enrich_candidate_metadata(candidate)
    candidate["source_tier_hint"] = detect_source_tier_hint(candidate)
    candidate = enrich_candidate_metadata(candidate)
    candidate["credibility_hints"] = detect_credibility_hints(candidate)
    candidate["business_relevance_hints"] = ["target_domain"] if candidate["domain_hints"] else []
    triage = triage_candidate_metadata(candidate)
    candidate["deep_read_priority_hint"] = triage["deep_read_priority"]
    candidate["keyword_matches"] = sorted(set(candidate["domain_hints"]))
    candidate["dedup_keys"] = extract_dedup_keys(candidate)
    validate_json(candidate, "source_candidate")
    return candidate


def _parse_arxiv_entries(xml: str) -> list[Dict[str, Any]]:
    root = ET.fromstring(xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results = []
    for entry in root.findall("atom:entry", ns):
        title = " ".join(entry.findtext("atom:title", default="", namespaces=ns).split())
        abstract = entry.findtext("atom:summary", default="", namespaces=ns)
        url = entry.findtext("atom:id", default="", namespaces=ns)
        authors = [a.findtext("atom:name", default="", namespaces=ns) for a in entry.findall("atom:author", ns)]
        pdf = None
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf = link.attrib.get("href")
        arxiv_id = url.rsplit("/", 1)[-1] if url else None
        if arxiv_id and pdf is None:
            pdf = f"https://arxiv.org/pdf/{arxiv_id}"
        if arxiv_id:
            base_id = re.sub(r"v\d+$", "", arxiv_id)
            pdf = f"https://arxiv.org/pdf/{base_id}"
        results.append(_candidate("arxiv", arxiv_id or url, title, abstract, authors, entry.findtext("atom:published", namespaces=ns), entry.findtext("atom:updated", namespaces=ns), "arXiv", url, pdf, arxiv_id=arxiv_id, document_type="paper"))
    return results


def query_arxiv(query_profile: str, max_candidates: int, config: Dict[str, Any]) -> list[Dict[str, Any]]:
    endpoint = provider_endpoints(config)["arxiv"]
    params = urllib.parse.urlencode({"search_query": "all:" + _query(query_profile, config), "start": 0, "max_results": max_candidates})
    xml = _request_text(f"{endpoint}?{params}", config)
    return _parse_arxiv_entries(xml)


def query_arxiv_id(arxiv_id: str, config: Dict[str, Any]) -> list[Dict[str, Any]]:
    endpoint = provider_endpoints(config)["arxiv"]
    clean_id = str(arxiv_id).strip().removeprefix("arXiv:").removeprefix("arxiv:")
    params = urllib.parse.urlencode({"id_list": clean_id, "start": 0, "max_results": 1})
    xml = _request_text(f"{endpoint}?{params}", config)
    results = _parse_arxiv_entries(xml)
    if results:
        return results
    return []


def _abstract_from_openalex(index: Dict[str, list[int]] | None) -> str:
    if not isinstance(index, dict):
        return ""
    pairs = []
    for word, positions in index.items():
        for pos in positions:
            pairs.append((pos, word))
    return " ".join(word for _, word in sorted(pairs))


def query_openalex(query_profile: str, max_candidates: int, config: Dict[str, Any]) -> list[Dict[str, Any]]:
    endpoint = provider_endpoints(config)["openalex"]
    params = urllib.parse.urlencode({"search": _query(query_profile, config), "per-page": max_candidates})
    data = _request_json(f"{endpoint}?{params}", config)
    results = []
    for item in data.get("results", [])[:max_candidates]:
        authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])]
        loc = item.get("primary_location") or {}
        source = loc.get("source") or {}
        results.append(_candidate("openalex", item.get("id", ""), item.get("display_name", ""), _abstract_from_openalex(item.get("abstract_inverted_index")), authors, str(item.get("publication_year") or ""), None, source.get("display_name", ""), item.get("id"), (loc.get("pdf_url") or None), item.get("doi"), openalex_id=item.get("id"), document_type="paper", metadata={"type": item.get("type")}))
    return results


def query_crossref(query_profile: str, max_candidates: int, config: Dict[str, Any]) -> list[Dict[str, Any]]:
    endpoint = provider_endpoints(config)["crossref"]
    params = urllib.parse.urlencode({"query": _query(query_profile, config), "rows": max_candidates})
    data = _request_json(f"{endpoint}?{params}", config)
    results = []
    for item in (data.get("message") or {}).get("items", [])[:max_candidates]:
        title = (item.get("title") or [""])[0]
        authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in item.get("author", [])]
        venue = (item.get("container-title") or [""])[0]
        published = item.get("published-print") or item.get("published-online") or {}
        date_parts = (published.get("date-parts") or [[None]])[0]
        results.append(_candidate("crossref", item.get("DOI", ""), title, item.get("abstract", ""), authors, "-".join(str(p) for p in date_parts if p), None, venue, item.get("URL"), None, item.get("DOI"), document_type="paper", metadata={"type": item.get("type")}))
    return results


def query_semantic_scholar(query_profile: str, max_candidates: int, config: Dict[str, Any]) -> list[Dict[str, Any]]:
    endpoint = provider_endpoints(config)["semantic_scholar"]
    params = urllib.parse.urlencode({"query": _query(query_profile, config), "limit": max_candidates, "fields": "title,abstract,authors,year,venue,url,externalIds"})
    data = _request_json(f"{endpoint}?{params}", config)
    results = []
    for item in data.get("data", [])[:max_candidates]:
        ext = item.get("externalIds") or {}
        results.append(_candidate("semantic_scholar", item.get("paperId", ""), item.get("title", ""), item.get("abstract", ""), [a.get("name", "") for a in item.get("authors", [])], str(item.get("year") or ""), None, item.get("venue", ""), item.get("url"), None, ext.get("DOI"), ext.get("ArXiv"), semantic_scholar_id=item.get("paperId"), document_type="paper"))
    return results


def query_ietf(query_profile: str, max_candidates: int, config: Dict[str, Any]) -> list[Dict[str, Any]]:
    endpoint = provider_endpoints(config)["ietf"]
    params = urllib.parse.urlencode({"limit": max_candidates, "title__contains": _query(query_profile, config).split()[0]})
    data = _request_json(f"{endpoint}?{params}", config)
    results = []
    for item in data.get("objects", [])[:max_candidates]:
        name = item.get("name", "")
        doc_type = "rfc" if name.startswith("rfc") else "internet_draft"
        results.append(_candidate("ietf", name, item.get("title", name), "", [], item.get("time"), item.get("expires"), "IETF", "https://datatracker.ietf.org/doc/" + name + "/", None, ietf_id=name, document_type=doc_type, metadata={"states": item.get("states")}))
    return results


def normalize_candidate(raw: Dict[str, Any], provider: str) -> Dict[str, Any]:
    raw["source_provider"] = provider
    return classify_candidate_metadata(raw)


def discover_provider(provider: str, query_profile: str, max_candidates: int, config: Dict[str, Any]) -> list[Dict[str, Any]]:
    if provider not in PROVIDER_ALLOWLIST:
        raise ValueError(f"provider not allowed: {provider}")
    functions = {
        "arxiv": query_arxiv,
        "openalex": query_openalex,
        "crossref": query_crossref,
        "semantic_scholar": query_semantic_scholar,
        "ietf": query_ietf,
    }
    time.sleep(float(config["rate_limit"]["min_interval_seconds_per_provider"]))
    return functions[provider](query_profile, max_candidates, config)


def deduplicate_candidates(candidates: list[Dict[str, Any]]) -> Dict[str, Any]:
    seen = {}
    unique = []
    duplicates = []
    for item in candidates:
        keys = item.get("dedup_keys") or extract_dedup_keys(item)
        match = None
        for key, value in keys.items():
            composite = f"{key}:{value}"
            if composite in seen:
                match = seen[composite]
                break
        if match:
            duplicates.append({"candidate_id": item["candidate_id"], "duplicate_of": match})
            continue
        unique.append(item)
        for key, value in keys.items():
            seen[f"{key}:{value}"] = item["candidate_id"]
    return {"candidates": unique, "duplicates": duplicates, "deduplicated_count": len(duplicates)}


def build_watchlist(candidates: list[Dict[str, Any]], triage_preview: list[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    preview_by_id = {item["candidate_id"]: item for item in (triage_preview or [])}
    selected = []
    signal = []
    background = []
    for candidate in rank_candidates(candidates):
        triage = preview_by_id.get(candidate["candidate_id"]) or triage_candidate_metadata(candidate)
        entry = {
            "candidate_id": candidate["candidate_id"],
            "title": candidate["title"],
            "source_provider": candidate.get("source_provider"),
            "provider_record_id": candidate.get("provider_record_id"),
            "arxiv_id": candidate.get("arxiv_id"),
            "venue": candidate.get("venue"),
            "source_tier": triage["source_tier"],
            "deep_read_priority": triage["deep_read_priority"],
            "domain": triage["domain"],
            "domain_hints": candidate.get("domain_hints") or [],
            "strong_conclusion_allowed": False,
        }
        if triage["source_tier"] in {"A", "B"} and triage["deep_read_priority"] == "High":
            selected.append(entry)
        elif triage["source_tier"] == "C":
            signal.append(entry)
        else:
            background.append(entry)
    return {"selected_for_deep_read": selected, "signal_only": signal, "background_only": background}


def score_candidate_for_deep_read(candidate: Dict[str, Any]) -> Dict[str, Any]:
    triage = triage_candidate_metadata(candidate)
    selected = triage["source_tier"] in {"A", "B"} and triage["deep_read_priority"] == "High"
    return {"candidate_id": candidate["candidate_id"], "selected_for_deep_read": selected, "triage": triage}


def discover_sources(query_profile: str = "datacenter_networking", providers: list[str] | None = None, max_candidates: int | None = None, dry_run: bool = False, network_enabled: bool = True, metadata_only: bool = True, arxiv_id: str | None = None) -> Dict[str, Any]:
    return run_discovery(query_profile, providers, max_candidates, dry_run, network_enabled, metadata_only, arxiv_id=arxiv_id)


def run_discovery(query_profile: str = "datacenter_networking", providers: list[str] | None = None, max_candidates: int | None = None, dry_run: bool = False, network_enabled: bool = True, metadata_only: bool = True, arxiv_id: str | None = None) -> Dict[str, Any]:
    config = load_source_discovery_config()
    requested = ["arxiv"] if arxiv_id else (providers or list(config["provider_allowlist"]))
    for provider in requested:
        if provider not in config["provider_allowlist"]:
            raise ValueError(f"provider not allowed: {provider}")
    per_provider = min(int(config["max_candidates_per_provider"]), int(max_candidates or config["max_candidates_per_provider"]))
    provider_errors = []
    candidates = []
    executed = []
    if dry_run or not network_enabled:
        sample = _candidate("manual_watchlist", "dry-run", "Dry-run datacenter RDMA congestion control candidate", "SIGCOMM style experiment baseline p99 RDMA datacenter", ["ZYW"], "2026", None, "SIGCOMM", "https://example.invalid/source", None, document_type="paper")
        candidates = [sample]
    elif arxiv_id:
        try:
            candidates.extend(query_arxiv_id(arxiv_id, config))
            executed.append("arxiv")
        except Exception as exc:
            provider_errors.append({"provider": "arxiv", "error": type(exc).__name__, "message": str(exc)[:300]})
    else:
        for provider in requested:
            try:
                candidates.extend(discover_provider(provider, query_profile, per_provider, config))
                executed.append(provider)
            except Exception as exc:
                provider_errors.append({"provider": provider, "error": type(exc).__name__, "message": str(exc)[:300]})
    candidates = candidates[: int(max_candidates or config["max_total_candidates"])]
    dedup = deduplicate_candidates(candidates)
    unique = dedup["candidates"]
    triage_preview = [triage_candidate_metadata(item) for item in select_for_triage(unique, int(config["max_selected_for_triage"]))]
    deep = select_for_deep_read(unique, int(config["max_selected_for_deep_read"]))
    watchlist = build_watchlist(unique, triage_preview)
    run = {
        "discovery_run_id": "disc-" + hashlib.sha256((_now() + query_profile).encode("utf-8")).hexdigest()[:16],
        "created_at": _now(),
        "dry_run": bool(dry_run),
        "network_used": bool(network_enabled and not dry_run),
        "real_metadata_discovery": bool(network_enabled and not dry_run),
        "providers_requested": requested,
        "providers_executed": executed,
        "query_profile": query_profile,
        "arxiv_id": arxiv_id,
        "candidate_count": len(candidates),
        "deduplicated_count": dedup["deduplicated_count"],
        "selected_for_triage_count": len(triage_preview),
        "selected_for_deep_read_count": len(deep),
        "candidates": unique,
        "deduplication_report": {"duplicates": dedup["duplicates"]},
        "watchlist": watchlist,
        "triage_preview": triage_preview,
        "provider_errors": provider_errors,
        "runtime_boundary": {
            "codex_runtime_used": False,
            "openrouter_called": False,
            "network_request_sent": bool(network_enabled and not dry_run),
            "discovery_network_used": bool(network_enabled and not dry_run),
            "model_network_used": False,
            "pdf_downloaded": False,
            "fulltext_fetched": False,
            "paywall_bypassed": False,
            "email_sent": False,
            "webhook_sent": False,
        },
        "validation": {"schema_valid": True, "metadata_only": metadata_only},
        "notes": ["metadata-only source discovery; no PDF download, fulltext fetch, model call, or delivery"],
    }
    validate_json(run, "discovery_run")
    return run
