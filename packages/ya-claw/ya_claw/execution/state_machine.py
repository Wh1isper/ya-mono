from __future__ import annotations

from datetime import UTC, datetime

from ya_claw.orm.tables import RunRecord, SessionRecord


def queue_run(session: SessionRecord, run: RunRecord, *, queued_at: datetime | None = None) -> None:
    effective_time = queued_at or datetime.now(UTC)
    session.head_run_id = run.id
    session.profile_name = run.profile_name
    session.project_id = run.project_id
    session.updated_at = effective_time
    run.status = "queued"


def mark_run_running(
    session: SessionRecord,
    run: RunRecord,
    *,
    started_at: datetime | None = None,
    claimed_by: str | None = None,
) -> None:
    effective_time = started_at or datetime.now(UTC)
    session.active_run_id = run.id
    session.head_run_id = run.id
    session.updated_at = effective_time
    run.status = "running"
    run.started_at = effective_time
    run.claimed_by = claimed_by
    run.claimed_at = effective_time


def complete_run(
    session: SessionRecord,
    run: RunRecord,
    *,
    committed_at: datetime | None = None,
) -> None:
    effective_time = committed_at or datetime.now(UTC)
    session.head_run_id = run.id
    session.head_success_run_id = run.id
    session.active_run_id = None
    session.updated_at = effective_time
    run.status = "completed"
    run.termination_reason = "completed"
    run.finished_at = effective_time
    run.committed_at = effective_time
    if run.started_at is None:
        run.started_at = effective_time


def fail_run(session: SessionRecord, run: RunRecord, *, finished_at: datetime | None = None) -> None:
    effective_time = finished_at or datetime.now(UTC)
    session.head_run_id = run.id
    if session.active_run_id == run.id:
        session.active_run_id = None
    session.updated_at = effective_time
    run.status = "failed"
    run.termination_reason = "error"
    run.finished_at = effective_time
    if run.started_at is None:
        run.started_at = effective_time


def cancel_run(session: SessionRecord, run: RunRecord, *, finished_at: datetime | None = None) -> None:
    effective_time = finished_at or datetime.now(UTC)
    session.head_run_id = run.id
    if session.active_run_id == run.id:
        session.active_run_id = None
    session.updated_at = effective_time
    run.status = "cancelled"
    run.termination_reason = "cancel"
    run.finished_at = effective_time


def interrupt_run(session: SessionRecord, run: RunRecord, *, finished_at: datetime | None = None) -> None:
    effective_time = finished_at or datetime.now(UTC)
    session.head_run_id = run.id
    if session.active_run_id == run.id:
        session.active_run_id = None
    session.updated_at = effective_time
    run.status = "cancelled"
    run.termination_reason = "interrupt"
    run.finished_at = effective_time
    if run.started_at is None:
        run.started_at = effective_time
