"""Store a fixed timezone on each campaign.

Revision ID: 0011_campaign_timezone
Revises: 0010_multi_attachments
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_campaign_timezone"
down_revision = "0010_multi_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("timezone", sa.String(length=80), nullable=True))
    op.execute(
        """
        UPDATE campaigns
        SET timezone = COALESCE(
            (SELECT user_settings.timezone
             FROM user_settings
             WHERE user_settings.user_id = campaigns.user_id),
            'UTC'
        )
        WHERE timezone IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("campaigns") as batch_op:
        batch_op.drop_column("timezone")
