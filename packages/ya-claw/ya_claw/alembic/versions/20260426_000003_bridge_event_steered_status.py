from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260426_000003"
down_revision = "20260426_000002"
branch_labels = None
depends_on = None

_OLD_ALLOWED_BRIDGE_EVENT_STATUSES = ("received", "queued", "submitted", "duplicate", "failed")
_NEW_ALLOWED_BRIDGE_EVENT_STATUSES = ("received", "queued", "submitted", "steered", "duplicate", "failed")


def upgrade() -> None:
    _replace_bridge_event_status_constraint(_NEW_ALLOWED_BRIDGE_EVENT_STATUSES)


def downgrade() -> None:
    op.execute("UPDATE bridge_events SET status = 'submitted' WHERE status = 'steered'")
    _replace_bridge_event_status_constraint(_OLD_ALLOWED_BRIDGE_EVENT_STATUSES)


def _replace_bridge_event_status_constraint(allowed_statuses: tuple[str, ...]) -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "sqlite":
        with op.batch_alter_table("bridge_events") as batch_op:
            batch_op.drop_constraint("ck_bridge_events_status", type_="check")
            batch_op.create_check_constraint(
                "ck_bridge_events_status",
                f"status IN {allowed_statuses!s}",
            )
        return

    op.drop_constraint("ck_bridge_events_status", "bridge_events", type_="check")
    op.create_check_constraint(
        "ck_bridge_events_status",
        "bridge_events",
        sa.column("status").in_(allowed_statuses),
    )
