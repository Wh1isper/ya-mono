from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ya_claw.orm.tables import RunRecord, SessionRecord


class SessionCreateRequest(BaseModel):
    profile_name: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCreateRequest(BaseModel):
    session_id: str | None = None
    profile_name: str | None = None
    project_id: str | None = None
    input_text: str | None = None
    trigger_type: str = "api"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunSummary(BaseModel):
    id: str
    session_id: str
    status: str
    trigger_type: str
    profile_name: str | None = None
    project_id: str | None = None
    input_text: str | None = None
    output_summary: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunDetail(RunSummary):
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionSummary(BaseModel):
    id: str
    parent_session_id: str | None = None
    profile_name: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    run_count: int = 0
    active_run_ids: list[str] = Field(default_factory=list)
    latest_run: RunSummary | None = None


class SessionDetail(SessionSummary):
    recent_runs: list[RunSummary] = Field(default_factory=list)


def run_summary_from_record(record: RunRecord) -> RunSummary:
    return RunSummary(
        id=record.id,
        session_id=record.session_id,
        status=record.status,
        trigger_type=record.trigger_type,
        profile_name=record.profile_name,
        project_id=record.project_id,
        input_text=record.input_text,
        output_summary=record.output_summary,
        error_message=record.error_message,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def run_detail_from_record(record: RunRecord) -> RunDetail:
    return RunDetail(
        **run_summary_from_record(record).model_dump(),
        metadata=dict(record.run_metadata),
    )


def session_summary_from_record(
    record: SessionRecord,
    *,
    run_count: int,
    active_run_ids: list[str],
    latest_run: RunSummary | None,
) -> SessionSummary:
    return SessionSummary(
        id=record.id,
        parent_session_id=record.parent_session_id,
        profile_name=record.profile_name,
        project_id=record.project_id,
        metadata=dict(record.session_metadata),
        created_at=record.created_at,
        updated_at=record.updated_at,
        run_count=run_count,
        active_run_ids=list(active_run_ids),
        latest_run=latest_run,
    )
