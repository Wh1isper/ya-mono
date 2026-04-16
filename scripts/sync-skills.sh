#!/bin/bash
# Sync canonical skill sources into the CLI skill bundle.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

SOURCE_DIR="skills/agent-builder"
TARGET_DIR="packages/yaacli/yaacli/skills/building-agents"

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cp -R "$SOURCE_DIR"/. "$TARGET_DIR"/
mkdir -p "$TARGET_DIR/examples"
cp -R examples/* "$TARGET_DIR/examples/"
cp examples/.env.example "$TARGET_DIR/examples/"

echo "Synced $SOURCE_DIR and repository examples into $TARGET_DIR"
