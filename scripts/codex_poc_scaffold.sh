#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
cat codex/prompts/poc_scaffold.prompt.md | codex exec --sandbox workspace-write --ask-for-approval on-request -
