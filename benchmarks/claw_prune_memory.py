"""Fresh-process RSS probe for Claw retention selection; no live data or deletion.

uv run --all-packages python benchmarks/claw_prune_memory.py
uv run --all-packages python benchmarks/claw_prune_memory.py --baseline-ref 1a0b1a7e

A separate process seeds synthetic SQLite rows before the measured process starts.
Only candidate selection runs, never prune_once or filesystem/container cleanup.
Use trusted local revisions only: --baseline-ref executes the historical module.
"""

# ruff: noqa: S101, S603
from __future__ import annotations

import argparse
import asyncio
import gc
import json
import resource
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from claw_memory import historical_module


def rss() -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    raise RuntimeError("Linux /proc RSS is required")


def seed(path: Path, rows: int, payload_chars: int) -> None:
    from sqlalchemy import create_engine, insert
    from ya_claw.orm.base import Base
    from ya_claw.orm.tables import RunRecord, SessionRecord

    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(SessionRecord), {"id": "session", "session_metadata": {}})
        for index in range(rows):
            payload = f"{index:08d}" + "x" * max(0, payload_chars - 8)
            connection.execute(
                insert(RunRecord),
                {
                    "id": f"run-{index:08d}",
                    "session_id": "session",
                    "sequence_no": index,
                    "status": "completed",
                    "input_parts": [{"type": "text", "text": payload}],
                    "run_metadata": {"payload": payload},
                    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                },
            )
    engine.dispose()


async def measure(path: Path, ref: str | None, rows: int) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from ya_claw.config import ClawSettings
    from ya_claw.controller.session_prune import SessionPruneController

    if ref:
        SessionPruneController = historical_module(
            ref, "packages/ya-claw/ya_claw/controller/session_prune.py", "baseline_prune"
        ).SessionPruneController
    settings = ClawSettings(
        _env_file=None,
        session_prune_run_keep_recent=10,
        session_prune_run_older_than_days=0,
        session_prune_batch_size=100,
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    gc.collect()
    before = rss()
    started = time.perf_counter()
    async with factory() as session:
        ids = await SessionPruneController()._select_prunable_run_ids(session, settings)
        assert ids == [f"run-{index:08d}" for index in range(min(100, max(0, rows - 10)))]
    elapsed = time.perf_counter() - started
    after = rss()
    gc.collect()
    after_gc = rss()
    await engine.dispose()
    print(
        json.dumps({
            "baseline_ref": ref,
            "rows": rows,
            "seconds": round(elapsed, 4),
            "before_mib": before,
            "peak_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "after_mib": after,
            "after_gc_mib": after_gc,
            "after_dispose_mib": rss(),
            "selected": len(ids),
        }),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref")
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--payload-chars", type=int, default=65536)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--measure", type=Path)
    args = parser.parse_args()
    if args.seed:
        seed(args.seed, args.rows, args.payload_chars)
    elif args.measure:
        asyncio.run(measure(args.measure, args.baseline_ref, args.rows))
    else:
        with TemporaryDirectory(prefix="claw-prune-memory-") as directory:
            path = Path(directory) / "synthetic.sqlite3"
            command = [sys.executable, __file__, "--rows", str(args.rows)]
            subprocess.run([*command, "--seed", str(path), "--payload-chars", str(args.payload_chars)], check=True)
            if args.baseline_ref:
                command.extend(["--baseline-ref", args.baseline_ref])
            subprocess.run([*command, "--measure", str(path)], check=True)
