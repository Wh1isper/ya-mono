from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.config import ClawSettings
from ya_claw.controller.heartbeat import (
    HeartbeatConfigResponse,
    HeartbeatController,
    HeartbeatFireListResponse,
    HeartbeatFireSummary,
    HeartbeatStatusResponse,
)
from ya_claw.execution.coordinator import ExecutionSupervisor
from ya_claw.execution.dispatcher import RunDispatcher
from ya_claw.notifications import NotificationHub
from ya_claw.runtime_state import InMemoryRuntimeState

router = APIRouter(prefix="/heartbeat", tags=["heartbeat"])
controller = HeartbeatController()


@router.get("/config", response_model=HeartbeatConfigResponse)
async def get_heartbeat_config(request: Request) -> HeartbeatConfigResponse:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.config(db_session, settings)


@router.get("/status", response_model=HeartbeatStatusResponse)
async def get_heartbeat_status(request: Request) -> HeartbeatStatusResponse:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.status(db_session, settings)


@router.get("/fires", response_model=HeartbeatFireListResponse)
async def list_heartbeat_fires(request: Request, limit: int = 50) -> HeartbeatFireListResponse:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.list_fires(db_session, limit=limit)


@router.post(":trigger", response_model=HeartbeatFireSummary, status_code=201)
async def trigger_heartbeat(request: Request) -> HeartbeatFireSummary:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    dispatcher = RunDispatcher(_get_execution_supervisor(request))
    async with session_factory() as db_session:
        fire = await controller.trigger(db_session, settings, runtime_state, dispatcher, manual=True)
    await _publish_fire_notification(request, fire)
    return fire


async def _publish_fire_notification(request: Request, fire: HeartbeatFireSummary) -> None:
    notification_hub = _get_notification_hub(request)
    await notification_hub.publish(
        "heartbeat.fire.created",
        {
            "heartbeat_fire_id": fire.id,
            "status": fire.status,
            "session_id": fire.session_id,
            "run_id": fire.run_id,
        },
    )


def _get_settings(request: Request) -> ClawSettings:
    settings = request.app.state.settings
    if not isinstance(settings, ClawSettings):
        raise TypeError("Application settings are unavailable.")
    return settings


def _get_runtime_state(request: Request) -> InMemoryRuntimeState:
    runtime_state = request.app.state.runtime_state
    if not isinstance(runtime_state, InMemoryRuntimeState):
        raise TypeError("Runtime state is unavailable.")
    return runtime_state


def _get_notification_hub(request: Request) -> NotificationHub:
    notification_hub = request.app.state.notification_hub
    if not isinstance(notification_hub, NotificationHub):
        raise TypeError("Notification hub is unavailable.")
    return notification_hub


def _get_execution_supervisor(request: Request) -> ExecutionSupervisor | None:
    supervisor = request.app.state.execution_supervisor
    if supervisor is None or isinstance(supervisor, ExecutionSupervisor):
        return supervisor
    raise TypeError("Execution supervisor is unavailable.")


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = request.app.state.db_session_factory
    if not isinstance(session_factory, async_sessionmaker):
        raise HTTPException(status_code=503, detail="Database session factory is unavailable.")
    return session_factory
