from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ya_claw.config import ClawSettings
from ya_claw.controller.models import (
    RunSummary,
    SessionCreateRequest,
    SessionDetail,
    SessionSummary,
    run_summary_from_record,
    session_summary_from_record,
)
from ya_claw.orm.tables import RunRecord, SessionRecord

_ACTIVE_RUN_STATUSES = frozenset({"queued", "running"})


class SessionController:
    async def create(
        self, db_session: AsyncSession, settings: ClawSettings, request: SessionCreateRequest
    ) -> SessionSummary:
        session_id = uuid4().hex
        record = SessionRecord(
            id=session_id,
            profile_name=request.profile_name,
            project_id=request.project_id,
            session_metadata=dict(request.metadata),
        )
        session_dir = settings.session_store_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=False)

        try:
            db_session.add(record)
            await db_session.commit()
            await db_session.refresh(record)
        except Exception:
            session_dir.rmdir()
            raise

        return session_summary_from_record(record, run_count=0, active_run_ids=[], latest_run=None)

    async def list(self, db_session: AsyncSession) -> list[SessionSummary]:
        statement: Select[tuple[SessionRecord]] = select(SessionRecord).order_by(SessionRecord.updated_at.desc())
        result = await db_session.execute(statement)
        records = list(result.scalars().all())
        return await self._build_summaries(db_session, records)

    async def get(self, db_session: AsyncSession, session_id: str) -> SessionDetail:
        record = await db_session.get(SessionRecord, session_id)
        if not isinstance(record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        summaries = await self._build_summaries(db_session, [record])
        summary = summaries[0]
        recent_runs = await self.list_runs(db_session, session_id)
        return SessionDetail(**summary.model_dump(), recent_runs=recent_runs)

    async def list_runs(self, db_session: AsyncSession, session_id: str) -> list[RunSummary]:
        record = await db_session.get(SessionRecord, session_id)
        if not isinstance(record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        statement: Select[tuple[RunRecord]] = (
            select(RunRecord)
            .where(RunRecord.session_id == session_id)
            .order_by(RunRecord.created_at.desc(), RunRecord.id.desc())
        )
        result = await db_session.execute(statement)
        run_records = list(result.scalars().all())
        return [run_summary_from_record(run_record) for run_record in run_records]

    async def read_blob(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        session_id: str,
        blob_name: str,
    ) -> dict[str, object]:
        record = await db_session.get(SessionRecord, session_id)
        if not isinstance(record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        session_dir = settings.session_store_dir / session_id
        blob_path = session_dir / blob_name
        if not blob_path.exists():
            raise HTTPException(status_code=404, detail=f"Session blob '{blob_name}' was not found.")

        return self._load_json(blob_path)

    async def _build_summaries(self, db_session: AsyncSession, records: list[SessionRecord]) -> list[SessionSummary]:
        if not records:
            return []

        session_ids = [record.id for record in records]
        statement: Select[tuple[RunRecord]] = (
            select(RunRecord)
            .where(RunRecord.session_id.in_(session_ids))
            .order_by(RunRecord.session_id.asc(), RunRecord.created_at.desc(), RunRecord.id.desc())
        )
        result = await db_session.execute(statement)
        run_records = list(result.scalars().all())

        grouped_runs: dict[str, list[RunRecord]] = {session_id: [] for session_id in session_ids}
        for run_record in run_records:
            grouped_runs.setdefault(run_record.session_id, []).append(run_record)

        summaries: list[SessionSummary] = []
        for record in records:
            runs = grouped_runs.get(record.id, [])
            latest_run = run_summary_from_record(runs[0]) if runs else None
            active_run_ids = [run.id for run in runs if run.status in _ACTIVE_RUN_STATUSES]
            summaries.append(
                session_summary_from_record(
                    record,
                    run_count=len(runs),
                    active_run_ids=active_run_ids,
                    latest_run=latest_run,
                )
            )

        return summaries

    def _load_json(self, path: Path) -> dict[str, object]:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, dict):
            return payload
        raise HTTPException(status_code=500, detail=f"Session blob '{path.name}' has invalid content.")
