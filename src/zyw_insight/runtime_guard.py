"""Runtime boundary checks for OpenClaw configs.

The guard checks the OpenClaw runtime config template. It intentionally focuses on
config files, not documentation, because runtime docs may mention forbidden tools
as negative examples.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


FORBIDDEN_PATTERNS = [
    r"openai-codex",
    r"@openai/codex",
    r"\bcodex\b",
    r"chatgpt/codex",
    r"codex\.openai",
]

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",
    r"OPENROUTER_API_KEY\s*[:=]\s*['\"][^'\"]+['\"]",
    r"OPENAI_API_KEY\s*[:=]\s*['\"][^'\"]+['\"]",
]


@dataclass(frozen=True)
class RuntimeGuardResult:
    ok: bool
    path: str
    failures: list[str]


def check_runtime_config(path: str | Path) -> RuntimeGuardResult:
    p = Path(path).expanduser()
    failures: list[str] = []
    if not p.exists():
        return RuntimeGuardResult(False, str(p), ["config file does not exist"])
    text = p.read_text(encoding="utf-8")
    lower = text.lower()

    if "openrouter/" not in lower:
        failures.append("no openrouter/ model reference found")

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            failures.append(f"forbidden runtime pattern found: {pattern}")

    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            failures.append(f"possible secret found: {pattern}")

    if "deliver: true" in lower:
        failures.append("deliver: true found; early runtime should be draft-only")

    return RuntimeGuardResult(not failures, str(p), failures)
