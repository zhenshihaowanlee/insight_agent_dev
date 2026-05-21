from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List

from .schema_validation import validate_json


SAFE_REVIEW_RECIPIENT = "REVIEW_REQUIRED@example.invalid"
FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _default_output_dir(created_at: str) -> Path:
    safe = created_at.replace(":", "").replace("+", "Z")
    return Path(".zyw_insight") / "email_drafts" / f"{safe}-draft"


def _split_recipients(value: str | Iterable[str] | None) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = []
        for chunk in value.split(","):
            stripped = chunk.strip()
            if stripped:
                parts.append(stripped)
        return parts
    return [str(item).strip() for item in value if str(item).strip()]


def _is_placeholder_recipient(address: str) -> bool:
    return address == SAFE_REVIEW_RECIPIENT or address.endswith(".invalid")


def validate_recipient_safety(to, cc=None, bcc=None, allow_real_recipient: bool = False) -> Dict[str, Any]:
    recipients = {
        "to": _split_recipients(to) or [SAFE_REVIEW_RECIPIENT],
        "cc": _split_recipients(cc),
        "bcc": _split_recipients(bcc),
    }
    real = [address for group in recipients.values() for address in group if not _is_placeholder_recipient(address)]
    if real and not allow_real_recipient:
        raise ValueError("real recipient addresses require --allow-real-recipient; draft generation only")
    return {
        "recipients": recipients,
        "real_recipient_present": bool(real),
        "allow_real_recipient": allow_real_recipient,
        "delivery_allowed": False,
        "notes": ["recipient validation only; no delivery is performed"],
    }


def _resolve_inputs(run_dir_or_brief_path: str | Path) -> Dict[str, Any]:
    path = Path(run_dir_or_brief_path)
    if path.is_dir():
        manifest_path = path / "run_manifest.json"
        brief_md = path / "brief" / "brief.md"
        brief_json = path / "brief" / "brief.json"
    elif path.suffix.lower() == ".md":
        brief_md = path
        brief_json = path.with_suffix(".json")
        manifest_path = path.parents[1] / "run_manifest.json" if len(path.parents) > 1 else Path()
    elif path.suffix.lower() == ".json":
        brief_json = path
        brief_md = path.with_suffix(".md")
        manifest_path = path.parents[1] / "run_manifest.json" if len(path.parents) > 1 else Path()
    else:
        raise ValueError(f"unsupported email draft input: {path}")

    if not brief_md.exists():
        raise FileNotFoundError(brief_md)
    if not brief_json.exists():
        raise FileNotFoundError(brief_json)

    manifest: Dict[str, Any] = {}
    if manifest_path and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    brief = json.loads(brief_json.read_text(encoding="utf-8"))
    return {
        "run_dir": str(path if path.is_dir() else brief_md.parents[1]),
        "manifest_path": str(manifest_path) if manifest_path else "",
        "manifest": manifest,
        "brief_json_path": str(brief_json),
        "brief_markdown_path": str(brief_md),
        "brief_json": brief,
        "brief_markdown": brief_md.read_text(encoding="utf-8"),
    }


def _contains_forbidden_value(text: str) -> bool:
    return any(pattern.search(text) for pattern in FORBIDDEN_VALUE_PATTERNS)


def _assert_safe_text(text: str) -> None:
    if _contains_forbidden_value(text):
        raise ValueError("email draft source contains secret-like value")


def render_email_markdown(brief_md: str, metadata: Dict[str, Any]) -> str:
    _assert_safe_text(brief_md)
    return "\n".join(
        [
            "DRAFT ONLY — requires human approval before external delivery.",
            "Not approved for sending.",
            "Not production recommendation.",
            "This brief is for awareness / review only, not for production decision.",
            "",
            f"Generated at: {metadata.get('created_at', 'not available')}",
            f"Source run id: {metadata.get('source_run_id', 'unknown')}",
            f"Brief path: {metadata.get('source_brief_markdown', 'not available')}",
            "Human approval required: true",
            "External delivery sent: false",
            "",
            "---",
            "",
            brief_md.strip(),
            "",
        ]
    )


