#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
WORKSPACE="${OPENCLAW_ZYW_WORKSPACE:-$HOME/.openclaw/workspace-zyw-insight}"

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

printf 'Target workspace: %s\n' "$WORKSPACE"
printf 'Skills source: %s\n' "$(pwd)/skills"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry run only. No files copied."
  exit 0
fi

mkdir -p "$WORKSPACE"
cp -R skills "$WORKSPACE/"
cp AGENTS.md "$WORKSPACE/AGENTS.md"
echo "Installed skills into $WORKSPACE"
