from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from ya_claw.config import ClawSettings
from ya_claw.controller.models import RunCreateRequest, SessionCreateRequest
from ya_claw.controller.run import RunController
from ya_claw.controller.session import SessionController
from ya_claw.db.engine import create_engine, create_session_factory
from ya_claw.orm.base import Base
from ya_claw.orm.tables import RunRecord


@pytest.fixture
async def db_engine(tmp_path: Path) -> AsyncEngine:
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'controller.sqlite3').resolve()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    session_factory = create_session_factory(db_engine)
    async with session_factory() as session:
        yield session


@pytest.fixture
def settings(tmp_path: Path) -> ClawSettings:
    data_dir = tmp_path / "runtime-data"
    workspace_root = tmp_path / "workspace"
    data_dir.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)
    return ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=data_dir,
        workspace_root=workspace_root,
    )


async def test_session_controller_lists_run_info(db_session: AsyncSession, settings: ClawSettings) -> None:
    controller = SessionController()
    session_summary = await controller.create(
        db_session,
        settings,
        SessionCreateRequest(profile_name="general", project_id="repo-a", metadata={"source": "api"}),
    )

    earlier = datetime.now(UTC) - timedelta(minutes=5)
    later = datetime.now(UTC)
    db_session.add_all([
        RunRecord(
            id="run-queued",
            session_id=session_summary.id,
            status="queued",
            trigger_type="api",
            project_id="repo-a",
            created_at=later,
        ),
        RunRecord(
            id="run-completed",
            session_id=session_summary.id,
            status="completed",
            trigger_type="api",
            project_id="repo-a",
            created_at=earlier,
            finished_at=earlier + timedelta(seconds=5),
        ),
    ])
    await db_session.commit()

    sessions = await controller.list(db_session)

    assert len(sessions) == 1
    assert sessions[0].id == session_summary.id
    assert sessions[0].run_count == 2
    assert sessions[0].active_run_ids == ["run-queued"]
    assert sessions[0].latest_run is not None
    assert sessions[0].latest_run.id == "run-queued"

    detail = await controller.get(db_session, session_summary.id)
    assert [run.id for run in detail.recent_runs] == ["run-queued", "run-completed"]


async def test_session_controller_reads_committed_blob(db_session: AsyncSession, settings: ClawSettings) -> None:
    controller = SessionController()
    session_summary = await controller.create(db_session, settings, SessionCreateRequest())
    session_dir = settings.session_store_dir / session_summary.id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "message.json").write_text(
        json.dumps({"messages": [{"role": "assistant", "content": "done"}]}), encoding="utf-8"
    )

    payload = await controller.read_blob(db_session, settings, session_summary.id, "message.json")

    assert payload == {"messages": [{"role": "assistant", "content": "done"}]}


async def test_run_controller_create_auto_creates_session(db_session: AsyncSession, settings: ClawSettings) -> None:
    controller = RunController()

    run = await controller.create(
        db_session,
        settings,
        RunCreateRequest(
            session_id=None,
            profile_name="general",
            project_id="repo-b",
            input_text="hello",
            metadata={"source": "tool"},
        ),
    )

    assert run.status == "queued"
    assert run.session_id
    assert run.profile_name == "general"
    assert run.project_id == "repo-b"
    assert run.metadata == {"source": "tool"}
    assert (settings.session_store_dir / run.session_id).exists()