def write_eml_draft(email_draft: Dict[str, Any], body_markdown: str) -> str:
    message = EmailMessage()
    headers = email_draft["headers"]
    message["Subject"] = headers["subject"]
    message["To"] = ", ".join(headers["to"])
    if headers.get("cc"):
        message["Cc"] = ", ".join(headers["cc"])
    if headers.get("reply_to"):
        message["Reply-To"] = headers["reply_to"]
    message["X-ZYW-Draft-Only"] = headers["x_zyw_draft_only"]
    message.set_content(body_markdown)
    eml_path = Path(email_draft["body"]["eml_path"])
    eml_path.parent.mkdir(parents=True, exist_ok=True)
    eml_path.write_text(message.as_string(), encoding="utf-8")
    return str(eml_path)


def _approval_payload(email_draft: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "approval_id": f"approval-{email_draft['email_draft_id'].removeprefix('email-')}",
        "created_at": email_draft["created_at"],
        "source_email_draft_id": email_draft["email_draft_id"],
        "approval_required": True,
        "approved": False,
        "reviewer": None,
        "checklist": {
            "content_quality_reviewed": False,
            "no_strong_claim_without_evidence": False,
            "vendor_claims_marked": False,
            "budget_context_reviewed": False,
            "draft_only_confirmed": False,
            "no_api_key_or_secret": False,
            "no_external_delivery": False,
            "recipients_reviewed": False,
            "attachments_reviewed": False,
        },
        "approval_decision": "pending",
        "comments": "",
    }


