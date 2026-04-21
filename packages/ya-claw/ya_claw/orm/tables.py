from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ya_claw.orm.base import Base

_ALLOWED_RUN_STATUSES = ("queued", "running", "completed", "failed", "cancelled")


def utc_now() -> datetime:
    return datetime.now(UTC)


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
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    trigger_type: Mapped[str] = mapped_column(String(32), default="api")
    profile_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[SessionRecord] = relationship(back_populates="runs")
