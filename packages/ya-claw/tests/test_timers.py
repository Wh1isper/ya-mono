from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from ya_claw.app import create_app
from ya_claw.config import ClawSettings, get_settings
from ya_claw.controller.heartbeat import HeartbeatController
from ya_claw.controller.schedule import ScheduleController, ScheduleCreateRequest, compute_next_fire_at
from ya_claw.db.engine import create_engine, create_session_factory
from ya_claw.execution.dispatcher import RunDispatcher
from ya_claw.execution.heartbeat import HeartbeatDispatcher
from ya_claw.execution.schedule import ScheduleDispatcher
from ya_claw.orm.base import Base
from ya_claw.orm.tables import HeartbeatFireRecord, RunRecord, ScheduleFireRecord, ScheduleRecord
from ya_claw.runtime_state import InMemoryRuntimeState


class RecordingSupervisor:
    def __init__(self) -> None:
        self.submitted_run_ids: list[str] = []

    def submit_run(self, run_id: str) -> bool:
        self.submitted_run_ids.append(run_id)
        return True


@pytest.fixture(autouse=True)
def clear_claw_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for env_name in (
        "YA_CLAW_API_TOKEN",
        "YA_CLAW_DATABASE_URL",
        "YA_CLAW_DATA_DIR",
        "YA_CLAW_WEB_DIST_DIR",
        "YA_CLAW_WORKSPACE_DIR",
        "YA_CLAW_PROFILE_SEED_FILE",
        "YA_CLAW_AUTO_SEED_PROFILES",
        "YA_CLAW_SCHEDULE_DISPATCH_ENABLED",
        "YA_CLAW_HEARTBEAT_ENABLED",
        "YA_CLAW_HEARTBEAT_INTERVAL_SECONDS",
        "YA_CLAW_HEARTBEAT_PROFILE",
    ):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setenv("YA_CLAW_API_TOKEN", "test-token")
    monkeypatch.setenv("YA_CLAW_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("YA_CLAW_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("YA_CLAW_AUTO_SEED_PROFILES", "false")
    monkeypatch.setenv("YA_CLAW_WORKSPACE_PROVIDER_BACKEND", "local")
    monkeypatch.setenv("YA_CLAW_BRIDGE_DISPATCH_MODE", "manual")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def db_engine(tmp_path: Path) -> AsyncEngine:
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'timers.sqlite3').resolve()}")
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
    workspace_dir = tmp_path / "workspace"
    data_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=data_dir,
        workspace_dir=workspace_dir,
        workspace_provider_backend="local",
        bridge_dispatch_mode="manual",
        _env_file=None,
    )


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _create_schema() -> None:
    import asyncio

    async def _run() -> None:
        settings = get_settings()
        engine = create_engine(settings.resolved_database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    asyncio.run(_run())


async def test_cron_next_fire_supports_steps_ranges_and_timezone() -> None:
    now = datetime(2026, 4, 26, 5, 7, tzinfo=UTC)

    assert compute_next_fire_at("*/15 5-6 * * *", "UTC", now=now) == datetime(2026, 4, 26, 5, 15, tzinfo=UTC)
    assert compute_next_fire_at("0 9 * * *", "Asia/Shanghai", now=now) == datetime(2026, 4, 27, 1, 0, tzinfo=UTC)


async def test_schedule_controller_dispatch_due_scans_due_records_and_submits_run(
    db_session: AsyncSession,
    settings: ClawSettings,
) -> None:
    controller = ScheduleController()
    runtime_state = InMemoryRuntimeState()
    supervisor = RecordingSupervisor()
    dispatcher = RunDispatcher(supervisor)  # type: ignore[arg-type]
    now = datetime(2026, 4, 26, 5, 30, tzinfo=UTC)

    schedule = await controller.create(
        db_session,
        ScheduleCreateRequest(
            name="Every minute smoke test",
            prompt="Report timer status.",
            cron="* * * * *",
            timezone="UTC",
            profile_name="default",
            metadata={"purpose": "test"},
        ),
    )
    record = await db_session.get(ScheduleRecord, schedule.id)
    assert isinstance(record, ScheduleRecord)
    record.next_fire_at = now - timedelta(minutes=1)
    await db_session.commit()

    fired = await controller.dispatch_due(db_session, settings, runtime_state, dispatcher, now=now)

    assert len(fired) == 1
    fire = fired[0]
    assert fire.status == "submitted"
    assert fire.run_id in supervisor.submitted_run_ids
    assert fire.created_session_id is not None

    run = await db_session.get(RunRecord, fire.run_id)
    assert isinstance(run, RunRecord)
    assert run.status == "queued"
    assert run.trigger_type == "schedule"
    assert run.profile_name == "default"
    assert run.run_metadata["source"] == "schedule"
    assert run.run_metadata["schedule_id"] == schedule.id
    assert run.run_metadata["schedule_fire_id"] == fire.id

    await db_session.refresh(record)
    assert record.fire_count == 1
    assert record.last_fire_id == fire.id
    assert record.last_run_id == fire.run_id
    assert record.next_fire_at is not None
    assert record.next_fire_at.replace(tzinfo=UTC) > now


async def test_heartbeat_controller_defaults_and_manual_trigger_create_isolated_run(
    db_session: AsyncSession,
    settings: ClawSettings,
) -> None:
    settings.heartbeat_guidance_path.write_text("# Heartbeat\nCheck runtime health.\n", encoding="utf-8")
    controller = HeartbeatController()
    runtime_state = InMemoryRuntimeState()
    supervisor = RecordingSupervisor()
    dispatcher = RunDispatcher(supervisor)  # type: ignore[arg-type]

    config = await controller.config(db_session, settings)
    assert config.enabled is False
    assert config.interval_seconds == 300
    assert config.profile_name == "default"
    assert config.guidance_file["exists"] is True
    assert config.next_fire_at is None

    settings.heartbeat_enabled = True
    fire = await controller.trigger(db_session, settings, runtime_state, dispatcher)

    assert fire.status == "submitted"
    assert fire.metadata["manual"] is True
    assert fire.run_id in supervisor.submitted_run_ids
    assert fire.session_id is not None

    run = await db_session.get(RunRecord, fire.run_id)
    assert isinstance(run, RunRecord)
    assert run.trigger_type == "heartbeat"
    assert run.profile_name == "default"
    assert run.run_metadata["source"] == "heartbeat"
    assert run.run_metadata["heartbeat_fire_id"] == fire.id
    assert run.restore_from_run_id is None


async def test_heartbeat_dispatcher_scan_triggers_due_fire(
    db_engine: AsyncEngine,
    settings: ClawSettings,
) -> None:
    settings.heartbeat_enabled = True
    settings.heartbeat_interval_seconds = 1
    session_factory = create_session_factory(db_engine)
    runtime_state = InMemoryRuntimeState()
    supervisor = RecordingSupervisor()
    dispatcher = HeartbeatDispatcher(
        settings=settings,
        session_factory=session_factory,
        runtime_state=runtime_state,
        run_dispatcher=RunDispatcher(supervisor),  # type: ignore[arg-type]
    )

    count = await dispatcher.dispatch_once()

    assert count == 1
    assert len(supervisor.submitted_run_ids) == 1
    async with session_factory() as session:
        fire = (await session.execute(select(HeartbeatFireRecord))).scalar_one()
        run = await session.get(RunRecord, fire.run_id)
    assert fire.status == "submitted"
    assert fire.fire_metadata["manual"] is False
    assert isinstance(run, RunRecord)
    assert run.trigger_type == "heartbeat"


async def test_schedule_dispatcher_scan_processes_pending_and_due_fires(
    db_engine: AsyncEngine,
    settings: ClawSettings,
) -> None:
    session_factory = create_session_factory(db_engine)
    runtime_state = InMemoryRuntimeState()
    supervisor = RecordingSupervisor()
    controller = ScheduleController()
    now = datetime(2026, 4, 26, 5, 30, tzinfo=UTC)

    async with session_factory() as session:
        schedule = await controller.create(
            session,
            ScheduleCreateRequest(
                name="Due schedule",
                prompt="Report schedule status.",
                cron="* * * * *",
                timezone="UTC",
                profile_name="default",
            ),
        )
        record = await session.get(ScheduleRecord, schedule.id)
        assert isinstance(record, ScheduleRecord)
        record.next_fire_at = now - timedelta(minutes=1)
        await session.commit()

    dispatcher = ScheduleDispatcher(
        settings=settings,
        session_factory=session_factory,
        runtime_state=runtime_state,
        run_dispatcher=RunDispatcher(supervisor),  # type: ignore[arg-type]
    )

    count = await dispatcher.dispatch_once()

    assert count == 1
    assert len(supervisor.submitted_run_ids) == 1
    async with session_factory() as session:
        fire = (await session.execute(select(ScheduleFireRecord))).scalar_one()
        run = await session.get(RunRecord, fire.run_id)
        record = await session.get(ScheduleRecord, schedule.id)
    assert fire.status == "submitted"
    assert fire.fire_metadata["manual"] is False
    assert isinstance(run, RunRecord)
    assert run.trigger_type == "schedule"
    assert isinstance(record, ScheduleRecord)
    assert record.fire_count == 1


def test_timer_api_routes_expose_config_create_trigger_and_fire_history() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        client.app.state.execution_supervisor = None
        heartbeat_config = client.get("/api/v1/heartbeat/config", headers=_auth_headers())
        assert heartbeat_config.status_code == 200
        assert heartbeat_config.json()["enabled"] is False
        assert heartbeat_config.json()["interval_seconds"] == 300

        create_schedule = client.post(
            "/api/v1/schedules",
            headers=_auth_headers(),
            json={
                "name": "API cron smoke test",
                "prompt": "Report API timer status.",
                "cron": "* * * * *",
                "timezone": "UTC",
                "enabled": True,
                "owner_kind": "user",
            },
        )
        assert create_schedule.status_code == 201
        schedule_id = create_schedule.json()["id"]
        assert create_schedule.json()["cron"]["next_fire_at"] is not None

        manual_fire = client.post(
            f"/api/v1/schedules/{schedule_id}:trigger",
            headers=_auth_headers(),
        )
        assert manual_fire.status_code == 201
        assert manual_fire.json()["status"] == "submitted"
        assert manual_fire.json()["run_id"] is not None

        schedule_fires = client.get(f"/api/v1/schedules/{schedule_id}/fires", headers=_auth_headers())
        assert schedule_fires.status_code == 200
        assert len(schedule_fires.json()["fires"]) == 1

        heartbeat_fire = client.post("/api/v1/heartbeat:trigger", headers=_auth_headers())
        assert heartbeat_fire.status_code == 201
        assert heartbeat_fire.json()["status"] == "submitted"
        assert heartbeat_fire.json()["run_id"] is not None

        heartbeat_fires = client.get("/api/v1/heartbeat/fires", headers=_auth_headers())
        assert heartbeat_fires.status_code == 200
        assert len(heartbeat_fires.json()["fires"]) == 1
