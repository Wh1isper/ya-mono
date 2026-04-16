#!/bin/bash
# Sync shared docs and SDK skill assets into the CLI skill bundle.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

SKILL_DIR="packages/yaacli/yaacli/skills/building-agents"
SDK_DIR="packages/ya-agent-sdk"

rm -rf "$SKILL_DIR"
mkdir -p "$SKILL_DIR/docs" "$SKILL_DIR/examples"
cp -r docs/* "$SKILL_DIR/docs/"
cp -r examples/* "$SKILL_DIR/examples/"
cp examples/.env.example "$SKILL_DIR/examples/"
cp "$SDK_DIR/README.md" "$SKILL_DIR/"
cp "$SDK_DIR/SKILL.md" "$SKILL_DIR/"

echo "Synced docs, examples, SDK README, SDK SKILL.md, and .env.example to $SKILL_DIR"
