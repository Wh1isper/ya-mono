from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ya_claw.config import ClawSettings
from ya_claw.controller.models import (
    ProfileDetail,
    ProfileSeedResponse,
    ProfileSummary,
    ProfileUpsertRequest,
)
from ya_claw.execution.profile import ProfileResolver
from ya_claw.orm.tables import ProfileRecord


class ProfileController:
    async def list(self, db_session: AsyncSession) -> list[ProfileSummary]:
        statement: Select[tuple[ProfileRecord]] = select(ProfileRecord).order_by(ProfileRecord.name.asc())
        result = await db_session.execute(statement)
        records = list(result.scalars().all())
        return [profile_summary_from_record(record) for record in records]

    async def get(self, db_session: AsyncSession, profile_name: str) -> ProfileDetail:
        record = await db_session.get(ProfileRecord, profile_name)
        if not isinstance(record, ProfileRecord):
            raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' was not found.")
        return profile_detail_from_record(record)

    async def upsert(
        self,
        db_session: AsyncSession,
        profile_name: str,
        request: ProfileUpsertRequest,
    ) -> ProfileDetail:
        record = await db_session.get(ProfileRecord, profile_name)
        if not isinstance(record, ProfileRecord):
            record = ProfileRecord(name=profile_name, model=request.model)
            db_session.add(record)

        record.model = request.model.strip()
        record.model_settings_preset = request.model_settings_preset
        record.model_settings_override = request.model_settings_override
        record.model_config_preset = request.model_config_preset
        record.model_config_override = request.model_config_override
        record.system_prompt = request.system_prompt
        record.toolsets = list(request.toolsets)
        record.subagents = [dict(item) for item in request.subagents]
        record.include_builtin_subagents = request.include_builtin_subagents
        record.unified_subagents = request.unified_subagents
        record.need_user_approve_tools = list(request.need_user_approve_tools)
        record.need_user_approve_mcps = list(request.need_user_approve_mcps)
        record.workspace_backend_hint = request.workspace_backend_hint
        record.enabled = request.enabled
        record.source_type = request.source_type or "api"
        record.source_version = request.source_version
        record.source_checksum = request.source_checksum
        await db_session.commit()
        await db_session.refresh(record)
        return profile_detail_from_record(record)

    async def delete(self, db_session: AsyncSession, profile_name: str) -> None:
        record = await db_session.get(ProfileRecord, profile_name)
        if not isinstance(record, ProfileRecord):
            raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' was not found.")
        await db_session.delete(record)
        await db_session.commit()

    async def seed(
        self,
        *,
        settings: ClawSettings,
        resolver: ProfileResolver,
        prune_missing: bool,
    ) -> ProfileSeedResponse:
        seed_file = settings.resolved_profile_seed_file
        if seed_file is None or not seed_file.exists():
            raise HTTPException(status_code=404, detail="Profile seed file is not configured or does not exist.")
        seeded_names = await resolver.seed_profiles(prune_missing=prune_missing)
        return ProfileSeedResponse(
            seeded_names=seeded_names,
            seed_file=str(seed_file),
            prune_missing=prune_missing,
        )


def profile_summary_from_record(record: ProfileRecord) -> ProfileSummary:
    return ProfileSummary(
        name=record.name,
        model=record.model,
        workspace_backend_hint=record.workspace_backend_hint,
        enabled=record.enabled,
        source_type=record.source_type,
        source_version=record.source_version,
        updated_at=record.updated_at,
    )


def profile_detail_from_record(record: ProfileRecord) -> ProfileDetail:
    return ProfileDetail(
        **profile_summary_from_record(record).model_dump(),
        model_settings_preset=record.model_settings_preset,
        model_settings_override=dict(record.model_settings_override)
        if isinstance(record.model_settings_override, dict)
        else None,
        model_config_preset=record.model_config_preset,
        model_config_override=dict(record.model_config_override)
        if isinstance(record.model_config_override, dict)
        else None,
        system_prompt=record.system_prompt,
        toolsets=list(record.toolsets or []),
        subagents=[dict(item) for item in record.subagents or []],
        include_builtin_subagents=bool(record.include_builtin_subagents),
        unified_subagents=bool(record.unified_subagents),
        need_user_approve_tools=list(record.need_user_approve_tools or []),
        need_user_approve_mcps=list(record.need_user_approve_mcps or []),
        source_checksum=record.source_checksum,
        created_at=record.created_at,
    )
