from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ya_claw.config import ClawSettings
from ya_claw.controller.models import RunCreateRequest, RunDetail, run_detail_from_record
from ya_claw.orm.tables import RunRecord, SessionRecord


class RunController:
    async def create(self, db_session: AsyncSession, settings: ClawSettings, request: RunCreateRequest) -> RunDetail:
        session_id = request.session_id
        if session_id is None:
            session_id = uuid4().hex
            session_record = SessionRecord(
                id=session_id,
                profile_name=request.profile_name,
                project_id=request.project_id,
                session_metadata=dict(request.metadata),
            )
            db_session.add(session_record)
        else:
            session_record = await db_session.get(SessionRecord, session_id)
            if not isinstance(session_record, SessionRecord):
                raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        session_dir = settings.session_store_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        run_record = RunRecord(
            id=uuid4().hex,
            session_id=session_id,
            status="queued",
            trigger_type=request.trigger_type,
            profile_name=request.profile_name or session_record.profile_name,
            project_id=request.project_id or session_record.project_id,
            input_text=request.input_text,
            run_metadata=dict(request.metadata),
        )
        db_session.add(run_record)

        session_record.profile_name = run_record.profile_name
        session_record.project_id = run_record.project_id
        session_record.updated_at = datetime.now(UTC)

        await db_session.commit()
        await db_session.refresh(run_record)
        return run_detail_from_record(run_record)

    async def get(self, db_session: AsyncSession, run_id: str) -> RunDetail:
        run_record = await db_session.get(RunRecord, run_id)
        if not isinstance(run_record, RunRecord):
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found.")
        return run_detail_from_record(run_record)

    async def cancel(self, db_session: AsyncSession, run_id: str) -> RunDetail:
        run_record = await db_session.get(RunRecord, run_id)
        if not isinstance(run_record, RunRecord):
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found.")

        if run_record.status in {"queued", "running"}:
            run_record.status = "cancelled"
            run_record.finished_at = datetime.now(UTC)
            await db_session.commit()
            await db_session.refresh(run_record)

        return run_detail_from_record(run_record)
