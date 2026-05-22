from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .fulltext_eligibility import load_fulltext_policy
from .pdf_text_extract import extract_pdf_text
from .schema_validation import validate_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _artifact_id(candidate_id: str, created_at: str) -> str:
    return "fulltext-" + hashlib.sha256(f"{candidate_id}:{created_at}".encode("utf-8")).hexdigest()[:16]


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_and_extract_fulltext(
    candidate: Dict[str, Any],
    eligibility: Dict[str, Any],
    output_dir: str | Path,
    allow_network: bool = False,
    dry_run: bool = True,
    policy: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    policy = policy or load_fulltext_policy()
    created_at = _now()
    candidate_id = str(candidate.get("candidate_id") or eligibility.get("candidate_id") or "unknown")
    artifact_id = _artifact_id(candidate_id, created_at)
    run_dir = Path(output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = run_dir / f"{artifact_id}.pdf"
    text_path = run_dir / f"{artifact_id}.txt"

    text = ""
    page_count = 0
    section_hints: Dict[str, bool] = {
        "abstract": False,
        "method_or_design": False,
        "evaluation_or_experiments": False,
        "limitations_or_discussion": False,
        "references": False,
    }
    status = "planned"
    error = None
    pdf_written = False

    if not eligibility.get("fetch_allowed"):
        status = "rejected"
        error = {"status": "eligibility_rejected", "message": eligibility.get("eligibility_reason")}
    elif dry_run or not allow_network:
        status = "dry_run_planned"
    else:
        try:
            req = urllib.request.Request(
                str(eligibility["pdf_url"]),
                headers={"User-Agent": str(policy["user_agent"]), "Accept": "application/pdf"},
            )
            with urllib.request.urlopen(req, timeout=int(policy["timeout_seconds"])) as resp:
                chunks = []
                total = 0
                limit = int(eligibility["max_pdf_bytes"])
                while True:
                    chunk = resp.read(min(65536, limit - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("PDF exceeds max_pdf_bytes")
                    chunks.append(chunk)
            pdf_path.write_bytes(b"".join(chunks))
            pdf_written = True
            extracted = extract_pdf_text(pdf_path, int(eligibility["max_pages"]), int(eligibility["max_extracted_chars"]))
            text = extracted["text"]
            page_count = int(extracted["page_count"])
            section_hints = extracted["section_hints"]
            text_path.write_text(text, encoding="utf-8")
            status = "extracted"
        except Exception as exc:
            status = "error"
            error = {"status": type(exc).__name__, "message": str(exc)[:300]}

    artifact = {
        "artifact_id": artifact_id,
        "candidate_id": candidate_id,
        "created_at": created_at,
        "status": status,
        "pdf_path": str(pdf_path) if pdf_written else None,
        "extracted_text_path": str(text_path) if text else None,
        "extracted_text_sha256": _sha_text(text) if text else None,
        "extracted_char_count": len(text),
        "page_count": page_count,
        "section_hints": section_hints,
        "extraction_quality": "full_paper_section_sufficient" if section_hints.get("abstract") and section_hints.get("method_or_design") and section_hints.get("evaluation_or_experiments") else "partial_or_unverified",
        "source_url": eligibility.get("source_url"),
        "pdf_url": eligibility.get("pdf_url"),
        "planned_pdf_url": eligibility.get("pdf_url") if dry_run or not allow_network else None,
        "open_access": True,
        "paywall_bypassed": False,
        "body_is_untrusted": True,
        "error": error,
        "runtime_boundary": {
            "open_access_only": True,
            "fetch_allowed_by_eligibility": bool(eligibility.get("fetch_allowed")),
            "network_request_sent": bool(pdf_written),
            "max_pdf_bytes_enforced": True,
            "max_pages_enforced": True,
            "max_extracted_chars_enforced": True,
            "ocr_used": False,
            "paywall_bypassed": False,
            "credentials_used": False,
            "body_logged_to_ledger": False,
            "codex_runtime_used": False,
        },
    }
    validate_json(artifact, "fulltext_artifact")
    _write_json(run_dir / "fulltext_artifact.json", artifact)
    return artifact
