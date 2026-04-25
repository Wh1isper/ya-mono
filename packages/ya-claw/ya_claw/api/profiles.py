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
from ya_claw.notifications import NotificationHub

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
        existing_profile = await controller.exists(db_session, profile_name)
        profile = await controller.upsert(db_session, profile_name, payload)
    await _publish_profile_notification(request, "profile.updated" if existing_profile else "profile.created", profile)
    return profile


@router.delete("/{profile_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(request: Request, profile_name: str) -> Response:
    session_factory = _get_session_factory(request)
    async with session_factory() as db_session:
        await controller.delete(db_session, profile_name)
    await _publish_profile_deleted_notification(request, profile_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/seed", response_model=ProfileSeedResponse)
async def seed_profiles(request: Request, payload: ProfileSeedRequest) -> ProfileSeedResponse:
    settings = _get_settings(request)
    resolver = _get_profile_resolver(request)
    response = await controller.seed(settings=settings, resolver=resolver, prune_missing=payload.prune_missing)
    notification_hub = _get_notification_hub(request)
    await notification_hub.publish(
        "profiles.seeded",
        {
            "seeded_names": response.seeded_names,
            "seed_file": response.seed_file,
            "prune_missing": response.prune_missing,
        },
    )
    return response


async def _publish_profile_notification(request: Request, event_type: str, profile: ProfileDetail) -> None:
    notification_hub = _get_notification_hub(request)
    await notification_hub.publish(
        event_type,
        {
            "profile_name": profile.name,
            "model": profile.model,
            "enabled": profile.enabled,
            "workspace_backend_hint": profile.workspace_backend_hint,
            "source_type": profile.source_type,
            "source_version": profile.source_version,
        },
    )


async def _publish_profile_deleted_notification(request: Request, profile_name: str) -> None:
    notification_hub = _get_notification_hub(request)
    await notification_hub.publish("profile.deleted", {"profile_name": profile_name})


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


def _get_notification_hub(request: Request) -> NotificationHub:
    notification_hub = request.app.state.notification_hub
    if not isinstance(notification_hub, NotificationHub):
        raise TypeError("Notification hub is unavailable.")
    return notification_hub
