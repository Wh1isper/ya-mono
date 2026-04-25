from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260425_000003"
down_revision = "20260423_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_instances",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("process_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("claimed_by", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("claimed_by")
    op.drop_table("runtime_instances")
