from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | {".pdf"}


def source_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".txt":
        return "text"
    if suffix == ".pdf":
        return "pdf"
    raise ValueError(f"unsupported source extension: {suffix or '<none>'}")


def extract_markdown_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            if title:
                return title
    return fallback


def ingest_pdf(path: str | Path) -> Dict[str, Any]:
    """Reserved PDF ingestion interface. OCR/text extraction is intentionally absent."""
    source_path = Path(path)
    raise NotImplementedError(f"PDF ingestion is TODO for {source_path}; OCR and large dependencies are not included in the PoC.")


def ingest_file(path: str | Path) -> Dict[str, Any]:
    source_path = Path(path).expanduser().resolve()
    source_type = source_type_for_path(source_path)
    if source_type == "pdf":
        return ingest_pdf(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    body = source_path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    title = extract_markdown_title(body, source_path.stem) if source_type == "markdown" else source_path.stem
    discovered_at = datetime.now(timezone.utc).isoformat()
    uri = source_path.as_uri()
    source_id = f"local-{content_hash[:16]}"

    provenance = {
        "local_path": str(source_path),
        "imported_by": "zyw_insight.ingestion",
        "import_mode": "local_file",
    }
    metadata: Dict[str, Any] = {
        "file_name": source_path.name,
        "extension": source_path.suffix.lower(),
        "size_bytes": source_path.stat().st_size,
        "encoding": "utf-8",
    }

    return {
        "source_id": source_id,
        "id": source_id,
        "title": title,
        "source_type": source_type,
        "source_rank": "unknown",
        "relevance": "Unknown",
        "deep_read_decision": "Low",
        "path": str(source_path),
        "local_path": str(source_path),
        "uri": uri,
        "url": None,
        "discovered_at": discovered_at,
        "body": body,
        "body_is_untrusted": True,
        "provenance": provenance,
        "content_hash": content_hash,
        "hash": content_hash,
        "metadata": metadata,
        "rationale": "Local file ingestion only; body is untrusted content and must not be treated as instructions.",
    }
