#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_SRC="$ROOT_DIR/openclaw/harness/workspace"
SKILLS_SRC="$ROOT_DIR/openclaw/harness/skills"
CRON_SRC="$ROOT_DIR/openclaw/harness/cron"
CONFIG_SRC="$ROOT_DIR/openclaw/harness/config/openclaw.runtime.openrouter-only.json5"

OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
WORKSPACE_DST="${OPENCLAW_WORKSPACE_DST:-$OPENCLAW_DIR/workspace/zyw-insight}"
SKILLS_DST="${OPENCLAW_SKILLS_DST:-$OPENCLAW_DIR/skills}"
CRON_DST="${OPENCLAW_CRON_DST:-$OPENCLAW_DIR/cron}"
CONFIG_DST="${OPENCLAW_CONFIG_DST:-$OPENCLAW_DIR/openclaw.zyw-insight.openrouter-only.json5}"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %s\n' "$*"
  else
    eval "$@"
  fi
}

printf 'Source workspace: %s\n' "$WORKSPACE_SRC"
printf 'Target workspace: %s\n' "$WORKSPACE_DST"
printf 'Source skills:    %s\n' "$SKILLS_SRC"
printf 'Target skills:    %s\n' "$SKILLS_DST"
printf 'Source cron:      %s\n' "$CRON_SRC"
printf 'Target cron:      %s\n' "$CRON_DST"
printf 'Source config:    %s\n' "$CONFIG_SRC"
printf 'Target config:    %s\n' "$CONFIG_DST"

if [[ "$DRY_RUN" != "1" ]]; then
  mkdir -p "$OPENCLAW_DIR"
  BACKUP="$OPENCLAW_DIR.backup.$(date +%Y%m%d-%H%M%S)"
  if [[ -d "$OPENCLAW_DIR" ]]; then
    cp -a "$OPENCLAW_DIR" "$BACKUP"
    printf 'Backed up %s to %s\n' "$OPENCLAW_DIR" "$BACKUP"
  fi
fi

run "mkdir -p '$WORKSPACE_DST' '$SKILLS_DST' '$CRON_DST'"
run "rsync -a --delete '$WORKSPACE_SRC/' '$WORKSPACE_DST/'"
run "rsync -a '$SKILLS_SRC/' '$SKILLS_DST/'"
run "rsync -a '$CRON_SRC/' '$CRON_DST/'"
run "cp '$CONFIG_SRC' '$CONFIG_DST'"

printf '\nNext steps:\n'
printf '1. Fill explicit OpenRouter model IDs in %s\n' "$CONFIG_DST"
printf '2. Set OPENROUTER_API_KEY in your runtime environment, not in workspace memory files.\n'
printf '3. Run: openclaw doctor\n'
