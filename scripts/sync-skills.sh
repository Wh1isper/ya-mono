#!/bin/bash
# Sync canonical skill sources into the CLI skill bundle.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

sync_skill() {
  local source_dir="$1"
  local target_dir="$2"

  rm -rf "$target_dir"
  mkdir -p "$target_dir"
  cp -R "$source_dir"/. "$target_dir"/

  echo "Synced $source_dir into $target_dir"
}

sync_skill "skills/agent-builder" "packages/yaacli/yaacli/skills/building-agents"
mkdir -p "packages/yaacli/yaacli/skills/building-agents/examples"
cp -R examples/* "packages/yaacli/yaacli/skills/building-agents/examples/"
cp examples/.env.example "packages/yaacli/yaacli/skills/building-agents/examples/"
echo "Synced repository examples into packages/yaacli/yaacli/skills/building-agents/examples"
