from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .discovery_filters import detect_domain_hints, detect_source_tier_hint, detect_vendor_or_marketing, detect_weak_source
from .ingestion import ingest_file


DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "datacenter networking": ("datacenter", "data center", "fabric", "leaf-spine", "clos"),
    "optical interconnect": ("optical", "photonics", "co-packaged optics", "cpo", "wavelength"),
    "RDMA / RoCE": ("rdma", "roce", "pfc", "infiniband"),
    "congestion control": ("congestion control", "ecn", "dcqcn", "hpcc", "queue"),
    "AI cluster networking": ("ai cluster", "gpu cluster", "collective", "training cluster", "all-reduce"),
    "SmartNIC / DPU": ("smartnic", "dpu", "ipu", "offload"),
    "P4 / programmable data plane": ("p4", "programmable data plane", "tofino"),
    "network security": ("security", "isolation", "encryption", "ddos", "side channel"),
    "network operations": ("operations", "observability", "rollback", "incident", "telemetry"),
    "network measurement": ("measurement", "trace", "packet capture", "telemetry", "benchmark"),
    "silicon / SerDes / BER / FEC": ("silicon", "serdes", "ber", "fec", "asic", "cmos"),
}

A_TIER_KEYWORDS = (
    "sigcomm",
    "nsdi",
    "imc",
    "osdi",
    "sosp",
    "ietf",
    "rfc",
    "ieee",
    "etsi",
    "standard",
    "production system",
)
B_TIER_KEYWORDS = (
    "engineering blog",
    "technical report",
    "open source",
    "github",
    "meta engineering",
    "google research",
    "microsoft research",
    "nvidia technical",
    "cloudflare blog",
)
C_TIER_KEYWORDS = ("arxiv", "whitepaper", "white paper", "news", "press release", "vendor")
D_TIER_KEYWORDS = ("summary of", "secondary summary", "no experiment details", "marketing-only", "marketing only")

EXPERIMENT_KEYWORDS = ("experiment", "evaluation", "testbed", "prototype", "deployment", "trace", "benchmark", "p95", "p99")
BASELINE_KEYWORDS = ("baseline", "comparison", "compare against", "ablation")
BUSINESS_KEYWORDS = (
    "datacenter",
    "data center",
    "rdma",
    "roce",
    "congestion",
    "ai cluster",
    "gpu cluster",
    "smartnic",
    "dpu",
    "p4",
    "optical",
    "serdes",
    "fec",
)
MARKETING_KEYWORDS = ("breakthrough", "best-in-class", "revolutionary", "unmatched", "industry-leading", "product marketing")
VENDOR_KEYWORDS = ("vendor", "product", "solution", "platform", "whitepaper", "white paper")
AVERAGE_ONLY_KEYWORDS = ("average latency", "mean latency", "avg latency")
PROCESS_KEYWORDS = ("process", "silicon", "serdes", "ber", "fec", "asic", "power", "thermal", "implementation constraint")


def _lower_text(source: Dict[str, Any]) -> str:
    parts = [str(source.get("title", "")), str(source.get("body", ""))]
    metadata = source.get("metadata")
    if isinstance(metadata, dict):
        parts.extend(str(v) for v in metadata.values())
    return "\n".join(parts).lower()


def _detect_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    found = []
    for keyword in keywords:
        if keyword.lower() in text:
            found.append(keyword)
    return sorted(set(found))


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _domain(text: str) -> tuple[str, list[str]]:
    scores: list[tuple[int, str, list[str]]] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        found = _detect_keywords(text, keywords)
        if found:
            scores.append((len(found), domain, found))
    if not scores:
        return "unknown", []
    scores.sort(key=lambda item: (-item[0], item[1]))
    return scores[0][1], scores[0][2]


def _source_tier(text: str) -> tuple[str, str]:
    if _contains_any(text, D_TIER_KEYWORDS):
        return "D", "secondary summary, marketing-only, or missing experiment details signal"
    if _contains_any(text, A_TIER_KEYWORDS):
        return "A", "top conference, standards, RFC, or production-system signal"
    if _contains_any(text, B_TIER_KEYWORDS):
        return "B", "engineering blog, top lab, technical report, or open-source technical documentation signal"
    if _contains_any(text, C_TIER_KEYWORDS):
        return "C", "arXiv, vendor whitepaper, news, or press-release signal"
    return "D", "no high-confidence source signal detected"


def _document_type(source: Dict[str, Any], text: str) -> str:
    if "rfc" in text:
        return "rfc"
    if "standard" in text or "ietf" in text or "ieee" in text or "etsi" in text:
        return "standard"
    if _contains_any(text, ("whitepaper", "white paper")):
        return "whitepaper"
    if _contains_any(text, ("sigcomm", "nsdi", "imc", "osdi", "sosp", "paper")):
        return "paper"
    if _contains_any(text, ("engineering blog", "blog")):
        return "engineering_blog"
    if source.get("source_type") in {"markdown", "text", "pdf"}:
        return str(source["source_type"])
    return "unknown"


