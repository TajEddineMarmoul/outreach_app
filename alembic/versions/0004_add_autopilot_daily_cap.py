from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_add_autopilot_daily_cap"
down_revision = "0003_platform_delivery_compat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("autopilot_daily_cap", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "autopilot_daily_cap")
