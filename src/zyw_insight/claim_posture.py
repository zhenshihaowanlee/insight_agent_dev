from __future__ import annotations

import re
from typing import Any, Dict, List


STRONG_CLAIMS = (
    "ready for production",
    "production-ready",
    "deploy immediately",
    "immediate rollout",
    "validated for production",
    "proven in production",
    "recommend production deployment",
    "strong investment decision",
    "S action without validation",
    "A action without evidence boundary",
)
NEGATIVE_GUARDRAILS = (
    "not ready for production",
    "do not recommend production deployment",
    "not validated for production",
    "requires validation before production use",
    "production use requires independent validation",
    "do not escalate to production",
    "no production recommendation",
    "not production recommendation",
    "not for production decision",
    "no production or major investment decision",
)
CONDITIONAL_CLAIMS = (
    "ready for PoC only after",
    "suitable for watchlist",
    "suitable for guarded PoC scoping",
    "management awareness only",
    "not management decision ready",
    "requires p95/p99 baseline validation",
    "requires validation",
    "guarded validation",
)
EVIDENCE_GAPS = (
    "insufficient evidence",
    "evidence gap",
    "missing baseline",
    "no experiment",
    "not available",
    "weak evidence",
)


def _matches(text: str, terms: tuple[str, ...]) -> List[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def is_guarded_production_phrase(text: str) -> bool:
    return bool(_matches(text, NEGATIVE_GUARDRAILS))


def classify_claim_posture(text: str) -> Dict[str, Any]:
    strong = _matches(text, STRONG_CLAIMS)
    negative = _matches(text, NEGATIVE_GUARDRAILS)
    conditional = _matches(text, CONDITIONAL_CLAIMS)
    evidence_gap = _matches(text, EVIDENCE_GAPS)

    if negative:
        return {
            "posture": "negative_guardrail",
            "matched_terms": negative,
            "negated": True,
            "requires_revision": False,
            "reason": "production-like phrase is explicitly negated or guarded",
        }
    if strong:
        return {
            "posture": "strong_claim",
            "matched_terms": strong,
            "negated": False,
            "requires_revision": True,
            "reason": "strong production or investment posture detected",
        }
    if conditional:
        has_boundary = bool(evidence_gap or re.search(r"\b(before|after|requires|only|guarded|scoping|watchlist)\b", text, flags=re.IGNORECASE))
        return {
            "posture": "conditional_claim",
            "matched_terms": conditional,
            "negated": False,
            "requires_revision": not has_boundary,
            "reason": "conditional claim has evidence boundary" if has_boundary else "conditional claim lacks evidence boundary",
        }
    if evidence_gap:
        return {
            "posture": "evidence_gap",
            "matched_terms": evidence_gap,
            "negated": False,
            "requires_revision": False,
            "reason": "explicit evidence gap or weak-evidence marker",
        }
    return {
        "posture": "neutral",
        "matched_terms": [],
        "negated": False,
        "requires_revision": False,
        "reason": "no strong claim posture detected",
    }


def detect_strong_claims(text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        posture = classify_claim_posture(line)
        if posture["posture"] == "strong_claim" and posture["requires_revision"]:
            findings.append({"line": line_number, "text": line.strip(), **posture})
    return findings


def rewrite_strong_claim_to_guarded(text: str) -> str:
    rewritten = text
    replacements = {
        "ready for production": "not ready for production without independent validation",
        "production-ready": "not production ready without independent validation",
        "deploy immediately": "do not deploy; use only for guarded validation planning",
        "immediate rollout": "no rollout; use only for guarded validation planning",
        "validated for production": "not validated for production use",
        "proven in production": "not proven for production use",
        "recommend production deployment": "do not recommend production deployment",
        "strong investment decision": "major investment decision is not supported",
        "S action without validation": "S action is not supported without validation",
        "A action without evidence boundary": "A action is not supported without evidence boundary",
    }
    for source, target in replacements.items():
        rewritten = re.sub(re.escape(source), target, rewritten, flags=re.IGNORECASE)
    return rewritten
