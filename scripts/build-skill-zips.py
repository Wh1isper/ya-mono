#!/usr/bin/env python3
"""Build release skill zip archives from canonical skill sources."""

from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"

SKILL_PACKAGES = [
    (ROOT / "skills/agent-builder", "SKILL.zip", Path("ya-agent-sdk")),
    (ROOT / "skills/ya-claw-deploy", "YA_CLAW_DEPLOY_SKILL.zip", Path("ya-claw-deploy")),
]


def write_zip(source_dir: Path, output_path: Path, archive_root: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                arcname = archive_root / path.relative_to(source_dir)
                zf.write(path, arcname)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Build archives in a temporary directory for validation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="ya-mono-skill-zips-") as tmp_dir:
            output_dir = Path(tmp_dir)
            for source_dir, output_name, archive_root in SKILL_PACKAGES:
                output_path = output_dir / output_name
                write_zip(source_dir, output_path, archive_root)
                print(f"Validated {output_name} from {source_dir.relative_to(ROOT)}")
        return

    for source_dir, output_name, archive_root in SKILL_PACKAGES:
        output_path = DIST_DIR / output_name
        write_zip(source_dir, output_path, archive_root)
        print(f"Built {output_path.relative_to(ROOT)} from {source_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
