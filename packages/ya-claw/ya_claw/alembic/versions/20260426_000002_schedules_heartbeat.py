from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260426_000002"
down_revision = "20260425_000001"
branch_labels = None
depends_on = None

_ALLOWED_SCHEDULE_STATUSES = ("active", "paused", "deleted")
_ALLOWED_SCHEDULE_EXECUTION_MODES = ("continue_session", "fork_session", "isolate_session")
_ALLOWED_SCHEDULE_ACTIVE_POLICIES = ("steer", "queue")
_ALLOWED_SCHEDULE_FIRE_STATUSES = ("pending", "submitted", "steered", "skipped", "failed")
_ALLOWED_HEARTBEAT_FIRE_STATUSES = ("pending", "submitted", "skipped", "failed")


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("owner_kind", sa.String(length=32), nullable=True),
        sa.Column("owner_session_id", sa.String(length=32), nullable=True),
        sa.Column("owner_run_id", sa.String(length=32), nullable=True),
        sa.Column("profile_name", sa.String(length=255), nullable=True),
        sa.Column("cron_expr", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_mode", sa.String(length=32), nullable=True),
        sa.Column("target_session_id", sa.String(length=32), nullable=True),
        sa.Column("source_session_id", sa.String(length=32), nullable=True),
        sa.Column("on_active", sa.String(length=32), nullable=True),
        sa.Column("input_parts_template", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("last_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fire_id", sa.String(length=32), nullable=True),
        sa.Column("last_session_id", sa.String(length=32), nullable=True),
        sa.Column("last_run_id", sa.String(length=32), nullable=True),
        sa.Column("fire_count", sa.Integer(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN {_ALLOWED_SCHEDULE_STATUSES!s}", name="ck_schedules_status"),
        sa.CheckConstraint(
            f"execution_mode IN {_ALLOWED_SCHEDULE_EXECUTION_MODES!s}",
            name="ck_schedules_execution_mode",
        ),
        sa.CheckConstraint(f"on_active IN {_ALLOWED_SCHEDULE_ACTIVE_POLICIES!s}", name="ck_schedules_on_active"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedules_due", "schedules", ["status", "next_fire_at"])
    op.create_index("ix_schedules_owner_session", "schedules", ["owner_session_id"])
    op.create_index("ix_schedules_target_session", "schedules", ["target_session_id"])
    op.create_index("ix_schedules_source_session", "schedules", ["source_session_id"])

    op.create_table(
        "schedule_fires",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("schedule_id", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("target_session_id", sa.String(length=32), nullable=True),
        sa.Column("source_session_id", sa.String(length=32), nullable=True),
        sa.Column("created_session_id", sa.String(length=32), nullable=True),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("active_run_id", sa.String(length=32), nullable=True),
        sa.Column("input_parts", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN {_ALLOWED_SCHEDULE_FIRE_STATUSES!s}", name="ck_schedule_fires_status"),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "dedupe_key", name="uq_schedule_fires_dedupe"),
    )
    op.create_index("ix_schedule_fires_schedule_created", "schedule_fires", ["schedule_id", "created_at"])
    op.create_index("ix_schedule_fires_status_scheduled", "schedule_fires", ["status", "scheduled_at"])
    op.create_index("ix_schedule_fires_run", "schedule_fires", ["run_id"])

    op.create_table(
        "heartbeat_fires",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=True),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN {_ALLOWED_HEARTBEAT_FIRE_STATUSES!s}", name="ck_heartbeat_fires_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_heartbeat_fires_dedupe"),
    )
    op.create_index("ix_heartbeat_fires_status_scheduled", "heartbeat_fires", ["status", "scheduled_at"])
    op.create_index("ix_heartbeat_fires_run", "heartbeat_fires", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_heartbeat_fires_run", table_name="heartbeat_fires")
    op.drop_index("ix_heartbeat_fires_status_scheduled", table_name="heartbeat_fires")
    op.drop_table("heartbeat_fires")
    op.drop_index("ix_schedule_fires_run", table_name="schedule_fires")
    op.drop_index("ix_schedule_fires_status_scheduled", table_name="schedule_fires")
    op.drop_index("ix_schedule_fires_schedule_created", table_name="schedule_fires")
    op.drop_table("schedule_fires")
    op.drop_index("ix_schedules_source_session", table_name="schedules")
    op.drop_index("ix_schedules_target_session", table_name="schedules")
    op.drop_index("ix_schedules_owner_session", table_name="schedules")
    op.drop_index("ix_schedules_due", table_name="schedules")
    op.drop_table("schedules")
