from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "source_discovery.json"


PROVIDER_ALLOWLIST = ("arxiv", "openalex", "crossref", "semantic_scholar", "ietf")
METADATA_ONLY_PROVIDERS = set(PROVIDER_ALLOWLIST)


def load_source_discovery_config() -> Dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def provider_endpoints(config: Dict[str, Any] | None = None) -> Dict[str, str]:
    return (config or load_source_discovery_config())["provider_endpoints"]


def query_profiles(config: Dict[str, Any] | None = None) -> Dict[str, str]:
    return (config or load_source_discovery_config())["query_profiles"]


def domain_keywords(config: Dict[str, Any] | None = None) -> Dict[str, list[str]]:
    return (config or load_source_discovery_config())["domain_keywords"]


def source_tier_rules(config: Dict[str, Any] | None = None) -> Dict[str, list[str]]:
    return (config or load_source_discovery_config())["source_tier_rules"]


def venue_keywords(config: Dict[str, Any] | None = None) -> list[str]:
    return list((config or load_source_discovery_config())["venue_keywords"])


def rate_limit(config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return (config or load_source_discovery_config())["rate_limit"]


def user_agent(config: Dict[str, Any] | None = None) -> str:
    return str((config or load_source_discovery_config())["user_agent"])


FORBIDDEN_SOURCE_PATTERNS = (
    "paywall",
    "download pdf",
    "fulltext",
    "full text",
    "sci-hub",
)
