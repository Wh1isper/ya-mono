from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.config import ClawSettings
from ya_claw.controller.models import RunSummary, SessionCreateRequest, SessionDetail, SessionSummary
from ya_claw.controller.session import SessionController

router = APIRouter(prefix="/sessions", tags=["sessions"])
controller = SessionController()


@router.post("", response_model=SessionSummary, status_code=201)
async def create_session(request: Request, payload: SessionCreateRequest) -> SessionSummary:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.create(db_session, settings, payload)


@router.get("", response_model=list[SessionSummary])
async def list_sessions(request: Request) -> list[SessionSummary]:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.list(db_session)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(request: Request, session_id: str) -> SessionDetail:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.get(db_session, session_id)


@router.get("/{session_id}/runs", response_model=list[RunSummary])
async def list_session_runs(request: Request, session_id: str) -> list[RunSummary]:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.list_runs(db_session, session_id)


@router.get("/{session_id}/state")
async def get_session_state(request: Request, session_id: str) -> dict[str, object]:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.read_blob(db_session, settings, session_id, "state.json")


@router.get("/{session_id}/message")
async def get_session_message(request: Request, session_id: str) -> dict[str, object]:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.read_blob(db_session, settings, session_id, "message.json")


def _get_settings(request: Request) -> ClawSettings:
    settings = request.app.state.settings
    if not isinstance(settings, ClawSettings):
        raise TypeError("Application settings are unavailable.")
    return settings


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = request.app.state.db_session_factory
    if not isinstance(session_factory, async_sessionmaker):
        raise TypeError("Database session factory is unavailable.")
    return session_factory
