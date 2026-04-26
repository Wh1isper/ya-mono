#!/bin/bash
# Verify canonical agent-builder skill source is synchronized into the YAACLI bundled skills directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
SOURCE_DIR = ROOT / "skills/agent-builder"
TARGET_DIR = ROOT / "packages/yaacli/yaacli/skills/building-agents"
IGNORED_TOP_LEVEL = {"examples"}


def collect_files(root: Path) -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    if not root.exists():
        raise SystemExit(f"Missing directory: {root}")
    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root)
        if relative_path.parts and relative_path.parts[0] in IGNORED_TOP_LEVEL:
            continue
        if path.is_file():
            files[relative_path] = path.read_bytes()
    return files


source_files = collect_files(SOURCE_DIR)
target_files = collect_files(TARGET_DIR)
source_paths = set(source_files)
target_paths = set(target_files)
missing = sorted(source_paths - target_paths)
extra = sorted(target_paths - source_paths)
changed = sorted(path for path in source_paths & target_paths if source_files[path] != target_files[path])
if missing or extra or changed:
    print(f"Skill bundle is out of sync: {SOURCE_DIR.relative_to(ROOT)} -> {TARGET_DIR.relative_to(ROOT)}")
    for path in missing:
        print(f"Missing in target: {path}")
    for path in extra:
        print(f"Extra in target: {path}")
    for path in changed:
        print(f"Changed: {path}")
    print("Run ./scripts/sync-skills.sh")
    raise SystemExit(1)

for forbidden_dir in [ROOT / "packages/yaacli/yaacli/skills/ya-claw-deploy"]:
    if forbidden_dir.exists():
        print(f"Unexpected bundled skill directory: {forbidden_dir.relative_to(ROOT)}")
        raise SystemExit(1)

print("Skill bundles are synchronized.")
PY
