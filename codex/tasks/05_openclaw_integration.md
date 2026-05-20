# Task 05 — OpenClaw integration

Goal: make local CLI usable from OpenClaw skills.

Requirements:

- Document exact commands in `openclaw/OPENCLAW_SETUP.md`.
- Add a `scripts/install_skills.sh` helper.
- Do not overwrite existing `~/.openclaw/openclaw.json` automatically.
- Add dry-run mode.

Acceptance:

- Running script with dry-run prints planned copies.
- No global config changes without explicit user action.
