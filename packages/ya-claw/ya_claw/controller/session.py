from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ya_claw.config import ClawSettings
from ya_claw.controller.models import (
    RunCreateRequest,
    RunDetail,
    RunStatus,
    RunSummary,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDetail,
    SessionForkRequest,
    SessionGetResponse,
    SessionRunCreateRequest,
    SessionSummary,
    extract_project_references,
    normalize_project_references,
    run_summary_from_record,
    serialize_project_references,
    session_summary_from_record,
)
from ya_claw.controller.run import RunController
from ya_claw.orm.tables import RunRecord, SessionRecord
from ya_claw.runtime_state import InMemoryRuntimeState
from ya_claw.workspace import cleanup_session_sandbox, remove_session_sandbox_metadata

_DEFAULT_SESSION_RUNS_LIMIT = 20
_MAX_SESSION_RUNS_LIMIT = 100


class _SessionRunPage(BaseModel):
    items: list[RunSummary] = Field(default_factory=list)
    limit: int
    has_more: bool = False
    next_before_sequence_no: int | None = None


class SessionController:
    def __init__(self) -> None:
        self._run_controller = RunController()

    async def create(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        request: SessionCreateRequest,
    ) -> SessionCreateResponse:
        session_id = uuid4().hex
        project_references = normalize_project_references(request.project_id, request.projects)
        primary_project_id = project_references[0].project_id if project_references else request.project_id
        session_metadata = dict(request.metadata)
        if project_references:
            session_metadata["projects"] = serialize_project_references(project_references)
        record = SessionRecord(
            id=session_id,
            profile_name=request.profile_name,
            project_id=primary_project_id,
            session_metadata=session_metadata,
        )
        db_session.add(record)
        await db_session.commit()
        await db_session.refresh(record)

        created_run = None
        if request.input_parts:
            created_run = await self._run_controller.create(
                db_session,
                settings,
                runtime_state,
                RunCreateRequest(
                    session_id=session_id,
                    profile_name=request.profile_name,
                    project_id=primary_project_id,
                    projects=project_references,
                    input_parts=request.input_parts,
                    trigger_type=request.trigger_type,
                    metadata={},
                    dispatch_mode=request.dispatch_mode,
                ),
            )
            refreshed_record = await db_session.get(SessionRecord, session_id)
            if isinstance(refreshed_record, SessionRecord):
                record = refreshed_record

        summary = await self._build_summary(db_session, record)
        return SessionCreateResponse(session=summary, run=created_run)

    async def create_run(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        session_id: str,
        request: SessionRunCreateRequest,
    ) -> RunDetail:
        record = await db_session.get(SessionRecord, session_id)
        if not isinstance(record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        if request.reset_sandbox:
            if isinstance(record.active_run_id, str):
                raise HTTPException(
                    status_code=409,
                    detail=f"Session '{session_id}' already has an active run '{record.active_run_id}'.",
                )
            await cleanup_session_sandbox(record.session_metadata)
            record.session_metadata = remove_session_sandbox_metadata(record.session_metadata)
            await db_session.commit()
            await db_session.refresh(record)

        run_metadata = dict(request.metadata)
        project_references = normalize_project_references(record.project_id, request.projects)
        if project_references:
            run_metadata["projects"] = serialize_project_references(project_references)
        if request.reset_state:
            run_metadata["reset_state"] = True
        if request.reset_sandbox:
            run_metadata["reset_sandbox"] = True

        return await self._run_controller.create(
            db_session,
            settings,
            runtime_state,
            RunCreateRequest(
                session_id=session_id,
                restore_from_run_id=request.restore_from_run_id,
                reset_state=request.reset_state,
                profile_name=record.profile_name,
                project_id=record.project_id,
                projects=project_references,
                input_parts=request.input_parts,
                trigger_type=request.trigger_type,
                metadata=run_metadata,
                dispatch_mode=request.dispatch_mode,
            ),
        )

    async def list(self, db_session: AsyncSession) -> list[SessionSummary]:
        statement: Select[tuple[SessionRecord]] = select(SessionRecord).order_by(SessionRecord.updated_at.desc())
        result = await db_session.execute(statement)
        records = list(result.scalars().all())
        return await self._build_summaries(db_session, records)

    async def get(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        session_id: str,
        *,
        runs_limit: int = _DEFAULT_SESSION_RUNS_LIMIT,
        before_sequence_no: int | None = None,
        include_message: bool = False,
    ) -> SessionGetResponse:
        record = await db_session.get(SessionRecord, session_id)
        if not isinstance(record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        summary = await self._build_summary(db_session, record)
        run_list = await self._list_runs(
            db_session,
            settings,
            session_id,
            limit=runs_limit,
            before_sequence_no=before_sequence_no,
            include_message=include_message,
        )
        return SessionGetResponse(
            session=SessionDetail(
                **summary.model_dump(),
                runs=run_list.items,
                runs_limit=run_list.limit,
                runs_has_more=run_list.has_more,
                runs_next_before_sequence_no=run_list.next_before_sequence_no,
            )
        )

    async def _list_runs(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        session_id: str,
        *,
        limit: int = _DEFAULT_SESSION_RUNS_LIMIT,
        before_sequence_no: int | None = None,
        include_message: bool = False,
    ) -> _SessionRunPage:
        record = await db_session.get(SessionRecord, session_id)
        if not isinstance(record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        normalized_limit = min(max(limit, 1), _MAX_SESSION_RUNS_LIMIT)
        statement = select(RunRecord).where(RunRecord.session_id == session_id)
        if isinstance(before_sequence_no, int):
            statement = statement.where(RunRecord.sequence_no < before_sequence_no)
        statement = statement.order_by(RunRecord.sequence_no.desc(), RunRecord.id.desc()).limit(normalized_limit + 1)

        result = await db_session.execute(statement)
        run_records = list(result.scalars().all())
        has_more = len(run_records) > normalized_limit
        page_records = run_records[:normalized_limit]
        items = [
            self._run_controller.build_session_run_summary(
                settings,
                run_record,
                include_message=include_message,
            )
            for run_record in page_records
        ]
        next_before_sequence_no = page_records[-1].sequence_no if has_more and page_records else None
        return _SessionRunPage(
            items=items,
            limit=normalized_limit,
            has_more=has_more,
            next_before_sequence_no=next_before_sequence_no,
        )

    async def fork(self, db_session: AsyncSession, session_id: str, request: SessionForkRequest) -> SessionSummary:
        source_record = await db_session.get(SessionRecord, session_id)
        if not isinstance(source_record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")

        restore_from_run_id = request.restore_from_run_id or source_record.head_success_run_id
        if restore_from_run_id is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' does not have a forkable run.")

        restore_record = await db_session.get(RunRecord, restore_from_run_id)
        if not isinstance(restore_record, RunRecord):
            raise HTTPException(status_code=404, detail=f"Run '{restore_from_run_id}' was not found.")
        if restore_record.session_id != source_record.id:
            raise HTTPException(
                status_code=422,
                detail=f"Run '{restore_from_run_id}' does not belong to session '{session_id}'.",
            )

        source_projects = extract_project_references(source_record.project_id, source_record.session_metadata)
        project_references = normalize_project_references(
            request.project_id or source_record.project_id, request.projects or source_projects
        )
        primary_project_id = (
            project_references[0].project_id if project_references else request.project_id or source_record.project_id
        )
        session_metadata = dict(request.metadata)
        if project_references:
            session_metadata["projects"] = serialize_project_references(project_references)
        fork_record = SessionRecord(
            id=uuid4().hex,
            parent_session_id=source_record.id,
            profile_name=request.profile_name or source_record.profile_name,
            project_id=primary_project_id,
            session_metadata=session_metadata,
            head_run_id=restore_record.id,
            head_success_run_id=restore_record.id
            if restore_record.status == RunStatus.COMPLETED
            else source_record.head_success_run_id,
        )
        db_session.add(fork_record)
        await db_session.commit()
        await db_session.refresh(fork_record)
        return await self._build_summary(db_session, fork_record)

    async def resolve_active_run_id(self, db_session: AsyncSession, session_id: str) -> str:
        record = await db_session.get(SessionRecord, session_id)
        if not isinstance(record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
        if not isinstance(record.active_run_id, str):
            raise HTTPException(status_code=409, detail=f"Session '{session_id}' does not have an active run.")
        return record.active_run_id

    async def _build_summary(self, db_session: AsyncSession, record: SessionRecord) -> SessionSummary:
        summaries = await self._build_summaries(db_session, [record])
        return summaries[0]

    async def _build_summaries(self, db_session: AsyncSession, records: list[SessionRecord]) -> list[SessionSummary]:
        if not records:
            return []

        session_ids = [record.id for record in records]
        statement: Select[tuple[RunRecord]] = (
            select(RunRecord)
            .where(RunRecord.session_id.in_(session_ids))
            .order_by(RunRecord.session_id.asc(), RunRecord.sequence_no.desc(), RunRecord.id.desc())
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
            summaries.append(
                session_summary_from_record(
                    record,
                    run_count=len(runs),
                    latest_run=latest_run,
                )
            )

        return summaries
