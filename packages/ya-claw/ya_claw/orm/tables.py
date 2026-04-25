from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ya_claw.orm.base import Base

_ALLOWED_RUN_STATUSES = ("queued", "running", "completed", "failed", "cancelled")


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProfileRecord(Base):
    __tablename__ = "profiles"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    model_settings_preset: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_settings_override: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model_config_preset: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_config_override: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    builtin_toolsets: Mapped[list[str]] = mapped_column(JSON, default=list)
    subagents: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    include_builtin_subagents: Mapped[bool] = mapped_column(Boolean, default=False)
    unified_subagents: Mapped[bool] = mapped_column(Boolean, default=False)
    need_user_approve_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    need_user_approve_mcps: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled_mcps: Mapped[list[str]] = mapped_column(JSON, default=list)
    disabled_mcps: Mapped[list[str]] = mapped_column(JSON, default=list)
    workspace_backend_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    head_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    head_success_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    parent: Mapped[SessionRecord | None] = relationship(remote_side=lambda: [SessionRecord.id])
    runs: Mapped[list[RunRecord]] = relationship(back_populates="session", cascade="all, delete-orphan")


class RunRecord(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_ALLOWED_RUN_STATUSES!s}",
            name="ck_runs_status",
        ),
        Index("ix_runs_session_created_at", "session_id", "created_at"),
        Index("ix_runs_session_sequence_no", "session_id", "sequence_no", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    restore_from_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    trigger_type: Mapped[str] = mapped_column(String(32), default="api")
    profile_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_parts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    run_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[SessionRecord] = relationship(back_populates="runs")


class RuntimeInstanceRecord(Base):
    __tablename__ = "runtime_instances"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    instance_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
