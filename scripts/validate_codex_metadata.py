#!/usr/bin/env python3
"""Validate Codex/OpenClaw metadata files that are parsed before a session starts."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _frontmatter_fields(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    block = text[4:end].strip()
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def validate_skills(root: Path) -> list[str]:
    errors: list[str] = []
    for base in [root / ".agents" / "skills", root / "skills", root / "openclaw" / "harness" / "skills"]:
        if not base.exists():
            continue
        for skill_md in sorted(base.glob("*/SKILL.md")):
            fields = _frontmatter_fields(skill_md.read_text())
            if not fields.get("name"):
                errors.append(f"{skill_md}: missing frontmatter name")
            if not fields.get("description"):
                errors.append(f"{skill_md}: missing frontmatter description")
    return errors


def validate_agents(root: Path) -> list[str]:
    errors: list[str] = []
    agent_dir = root / ".codex" / "agents"
    if not agent_dir.exists():
        return errors
    for toml_path in sorted(agent_dir.glob("*.toml")):
        try:
            data = tomllib.loads(toml_path.read_text())
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{toml_path}: TOML parse error: {exc}")
            continue
        for key in ["name", "description", "developer_instructions"]:
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{toml_path}: missing non-empty {key}")
    return errors


def main() -> int:
    root = _repo_root()
    errors = validate_skills(root) + validate_agents(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("codex metadata: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
