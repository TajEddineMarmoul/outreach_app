"""Track Gmail replies, automated responses, and rejected messages.

Revision ID: 0013_gmail_activity
Revises: 0012_template_updated_at
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_gmail_activity"
down_revision = "0012_template_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "senders",
        sa.Column(
            "gmail_tracking_status",
            sa.String(length=40),
            nullable=False,
            server_default="needs_reconnect",
        ),
    )
    op.add_column("senders", sa.Column("gmail_history_id", sa.String(length=255), nullable=True))
    op.add_column("senders", sa.Column("gmail_pending_history_id", sa.String(length=255), nullable=True))
    op.add_column("senders", sa.Column("gmail_watch_expiration_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("senders", sa.Column("gmail_watch_refresh_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("senders", sa.Column("gmail_backfill_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "senders",
        sa.Column("gmail_push_pending", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("senders", sa.Column("gmail_push_locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("senders", sa.Column("gmail_push_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "senders",
        sa.Column("gmail_sync_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "senders",
        sa.Column("gmail_sync_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_senders_email_status", "senders", ["email", "status"])
    op.create_index(
        "ix_senders_gmail_watch_due",
        "senders",
        ["gmail_tracking_status", "gmail_watch_refresh_at"],
    )
    op.create_index(
        "ix_senders_gmail_push_due",
        "senders",
        ["gmail_push_pending", "gmail_push_retry_at"],
    )
    op.add_column(
        "send_log",
        sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "send_log",
        sa.Column("response_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "send_log",
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "send_log",
        sa.Column("response_gmail_message_id", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_send_log_response_status", "send_log", ["response_status"])
    op.create_table(
        "gmail_activity_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(length=255),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.Integer(),
            sa.ForeignKey("senders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "send_log_id",
            sa.Integer(),
            sa.ForeignKey("send_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "sender_id",
            "gmail_message_id",
            "event_type",
            "recipient_email",
            name="uq_gmail_activity_sender_message_type_recipient",
        ),
    )
    op.create_index(
        "ix_gmail_activity_user_occurred",
        "gmail_activity_events",
        ["user_id", "occurred_at"],
    )
    op.create_index(
        "ix_gmail_activity_events_user_id",
        "gmail_activity_events",
        ["user_id"],
    )
    op.create_index(
        "ix_gmail_activity_events_sender_id",
        "gmail_activity_events",
        ["sender_id"],
    )
    op.create_index(
        "ix_gmail_activity_events_send_log_id",
        "gmail_activity_events",
        ["send_log_id"],
    )


def downgrade() -> None:
    op.drop_table("gmail_activity_events")
    with op.batch_alter_table("send_log") as batch:
        batch.drop_index("ix_send_log_response_status")
        batch.drop_column("response_gmail_message_id")
        batch.drop_column("responded_at")
        batch.drop_column("response_status")
        batch.drop_column("bounced_at")
    with op.batch_alter_table("senders") as batch:
        batch.drop_index("ix_senders_gmail_push_due")
        batch.drop_index("ix_senders_gmail_watch_due")
        batch.drop_index("ix_senders_email_status")
        batch.drop_column("gmail_sync_error")
        batch.drop_column("gmail_sync_checked_at")
        batch.drop_column("gmail_push_retry_at")
        batch.drop_column("gmail_push_locked_at")
        batch.drop_column("gmail_push_pending")
        batch.drop_column("gmail_backfill_completed_at")
        batch.drop_column("gmail_watch_refresh_at")
        batch.drop_column("gmail_watch_expiration_at")
        batch.drop_column("gmail_pending_history_id")
        batch.drop_column("gmail_history_id")
        batch.drop_column("gmail_tracking_status")
