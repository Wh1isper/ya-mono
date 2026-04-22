from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.config import ClawSettings
from ya_claw.controller.models import (
    ProfileDetail,
    ProfileSeedRequest,
    ProfileSeedResponse,
    ProfileSummary,
    ProfileUpsertRequest,
)
from ya_claw.controller.profile import ProfileController
from ya_claw.execution.profile import ProfileResolver

router = APIRouter(prefix="/profiles", tags=["profiles"])
controller = ProfileController()


@router.get("", response_model=list[ProfileSummary])
async def list_profiles(request: Request) -> list[ProfileSummary]:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.list(db_session)


@router.get("/{profile_name}", response_model=ProfileDetail)
async def get_profile(request: Request, profile_name: str) -> ProfileDetail:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.get(db_session, profile_name)


@router.put("/{profile_name}", response_model=ProfileDetail)
async def put_profile(request: Request, profile_name: str, payload: ProfileUpsertRequest) -> ProfileDetail:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        return await controller.upsert(db_session, profile_name, payload)


@router.delete("/{profile_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(request: Request, profile_name: str) -> Response:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        await controller.delete(db_session, profile_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/seed", response_model=ProfileSeedResponse)
async def seed_profiles(request: Request, payload: ProfileSeedRequest) -> ProfileSeedResponse:
    settings = _get_settings(request)
    resolver = _get_profile_resolver(request)
    return await controller.seed(settings=settings, resolver=resolver, prune_missing=payload.prune_missing)


def _get_settings(request: Request) -> ClawSettings:
    settings = request.app.state.settings
    if not isinstance(settings, ClawSettings):
        raise TypeError("Application settings are unavailable.")
    return settings


def _get_profile_resolver(request: Request) -> ProfileResolver:
    resolver = request.app.state.profile_resolver
    if not isinstance(resolver, ProfileResolver):
        raise TypeError("Profile resolver is unavailable.")
    return resolver


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    session_factory = request.app.state.db_session_factory
    if not isinstance(session_factory, async_sessionmaker):
        raise TypeError("Database session factory is unavailable.")
    return session_factory