def write_approval_checklist(email_draft: Dict[str, Any]) -> str:
    approval = _approval_payload(email_draft)
    validate_json(approval, "human_approval")
    path = Path(email_draft["approval"]["approval_checklist_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Human Approval Checklist",
        "",
        f"Approval ID: {approval['approval_id']}",
        f"Email draft ID: {approval['source_email_draft_id']}",
        "Approval decision: pending",
        "Approved: false",
        "",
        "## Checklist",
    ]
    labels = {
        "content_quality_reviewed": "content quality reviewed",
        "no_strong_claim_without_evidence": "no strong claim without evidence",
        "vendor_claims_marked": "vendor claims marked",
        "budget_context_reviewed": "budget context reviewed",
        "draft_only_confirmed": "draft-only status confirmed",
        "no_api_key_or_secret": "no credential-like value",
        "no_external_delivery": "no external delivery",
        "recipients_reviewed": "recipients reviewed",
        "attachments_reviewed": "attachments reviewed",
    }
    for key in approval["checklist"]:
        lines.append(f"- [ ] {labels.get(key, key)}")
    lines.extend(["", "## Comments", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def redact_email_draft_for_manifest(email_draft: Dict[str, Any]) -> Dict[str, Any]:
    headers = dict(email_draft.get("headers") or {})
    headers["bcc"] = ["redacted"] if headers.get("bcc") else []
    return {
        "email_draft_id": email_draft["email_draft_id"],
        "created_at": email_draft["created_at"],
        "source_run_id": email_draft["source_run_id"],
        "source_brief_json": email_draft["source_brief_json"],
        "source_brief_markdown": email_draft["source_brief_markdown"],
        "draft_only": True,
        "requires_human_approval": True,
        "external_delivery_sent": False,
        "transport_summary": {"mode": "local_artifact_only", "external_delivery": False},
        "headers": headers,
        "body": email_draft["body"],
        "attachments": email_draft["attachments"],
        "approval_summary": {"required": True, "approved": False, "decision": "pending"},
        "redaction_summary": {"credential_like_values_found": False, "raw_source_body_included": False},
        "runtime_boundary": {
            "codex_runtime_used": False,
            "real_openrouter_call_executed": False,
            "network_request_sent": False,
            "email_sent": False,
            "external_delivery_sent": False,
        },
        "validation": {"schema_valid": True, "local_artifact_only": True},
        "notes": email_draft.get("notes", []),
    }


def build_email_draft(
    run_dir_or_brief_path,
    output_dir=None,
    to=None,
    cc=None,
    bcc=None,
    subject=None,
    allow_real_recipient: bool = False,
    include_attachments: bool = True,
) -> Dict[str, Any]:
    inputs = _resolve_inputs(run_dir_or_brief_path)
    _assert_safe_text(inputs["brief_markdown"])
    created_at = _now()
    draft_id = f"email-{_hash(created_at + inputs['brief_markdown_path'])[:16]}"
    out_dir = Path(output_dir) if output_dir else _default_output_dir(created_at)
    out_dir.mkdir(parents=True, exist_ok=True)

    recipient_safety = validate_recipient_safety(to, cc, bcc, allow_real_recipient=allow_real_recipient)
    recipients = recipient_safety["recipients"]
    source_run_id = str((inputs["manifest"] or {}).get("run_id") or inputs["brief_json"].get("brief_id") or "unknown")
    email_subject = subject or f"[DRAFT][ZYW Insight][Review Required] 72h Technical Insight Brief - {source_run_id}"
    if not email_subject.startswith("[DRAFT][ZYW Insight][Review Required]"):
        email_subject = "[DRAFT][ZYW Insight][Review Required] " + email_subject.removeprefix("[DRAFT][ZYW Insight]").strip()

    body_md_path = out_dir / "email_draft.md"
    eml_path = out_dir / "email_draft.eml"
    preview_path = out_dir / "email_draft_preview.txt"
    approval_path = out_dir / "approval_checklist.md"
    manifest_path = out_dir / "email_draft_manifest.json"

    attachments = []
    if include_attachments:
        for attachment_path, attachment_type in (
            (inputs["brief_markdown_path"], "brief_markdown"),
            (inputs["brief_json_path"], "brief_json"),
            (inputs["manifest_path"], "run_manifest"),
            (str(approval_path), "approval_checklist"),
        ):
            if attachment_path:
                attachments.append({"path": attachment_path, "attachment_type": attachment_type, "included": True, "redacted": attachment_type == "run_manifest"})

    email_draft = {
        "email_draft_id": draft_id,
        "created_at": created_at,
        "source_run_id": source_run_id,
        "source_brief_json": inputs["brief_json_path"],
        "source_brief_markdown": inputs["brief_markdown_path"],
        "draft_only": True,
        "requires_human_approval": True,
        "external_delivery_sent": False,
        "transport": {
            "mode": "local_artifact_only",
            "smtp_used": False,
            "sendmail_used": False,
            "webhook_used": False,
            "network_used": False,
        },
        "headers": {
            "subject": email_subject,
            "to": recipients["to"],
            "cc": recipients["cc"],
            "bcc": recipients["bcc"],
            "reply_to": None,
            "x_zyw_draft_only": "true",
        },
        "body": {
            "markdown_path": str(body_md_path),
            "eml_path": str(eml_path),
            "preview_path": str(preview_path),
        },
        "attachments": attachments,
        "approval": {
            "approval_required": True,
            "approved": False,
            "approved_by": None,
            "approved_at": None,
            "approval_checklist_path": str(approval_path),
        },
        "redaction": {
            "body_contains_raw_source_body": False,
            "contains_api_key": False,
            "contains_token": False,
            "contains_secret": False,
            "contains_authorization": False,
            "contains_env": False,
        },
        "runtime_boundary": {
            "codex_runtime_used": False,
            "real_openrouter_call_executed": False,
            "network_request_sent": False,
            "email_sent": False,
            "webhook_sent": False,
        },
        "validation": {
            "recipient_safety": recipient_safety,
            "schema_valid": True,
            "secret_scan_passed": True,
        },
        "notes": [
            "Local email draft artifact only; no delivery path was used.",
            "Human approval checklist is pending by default.",
        ],
    }

    body_markdown = render_email_markdown(inputs["brief_markdown"], email_draft)
    body_md_path.write_text(body_markdown, encoding="utf-8")
    preview_path.write_text(body_markdown[:4000], encoding="utf-8")
    write_approval_checklist(email_draft)
    write_eml_draft(email_draft, body_markdown)
    validate_json(email_draft, "email_draft")
    manifest_path.write_text(json.dumps(redact_email_draft_for_manifest(email_draft), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return email_draft
