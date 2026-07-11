from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_add_autopilot_day_schedules"
down_revision = "0004_add_autopilot_daily_cap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autopilot_day_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.String(length=10), nullable=False),
        sa.Column("daily_cap", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False, server_default="09:00"),
        sa.Column("end_time", sa.String(length=5), nullable=False, server_default="17:00"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "day_of_week", name="uq_autopilot_day_campaign_day"),
    )
    op.create_index(
        "ix_autopilot_day_schedules_campaign",
        "autopilot_day_schedules",
        ["campaign_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_autopilot_day_schedules_campaign", table_name="autopilot_day_schedules")
    op.drop_table("autopilot_day_schedules")
