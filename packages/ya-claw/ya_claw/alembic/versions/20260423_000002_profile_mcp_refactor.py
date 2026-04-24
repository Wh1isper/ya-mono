from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260423_000002"
down_revision = "20260421_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.alter_column("toolsets", new_column_name="builtin_toolsets", existing_type=sa.JSON())
        batch_op.add_column(sa.Column("enabled_mcps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch_op.add_column(sa.Column("disabled_mcps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch_op.alter_column("enabled_mcps", server_default=None)
        batch_op.alter_column("disabled_mcps", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_column("disabled_mcps")
        batch_op.drop_column("enabled_mcps")
        batch_op.alter_column("builtin_toolsets", new_column_name="toolsets", existing_type=sa.JSON())
