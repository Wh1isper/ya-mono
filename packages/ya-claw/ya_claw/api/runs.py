from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.config import ClawSettings
from ya_claw.controller.models import RunCreateRequest, RunDetail
from ya_claw.controller.run import RunController

router = APIRouter(prefix="/runs", tags=["runs"])
controller = RunController()


@router.post("", response_model=RunDetail, status_code=201)
async def create_run(request: Request, payload: RunCreateRequest) -> RunDetail:
    settings = _get_settings(request)
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.create(db_session, settings, payload)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(request: Request, run_id: str) -> RunDetail:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.get(db_session, run_id)


@router.post("/{run_id}/cancel", response_model=RunDetail)
async def cancel_run(request: Request, run_id: str) -> RunDetail:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.cancel(db_session, run_id)


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