def _risk_flags(text: str) -> List[str]:
    flags = []
    if _contains_any(text, VENDOR_KEYWORDS):
        flags.append("vendor_claim")
    if _contains_any(text, ("no experiment", "no public testbed", "no testbed data", "without experiment")) or not _contains_any(text, EXPERIMENT_KEYWORDS):
        flags.append("no_experiment_signal")
    if _contains_any(text, MARKETING_KEYWORDS):
        flags.append("marketing_language")
    if _contains_any(text, ("no baseline", "without baseline")) or not _contains_any(text, BASELINE_KEYWORDS):
        flags.append("missing_baseline")
    has_tail_signal = _contains_any(text, ("p95", "p99", "tail", "worst-case")) and not _contains_any(text, ("no p95", "no p99", "does not provide p95", "does not provide p99"))
    if _contains_any(text, AVERAGE_ONLY_KEYWORDS) and not has_tail_signal:
        flags.append("average_only_signal")
    negated_process = _contains_any(text, ("no implementation constraints", "without implementation constraints")) or ("does not provide" in text and "implementation constraints" in text)
    if negated_process or not _contains_any(text, PROCESS_KEYWORDS):
        flags.append("process_constraint_missing")
    return flags


def _business_relevance(text: str) -> Tuple[str, List[str]]:
    found = _detect_keywords(text, BUSINESS_KEYWORDS)
    if len(found) >= 3:
        return "High", found
    if found:
        return "Medium", found
    return "Low", found


def triage_source(source: Dict[str, Any]) -> Dict[str, Any]:
    text = _lower_text(source)
    document_type = _document_type(source, text)
    source_tier, tier_reason = _source_tier(text)
    domain, domain_keywords = _domain(text)
    business_relevance, business_keywords = _business_relevance(text)
    risks = _risk_flags(text)

    credibility = {
        "A": "High",
        "B": "Medium",
        "C": "Low",
        "D": "Low",
    }.get(source_tier, "Low")

    technical_signals = _detect_keywords(text, EXPERIMENT_KEYWORDS + BASELINE_KEYWORDS + tuple(k for values in DOMAIN_KEYWORDS.values() for k in values))
    marketing_or_low_evidence = bool({"marketing_language", "no_experiment_signal"} & set(risks)) or source_tier == "D"
    if credibility == "High" and business_relevance == "High" and not marketing_or_low_evidence:
        deep_read_priority = "High"
    elif credibility in {"High", "Medium"} and (business_relevance in {"High", "Medium"} or technical_signals):
        deep_read_priority = "Medium"
    elif source_tier == "C" and business_relevance == "High" and technical_signals and "marketing_language" not in risks:
        deep_read_priority = "Medium"
    else:
        deep_read_priority = "Low"

    detected_keywords = sorted(set(domain_keywords + business_keywords + technical_signals + _detect_keywords(text, A_TIER_KEYWORDS + B_TIER_KEYWORDS + C_TIER_KEYWORDS + D_TIER_KEYWORDS)))
    reasons = [
        tier_reason,
        f"credibility={credibility}",
        f"business_relevance={business_relevance}",
        "deterministic rule-based triage only; no strong technical conclusion is made",
    ]
    if risks:
        reasons.append("risk flags: " + ", ".join(risks))

    return {
        "source_id": source.get("source_id") or source.get("id") or "unknown",
        "document_type": document_type,
        "source_tier": source_tier,
        "domain": domain,
        "credibility": credibility,
        "business_relevance": business_relevance,
        "deep_read_priority": deep_read_priority,
        "reasons": reasons,
        "detected_keywords": detected_keywords,
        "risk_flags": risks,
    }


def triage_path(path: str | Path) -> Dict[str, Any]:
    source_path = Path(path)
    if source_path.suffix.lower() == ".json":
        with source_path.open("r", encoding="utf-8") as f:
            source = json.load(f)
    else:
        source = ingest_file(source_path)
    return triage_source(source)


def triage_candidate_metadata(candidate: Dict[str, Any]) -> Dict[str, Any]:
    domains = candidate.get("domain_hints") or detect_domain_hints(candidate)
    tier = candidate.get("source_tier_hint")
    if tier in {None, "unknown"}:
        tier = detect_source_tier_hint(candidate)
    vendor = detect_vendor_or_marketing(candidate)
    weak = detect_weak_source(candidate)
    credibility = {"A": "High", "B": "Medium", "C": "Low", "D": "Low"}.get(tier, "Low")
    business_relevance = "High" if domains else "Low"
    if tier in {"A", "B"} and domains and not vendor and not weak:
        deep_read_priority = "High"
    elif tier in {"A", "B"} and domains:
        deep_read_priority = "Medium"
    else:
        deep_read_priority = "Low"
    risk_flags = []
    if vendor:
        risk_flags.append("vendor_claim")
    if weak:
        risk_flags.append("weak_source")
    if tier == "C":
        risk_flags.append("signal_only")
    if tier == "D":
        risk_flags.append("background_only")
    return {
        "source_id": candidate.get("candidate_id", "unknown"),
        "candidate_id": candidate.get("candidate_id", "unknown"),
        "document_type": candidate.get("document_type", "unknown"),
        "source_tier": tier,
        "domain": domains[0] if domains else "unknown",
        "credibility": credibility,
        "business_relevance": business_relevance,
        "deep_read_priority": deep_read_priority,
        "reasons": [
            f"metadata-only candidate from {candidate.get('source_provider')}",
            "candidate must pass CNI triage before ingestion or analysis",
            "strong conclusions are not allowed at discovery stage",
        ],
        "detected_keywords": domains + list(candidate.get("keyword_matches") or []),
        "risk_flags": risk_flags,
        "strong_conclusion_allowed": False,
    }
