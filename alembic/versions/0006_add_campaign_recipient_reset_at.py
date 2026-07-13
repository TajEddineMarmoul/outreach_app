from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_add_campaign_recipient_reset_at"
down_revision = "0005_add_autopilot_day_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("campaign_recipients")}
    if "reset_at" not in columns:
        op.add_column("campaign_recipients", sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("campaign_recipients")}
    if "reset_at" in columns:
        op.drop_column("campaign_recipients", "reset_at")
