from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260421_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("name", sa.String(length=255), primary_key=True),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("model_settings_preset", sa.String(length=255), nullable=True),
        sa.Column("model_settings_override", sa.JSON(), nullable=True),
        sa.Column("model_config_preset", sa.String(length=255), nullable=True),
        sa.Column("model_config_override", sa.JSON(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("toolsets", sa.JSON(), nullable=False),
        sa.Column("subagents", sa.JSON(), nullable=False),
        sa.Column("include_builtin_subagents", sa.Boolean(), nullable=False),
        sa.Column("unified_subagents", sa.Boolean(), nullable=False),
        sa.Column("need_user_approve_tools", sa.JSON(), nullable=False),
        sa.Column("need_user_approve_mcps", sa.JSON(), nullable=False),
        sa.Column("workspace_backend_hint", sa.String(length=32), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("source_checksum", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "parent_session_id", sa.String(length=32), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("profile_name", sa.String(length=255), nullable=True),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("head_run_id", sa.String(length=32), nullable=True),
        sa.Column("head_success_run_id", sa.String(length=32), nullable=True),
        sa.Column("active_run_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("restore_from_run_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("profile_name", sa.String(length=255), nullable=True),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("input_parts", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("termination_reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_runs_status",
        ),
    )
    op.create_index("ix_runs_session_id", "runs", ["session_id"], unique=False)
    op.create_index("ix_runs_session_created_at", "runs", ["session_id", "created_at"], unique=False)
    op.create_index("ix_runs_session_sequence_no", "runs", ["session_id", "sequence_no"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_runs_session_sequence_no", table_name="runs")
    op.drop_index("ix_runs_session_created_at", table_name="runs")
    op.drop_index("ix_runs_session_id", table_name="runs")
    op.drop_table("runs")
    op.drop_table("sessions")
    op.drop_table("profiles")
