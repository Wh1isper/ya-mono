from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from ya_claw.config import ClawSettings
from ya_claw.controller.models import (
    ControlResponse,
    DispatchMode,
    RunCreateRequest,
    RunDetail,
    RunGetResponse,
    RunTraceResponse,
    SteerRequest,
)
from ya_claw.controller.run import RunController
from ya_claw.execution.coordinator import ExecutionSupervisor
from ya_claw.execution.dispatcher import RunDispatcher
from ya_claw.notifications import NotificationHub
from ya_claw.runtime_state import InMemoryRuntimeState

router = APIRouter(prefix="/runs", tags=["runs"])
controller = RunController()


@router.post("", response_model=RunDetail, status_code=201)
async def create_run(request: Request, payload: RunCreateRequest) -> RunDetail:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    payload.dispatch_mode = DispatchMode.ASYNC
    async with session_factory() as db_session:
        run = await controller.create(db_session, settings, runtime_state, payload)
    await _publish_run_notification(request, "run.created", run)
    _dispatch_run(request, run.id, payload.dispatch_mode, require_submission=False)
    return run


@router.post(":stream")
async def create_run_stream(request: Request, payload: RunCreateRequest) -> EventSourceResponse:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    payload.dispatch_mode = DispatchMode.STREAM
    async with session_factory() as db_session:
        run = await controller.create(db_session, settings, runtime_state, payload)
    await _publish_run_notification(request, "run.created", run)
    _dispatch_run(request, run.id, payload.dispatch_mode, require_submission=True)
    return EventSourceResponse(runtime_state.stream_run_events(run.id))


@router.get("/{run_id}", response_model=RunGetResponse)
async def get_run(
    request: Request,
    run_id: str,
    include_state: bool = True,
    include_message: bool = False,
) -> RunGetResponse:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.get(
            db_session,
            settings,
            run_id,
            include_state=include_state,
            include_message=include_message,
        )


@router.get("/{run_id}/trace", response_model=RunTraceResponse)
async def get_run_trace(
    request: Request,
    run_id: str,
    max_item_chars: int = 4000,
    max_total_chars: int = 12000,
) -> RunTraceResponse:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.get_trace(
            db_session,
            settings,
            run_id,
            max_item_chars=max_item_chars,
            max_total_chars=max_total_chars,
        )


@router.post("/{run_id}/steer", response_model=ControlResponse)
async def steer_run(request: Request, run_id: str, payload: SteerRequest) -> ControlResponse:
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.steer(db_session, runtime_state, run_id, payload)


@router.post("/{run_id}/interrupt", response_model=RunDetail)
async def interrupt_run(request: Request, run_id: str) -> RunDetail:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        run = await controller.interrupt(db_session, settings, runtime_state, run_id)
    await _publish_run_notification(request, "run.updated", run)
    return run


@router.post("/{run_id}/cancel", response_model=RunDetail)
async def cancel_run(request: Request, run_id: str) -> RunDetail:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        run = await controller.cancel(db_session, settings, runtime_state, run_id)
    await _publish_run_notification(request, "run.updated", run)
    return run


@router.get("/{run_id}/events")
async def stream_run_events(
    request: Request,
    run_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    runtime_state = _get_runtime_state(request)
    if runtime_state.get_run_handle(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' does not have an active event buffer.")
    return EventSourceResponse(runtime_state.stream_run_events(run_id, last_event_id=last_event_id))


async def _publish_run_notification(request: Request, event_type: str, run: RunDetail) -> None:
    notification_hub = _get_notification_hub(request)
    await notification_hub.publish(
        event_type,
        {
            "session_id": run.session_id,
            "run_id": run.id,
            "status": run.status,
            "sequence_no": run.sequence_no,
            "profile_name": run.profile_name,
            "project_id": run.project_id,
            "termination_reason": run.termination_reason,
            "error_message": run.error_message,
        },
    )


def _dispatch_run(request: Request, run_id: str, mode: DispatchMode, *, require_submission: bool) -> None:
    dispatcher = RunDispatcher(_get_execution_supervisor(request))
    result = dispatcher.dispatch(run_id, mode)
    if require_submission and not result.submitted:
        raise HTTPException(status_code=503, detail="Execution supervisor is unavailable.")


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
        raise TypeError("Database session factory is unavailable.")
    return session_factory
