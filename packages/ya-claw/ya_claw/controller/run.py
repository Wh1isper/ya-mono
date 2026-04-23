from __future__ import annotations

from contextlib import suppress
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ya_claw.agui_adapter import AguiEventAdapter
from ya_claw.config import ClawSettings
from ya_claw.controller.models import (
    ControlResponse,
    RunCreateRequest,
    RunDetail,
    RunGetResponse,
    RunStatus,
    RunSummary,
    SessionSummary,
    SteerRequest,
    TerminationReason,
    run_detail_from_record,
    run_summary_from_record,
    session_summary_from_record,
)
from ya_claw.controller.store import (
    ensure_run_dir,
    read_run_message_blob_if_exists,
    read_run_state_blob_if_exists,
)
from ya_claw.execution.state_machine import cancel_run, interrupt_run, queue_run
from ya_claw.orm.tables import RunRecord, SessionRecord
from ya_claw.runtime_state import InMemoryRuntimeState

_ACTIVE_RUN_STATUSES = frozenset({RunStatus.QUEUED, RunStatus.RUNNING})


class RunController:
    async def create(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        request: RunCreateRequest,
    ) -> RunDetail:
        session_id = request.session_id
        if session_id is None:
            if request.restore_from_run_id is not None:
                raise HTTPException(
                    status_code=422,
                    detail="session_id is required when restore_from_run_id is provided.",
                )
            session_id = uuid4().hex
            session_record = SessionRecord(
                id=session_id,
                profile_name=request.profile_name,
                project_id=request.project_id,
                session_metadata={},
            )
            db_session.add(session_record)
        else:
            session_record = await db_session.get(SessionRecord, session_id)
            if not isinstance(session_record, SessionRecord):
                raise HTTPException(status_code=404, detail=f"Session '{session_id}' was not found.")
            if isinstance(session_record.active_run_id, str):
                raise HTTPException(
                    status_code=409,
                    detail=f"Session '{session_id}' already has an active run '{session_record.active_run_id}'.",
                )

        if request.reset_state and request.restore_from_run_id is not None:
            raise HTTPException(
                status_code=422,
                detail="reset_state and restore_from_run_id cannot be used together.",
            )

        restore_from_run_id = None
        if not request.reset_state:
            restore_from_run_id = request.restore_from_run_id or session_record.head_success_run_id
        if restore_from_run_id is not None:
            await self._validate_restore_source(db_session, session_id, restore_from_run_id)

        sequence_no = await self._next_sequence_no(db_session, session_id)
        run_id = uuid4().hex
        run_record = RunRecord(
            id=run_id,
            session_id=session_id,
            sequence_no=sequence_no,
            restore_from_run_id=restore_from_run_id,
            status=RunStatus.QUEUED,
            trigger_type=request.trigger_type,
            profile_name=request.profile_name or session_record.profile_name,
            project_id=request.project_id or session_record.project_id,
            input_parts=[part.model_dump(mode="json") for part in request.input_parts],
            run_metadata=dict(request.metadata),
        )
        db_session.add(run_record)
        queue_run(session_record, run_record)

        await db_session.commit()
        await db_session.refresh(run_record)

        ensure_run_dir(settings, run_id)
        runtime_state.register_run(session_id, run_id, dispatch_mode=request.dispatch_mode)
        agui_adapter = AguiEventAdapter(session_id=session_id, run_id=run_id)
        await runtime_state.append_run_event(
            run_id,
            agui_adapter.build_run_queued_event({
                "run_id": run_id,
                "session_id": session_id,
                "status": run_record.status,
                "sequence_no": sequence_no,
                "dispatch_mode": request.dispatch_mode,
            }),
        )

        return run_detail_from_record(run_record)

    async def get(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        run_id: str,
        *,
        include_state: bool,
        include_message: bool,
    ) -> RunGetResponse:
        run_record = await db_session.get(RunRecord, run_id)
        if not isinstance(run_record, RunRecord):
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found.")

        session_record = await db_session.get(SessionRecord, run_record.session_id)
        if not isinstance(session_record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{run_record.session_id}' was not found.")

        state_payload = read_run_state_blob_if_exists(settings, run_id)
        message_events = read_run_message_blob_if_exists(settings, run_id)
        has_state = state_payload is not None
        has_message = message_events is not None

        return RunGetResponse(
            session=await self._build_session_summary(db_session, session_record),
            run=run_detail_from_record(run_record, has_state=has_state, has_message=has_message),
            state=state_payload if include_state else None,
            message=message_events if include_message else None,
        )

    def build_session_run_summary(
        self,
        settings: ClawSettings,
        run_record: RunRecord,
        *,
        include_message: bool,
    ) -> RunSummary:
        message_payload = read_run_message_blob_if_exists(settings, run_record.id) if include_message else None
        return run_summary_from_record(run_record, message=message_payload)

    async def cancel(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        run_id: str,
    ) -> RunDetail:
        return await self._stop_run(
            db_session,
            settings,
            runtime_state,
            run_id,
            event_type="run.cancelled",
            termination_reason=TerminationReason.CANCEL,
        )

    async def interrupt(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        run_id: str,
    ) -> RunDetail:
        return await self._stop_run(
            db_session,
            settings,
            runtime_state,
            run_id,
            event_type="run.interrupted",
            termination_reason=TerminationReason.INTERRUPT,
        )

    async def steer(
        self,
        db_session: AsyncSession,
        runtime_state: InMemoryRuntimeState,
        run_id: str,
        request: SteerRequest,
    ) -> ControlResponse:
        run_record = await db_session.get(RunRecord, run_id)
        if not isinstance(run_record, RunRecord):
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found.")
        if run_record.status not in _ACTIVE_RUN_STATUSES:
            raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not active.")
        if not request.input_parts:
            raise HTTPException(status_code=422, detail="input_parts must not be empty for steer requests.")

        input_payload = [part.model_dump(mode="json") for part in request.input_parts]
        try:
            await runtime_state.record_steering(run_id, input_payload)
            agui_adapter = AguiEventAdapter(session_id=run_record.session_id, run_id=run_id)
            await runtime_state.append_run_event(
                run_id,
                agui_adapter.build_run_steered_event({
                    "run_id": run_id,
                    "session_id": run_record.session_id,
                    "input_parts": input_payload,
                }),
            )
        except KeyError as exc:
            raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not active in runtime state.") from exc

        return ControlResponse(
            session_id=run_record.session_id,
            run_id=run_id,
            status=RunStatus(run_record.status),
        )

    async def _stop_run(
        self,
        db_session: AsyncSession,
        settings: ClawSettings,
        runtime_state: InMemoryRuntimeState,
        run_id: str,
        *,
        event_type: str,
        termination_reason: TerminationReason,
    ) -> RunDetail:
        run_record = await db_session.get(RunRecord, run_id)
        if not isinstance(run_record, RunRecord):
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found.")

        session_record = await db_session.get(SessionRecord, run_record.session_id)
        if not isinstance(session_record, SessionRecord):
            raise HTTPException(status_code=404, detail=f"Session '{run_record.session_id}' was not found.")

        if run_record.status in _ACTIVE_RUN_STATUSES:
            with suppress(KeyError):
                await runtime_state.request_stop(run_id, termination_reason)
            if termination_reason == TerminationReason.INTERRUPT:
                interrupt_run(session_record, run_record)
            else:
                cancel_run(session_record, run_record)
            await db_session.commit()
            await db_session.refresh(run_record)

        await self._emit_terminal_event(runtime_state, run_record, event_type)

        state_payload = read_run_state_blob_if_exists(settings, run_id)
        message_payload = read_run_message_blob_if_exists(settings, run_id)
        return run_detail_from_record(
            run_record,
            has_state=state_payload is not None,
            has_message=message_payload is not None,
        )

    async def _emit_terminal_event(
        self,
        runtime_state: InMemoryRuntimeState,
        run_record: RunRecord,
        event_type: str,
    ) -> None:
        agui_adapter = AguiEventAdapter(session_id=run_record.session_id, run_id=run_record.id)
        event_payload = {
            "run_id": run_record.id,
            "session_id": run_record.session_id,
            "status": run_record.status,
            "termination_reason": run_record.termination_reason,
        }
        mapped_event = (
            agui_adapter.build_run_interrupted_event(event_payload)
            if event_type == "run.interrupted"
            else agui_adapter.build_run_cancelled_event(event_payload)
        )
        try:
            await runtime_state.append_run_event(
                run_record.id,
                mapped_event,
                terminal=True,
            )
        except KeyError:
            await runtime_state.close_run(run_record.id)

    async def _validate_restore_source(
        self,
        db_session: AsyncSession,
        session_id: str,
        restore_from_run_id: str,
    ) -> RunRecord:
        restore_record = await db_session.get(RunRecord, restore_from_run_id)
        if not isinstance(restore_record, RunRecord):
            raise HTTPException(status_code=404, detail=f"Run '{restore_from_run_id}' was not found.")
        if restore_record.session_id != session_id:
            raise HTTPException(
                status_code=422,
                detail=f"Run '{restore_from_run_id}' does not belong to session '{session_id}'.",
            )
        return restore_record

    async def _build_session_summary(
        self,
        db_session: AsyncSession,
        session_record: SessionRecord,
    ) -> SessionSummary:
        run_count_statement = select(func.count()).where(RunRecord.session_id == session_record.id)
        run_count_result = await db_session.execute(run_count_statement)
        run_count = run_count_result.scalar_one()

        latest_run_statement = (
            select(RunRecord)
            .where(RunRecord.session_id == session_record.id)
            .order_by(RunRecord.sequence_no.desc(), RunRecord.id.desc())
            .limit(1)
        )
        latest_run_result = await db_session.execute(latest_run_statement)
        latest_run_record = latest_run_result.scalar_one_or_none()
        latest_run = run_summary_from_record(latest_run_record) if isinstance(latest_run_record, RunRecord) else None
        return session_summary_from_record(
            session_record,
            run_count=run_count,
            latest_run=latest_run,
        )

    async def _next_sequence_no(self, db_session: AsyncSession, session_id: str) -> int:
        statement = select(func.max(RunRecord.sequence_no)).where(RunRecord.session_id == session_id)
        result = await db_session.execute(statement)
        max_value = result.scalar_one_or_none()
        if isinstance(max_value, int):
            return max_value + 1
        return 1
