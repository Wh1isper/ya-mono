from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260425_000005"
down_revision = "20260425_000004"
branch_labels = None
depends_on = None


_ALLOWED_BRIDGE_EVENT_STATUSES = ("received", "queued", "submitted", "duplicate", "failed")


def upgrade() -> None:
    op.create_table(
        "bridge_conversations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("adapter", sa.String(length=32), nullable=False),
        sa.Column("tenant_key", sa.String(length=255), nullable=False),
        sa.Column("external_chat_id", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("profile_name", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adapter", "tenant_key", "external_chat_id", name="uq_bridge_conversations_chat"),
    )
    op.create_index("ix_bridge_conversations_session_id", "bridge_conversations", ["session_id"])

    op.create_table(
        "bridge_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("adapter", sa.String(length=32), nullable=False),
        sa.Column("tenant_key", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("external_chat_id", sa.String(length=255), nullable=True),
        sa.Column("conversation_id", sa.String(length=32), nullable=True),
        sa.Column("session_id", sa.String(length=32), nullable=True),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("raw_event", sa.JSON(), nullable=True),
        sa.Column("normalized_event", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN {_ALLOWED_BRIDGE_EVENT_STATUSES!s}", name="ck_bridge_events_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adapter", "tenant_key", "event_id", name="uq_bridge_events_event"),
        sa.UniqueConstraint("adapter", "tenant_key", "external_message_id", name="uq_bridge_events_message"),
    )
    op.create_index("ix_bridge_events_chat_created_at", "bridge_events", ["external_chat_id", "created_at"])
    op.create_index("ix_bridge_events_run_id", "bridge_events", ["run_id"])
    op.create_index("ix_bridge_events_session_id", "bridge_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_bridge_events_session_id", table_name="bridge_events")
    op.drop_index("ix_bridge_events_run_id", table_name="bridge_events")
    op.drop_index("ix_bridge_events_chat_created_at", table_name="bridge_events")
    op.drop_table("bridge_events")
    op.drop_index("ix_bridge_conversations_session_id", table_name="bridge_conversations")
    op.drop_table("bridge_conversations")
