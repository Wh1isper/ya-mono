from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from ya_claw.config import ClawSettings
from ya_claw.controller.models import ControlResponse, RunCreateRequest, RunDetail, RunGetResponse, SteerRequest
from ya_claw.controller.run import RunController
from ya_claw.execution.coordinator import ExecutionSupervisor
from ya_claw.runtime_state import InMemoryRuntimeState

router = APIRouter(prefix="/runs", tags=["runs"])
controller = RunController()


@router.post("", response_model=RunDetail, status_code=201)
async def create_run(request: Request, payload: RunCreateRequest) -> RunDetail | EventSourceResponse:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        run = await controller.create(db_session, settings, runtime_state, payload)
    if payload.dispatch_mode == "stream":
        if not _submit_run(request, run.id):
            raise HTTPException(status_code=503, detail="Execution supervisor is unavailable.")
        return EventSourceResponse(runtime_state.stream_run_events(run.id))
    _submit_run(request, run.id)
    return run


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
        return await controller.interrupt(db_session, settings, runtime_state, run_id)


@router.post("/{run_id}/cancel", response_model=RunDetail)
async def cancel_run(request: Request, run_id: str) -> RunDetail:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.cancel(db_session, settings, runtime_state, run_id)


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


def _submit_run(request: Request, run_id: str) -> bool:
    supervisor = _get_execution_supervisor(request)
    if not isinstance(supervisor, ExecutionSupervisor):
        return False
    return supervisor.submit_run(run_id)


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
