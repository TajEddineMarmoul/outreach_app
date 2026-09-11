"""Add first-party email open and link-click tracking.

Revision ID: 0014_email_engagement
Revises: 0013_gmail_activity
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_email_engagement"
down_revision = "0013_gmail_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "engagement_tracking_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column("send_log", sa.Column("tracking_token", sa.String(length=255), nullable=True))
    op.add_column("send_log", sa.Column("first_opened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("send_log", sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "send_log",
        sa.Column("open_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("send_log", sa.Column("first_clicked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("send_log", sa.Column("last_clicked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "send_log",
        sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint("uq_send_log_tracking_token", "send_log", ["tracking_token"])
    op.create_index("ix_send_log_tracking_token", "send_log", ["tracking_token"])
    op.create_table(
        "email_tracking_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "send_log_id",
            sa.Integer(),
            sa.ForeignKey("send_log.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token", name="uq_email_tracking_links_token"),
    )
    op.create_index("ix_email_tracking_links_send_log", "email_tracking_links", ["send_log_id"])
    op.create_table(
        "email_tracking_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(length=255),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "send_log_id",
            sa.Integer(),
            sa.ForeignKey("send_log.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("link_url", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_email_tracking_events_send_log_occurred",
        "email_tracking_events",
        ["send_log_id", "occurred_at"],
    )
    op.create_index(
        "ix_email_tracking_events_user_occurred",
        "email_tracking_events",
        ["user_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_tracking_events_user_occurred", table_name="email_tracking_events")
    op.drop_index("ix_email_tracking_events_send_log_occurred", table_name="email_tracking_events")
    op.drop_table("email_tracking_events")
    op.drop_index("ix_email_tracking_links_send_log", table_name="email_tracking_links")
    op.drop_table("email_tracking_links")
    op.drop_index("ix_send_log_tracking_token", table_name="send_log")
    op.drop_constraint("uq_send_log_tracking_token", "send_log", type_="unique")
    op.drop_column("send_log", "click_count")
    op.drop_column("send_log", "last_clicked_at")
    op.drop_column("send_log", "first_clicked_at")
    op.drop_column("send_log", "open_count")
    op.drop_column("send_log", "last_opened_at")
    op.drop_column("send_log", "first_opened_at")
    op.drop_column("send_log", "tracking_token")
    op.drop_column("campaigns", "engagement_tracking_enabled")
