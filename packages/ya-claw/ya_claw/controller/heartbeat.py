from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ya_claw.config import ClawSettings
from ya_claw.controller.models import DispatchMode, RunCreateRequest, TextPart, TriggerType
from ya_claw.controller.run import RunController
from ya_claw.execution.dispatcher import RunDispatcher
from ya_claw.orm.tables import HeartbeatFireRecord, utc_now
from ya_claw.runtime_state import InMemoryRuntimeState

HeartbeatFireStatus = Literal["pending", "submitted", "skipped", "failed"]


class HeartbeatConfigResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    profile_name: str
    prompt: str
    on_active: str
    guidance_file: dict[str, Any]
    next_fire_at: datetime | None = None


class HeartbeatStatusResponse(BaseModel):
    enabled: bool
    next_fire_at: datetime | None = None
    last_fire: HeartbeatFireSummary | None = None


class HeartbeatFireSummary(BaseModel):
    id: str
    scheduled_at: datetime
    fired_at: datetime | None = None
    status: HeartbeatFireStatus
    session_id: str | None = None
    run_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class HeartbeatFireListResponse(BaseModel):
    fires: list[HeartbeatFireSummary] = Field(default_factory=list)


class HeartbeatController:
    def __init__(self) -> None:
        self._run_controller = RunController()

    async def config(self, db_session: AsyncSession, settings: ClawSettings) -> HeartbeatConfigResponse:
        return HeartbeatConfigResponse(
            enabled=settings.heartbeat_enabled,
            interval_seconds=settings.heartbeat_interval_seconds,
            profile_name=settings.resolved_heartbeat_profile,
            prompt=settings.heartbeat_prompt,
            on_active=settings.heartbeat_on_active,
            guidance_file={
                "path": str(settings.heartbeat_guidance_path),
                "exists": settings.heartbeat_guidance_path.exists(),
            },
            next_fire_at=await self.next_fire_at(db_session, settings),
        )

    async def status(self, db_session: AsyncSession, settings: ClawSettings) -> HeartbeatStatusResponse:
        return HeartbeatStatusResponse(
            enabled=settings.heartbeat_enabled,
            next_fire_at=await self.next_fire_at(db_session, settings),
            last_fire=await self.last_fire(db_session),
        )

    async def list_fires(self, db_session: AsyncSession, *, limit: int = 50) -> HeartbeatFireListResponse:
        normalized_limit = min(max(limit, 1), 200)
        result = await db_session.execute(
            select(HeartbeatFireRecord).order_by(HeartbeatFireRecord.created_at.desc()).limit(normalized_limit)
        )
        return HeartbeatFireListResponse(
            fires=[heartbeat_fire_summary_from_record(record) for record in result.scalars().all()]
        )

    async def last_fire(self, db_session: AsyncSession) -> HeartbeatFireSummary | None:
        result = await db_session.execute(
            select(HeartbeatFireRecord).order_by(HeartbeatFireRecord.created_at.desc()).limit(1)
        )
        record = result.scalar_one_or_none()
        return heartbeat_fire_summary_from_record(record) if isinstance(record, HeartbeatFireRecord) else None

    async def next_fire_at(self, db_session: AsyncSession, settings: ClawSettings) -> datetime | None:
        if not settings.heartbeat_enabled:
            return None
        last_fire = await self.last_fire(db_session)
        if last_fire is None:
            return utc_now()
        return last_fire.scheduled_at + timedelta(seconds=max(settings.heartbeat_interval_seconds, 1))

    async def dispatch_due(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        dispatcher: RunDispatcher,
    ) -> HeartbeatFireSummary | None:
        if not settings.heartbeat_enabled:
            return None
        due_at = await self.next_fire_at(db_session, settings)
        if due_at is None or due_at > utc_now():
            return None
        return await self.trigger(db_session, settings, runtime_state, dispatcher, scheduled_at=due_at, manual=False)

    async def trigger(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        dispatcher: RunDispatcher,
        *,
        scheduled_at: datetime | None = None,
        manual: bool = True,
    ) -> HeartbeatFireSummary:
        effective_scheduled_at = scheduled_at or utc_now()
        record = HeartbeatFireRecord(
            id=uuid4().hex,
            scheduled_at=effective_scheduled_at,
            fired_at=utc_now(),
            status="pending",
            dedupe_key=f"heartbeat:{'manual' if manual else effective_scheduled_at.isoformat()}:{uuid4().hex if manual else ''}",
            fire_metadata={"manual": manual},
        )
        db_session.add(record)
        await db_session.flush()
        try:
            run = await self._run_controller.create(
                db_session,
                settings,
                runtime_state,
                RunCreateRequest(
                    session_id=None,
                    reset_state=True,
                    profile_name=settings.resolved_heartbeat_profile,
                    input_parts=[TextPart(type="text", text=settings.heartbeat_prompt)],
                    trigger_type=TriggerType.HEARTBEAT,
                    metadata={"source": "heartbeat", "heartbeat_fire_id": record.id},
                    dispatch_mode=DispatchMode.ASYNC,
                ),
            )
            record.status = "submitted"
            record.session_id = run.session_id
            record.run_id = run.id
            dispatcher.dispatch(run.id, DispatchMode.ASYNC)
        except HTTPException as exc:
            record.status = "failed"
            record.error_message = str(exc.detail)
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)
        await db_session.commit()
        await db_session.refresh(record)
        return heartbeat_fire_summary_from_record(record)


def heartbeat_fire_summary_from_record(record: HeartbeatFireRecord) -> HeartbeatFireSummary:
    return HeartbeatFireSummary(
        id=record.id,
        scheduled_at=record.scheduled_at,
        fired_at=record.fired_at,
        status=cast(HeartbeatFireStatus, record.status),
        session_id=record.session_id,
        run_id=record.run_id,
        error_message=record.error_message,
        metadata=dict(record.fire_metadata),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
