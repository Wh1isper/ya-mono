from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from ya_claw.config import ClawSettings
from ya_claw.controller.models import (
    ControlResponse,
    RunDetail,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionForkRequest,
    SessionGetResponse,
    SessionRunCreateRequest,
    SessionSummary,
    SteerRequest,
)
from ya_claw.controller.run import RunController
from ya_claw.controller.session import SessionController
from ya_claw.execution.coordinator import ExecutionSupervisor
from ya_claw.runtime_state import InMemoryRuntimeState

router = APIRouter(prefix="/sessions", tags=["sessions"])
session_controller = SessionController()
run_controller = RunController()


@router.post("", response_model=SessionCreateResponse, status_code=201)
async def create_session(
    request: Request, payload: SessionCreateRequest
) -> SessionCreateResponse | EventSourceResponse:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        response = await session_controller.create(db_session, settings, runtime_state, payload)

    if payload.dispatch_mode == "stream" and response.run is not None:
        if not _submit_run(request, response.run.id):
            raise HTTPException(status_code=503, detail="Execution supervisor is unavailable.")
        return EventSourceResponse(runtime_state.stream_run_events(response.run.id))

    _submit_run(request, response.run.id if response.run is not None else None)
    return response


@router.get("", response_model=list[SessionSummary])
async def list_sessions(request: Request) -> list[SessionSummary]:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await session_controller.list(db_session)


@router.get("/{session_id}", response_model=SessionGetResponse)
async def get_session(
    request: Request,
    session_id: str,
    runs_limit: int = 20,
    before_sequence_no: int | None = None,
    include_message: bool = False,
) -> SessionGetResponse:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await session_controller.get(
            db_session,
            settings,
            session_id,
            runs_limit=runs_limit,
            before_sequence_no=before_sequence_no,
            include_message=include_message,
        )


@router.post("/{session_id}/runs", response_model=RunDetail, status_code=201)
async def create_session_run(
    request: Request, session_id: str, payload: SessionRunCreateRequest
) -> RunDetail | EventSourceResponse:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        run = await session_controller.create_run(db_session, settings, runtime_state, session_id, payload)

    if payload.dispatch_mode == "stream":
        if not _submit_run(request, run.id):
            raise HTTPException(status_code=503, detail="Execution supervisor is unavailable.")
        return EventSourceResponse(runtime_state.stream_run_events(run.id))

    _submit_run(request, run.id)
    return run


@router.post("/{session_id}/steer", response_model=ControlResponse)
async def steer_session(request: Request, session_id: str, payload: SteerRequest) -> ControlResponse:
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        run_id = await session_controller.resolve_active_run_id(db_session, session_id)
        return await run_controller.steer(db_session, runtime_state, run_id, payload)


@router.post("/{session_id}/interrupt", response_model=RunDetail)
async def interrupt_session(request: Request, session_id: str) -> RunDetail:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        run_id = await session_controller.resolve_active_run_id(db_session, session_id)
        return await run_controller.interrupt(db_session, settings, runtime_state, run_id)


@router.post("/{session_id}/cancel", response_model=RunDetail)
async def cancel_session(request: Request, session_id: str) -> RunDetail:
    settings = _get_settings(request)
    runtime_state = _get_runtime_state(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        run_id = await session_controller.resolve_active_run_id(db_session, session_id)
        return await run_controller.cancel(db_session, settings, runtime_state, run_id)


@router.post("/{session_id}/fork", response_model=SessionSummary, status_code=201)
async def fork_session(request: Request, session_id: str, payload: SessionForkRequest) -> SessionSummary:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await session_controller.fork(db_session, session_id, payload)


@router.get("/{session_id}/events")
async def stream_session_events(
    request: Request,
    session_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    runtime_state = _get_runtime_state(request)
    if runtime_state.get_session_run_handle(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' does not have an active event buffer.")
    return EventSourceResponse(runtime_state.stream_session_events(session_id, last_event_id=last_event_id))


def _submit_run(request: Request, run_id: str | None) -> bool:
    if run_id is None:
        return False
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
