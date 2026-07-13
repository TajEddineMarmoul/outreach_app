from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_platform_nullability"
down_revision = "0006_recipient_reset_at"
branch_labels = None
depends_on = None


def _assert_no_nulls(table_name: str, column_name: str) -> None:
    count = op.get_bind().execute(
        sa.text(f'SELECT count(*) FROM "{table_name}" WHERE "{column_name}" IS NULL')
    ).scalar_one()
    if count:
        raise RuntimeError(
            f"Cannot require {table_name}.{column_name}: {count} rows still contain NULL"
        )


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("The application schema migration requires PostgreSQL.")

    # These are obsolete file-token senders from before group-owned encrypted
    # credentials. They cannot send and are not valid Platform sender records.
    op.execute(
        """
        DELETE FROM senders
        WHERE group_id IS NULL
          AND encrypted_oauth_credentials IS NULL
          AND NOT EXISTS (SELECT 1 FROM send_jobs WHERE send_jobs.sender_id = senders.id)
          AND NOT EXISTS (SELECT 1 FROM send_log WHERE send_log.sender_id = senders.id)
        """
    )

    required_columns = (
        ("campaigns", "user_id"),
        ("contacts", "user_id"),
        ("contacts", "source_type"),
        ("contacts", "source_url"),
        ("send_log", "user_id"),
        ("senders", "user_id"),
        ("senders", "group_id"),
        ("senders", "display_name"),
    )
    for table_name, column_name in required_columns:
        _assert_no_nulls(table_name, column_name)
        op.alter_column(table_name, column_name, nullable=False)


def downgrade() -> None:
    for table_name, column_name in (
        ("campaigns", "user_id"),
        ("contacts", "user_id"),
        ("contacts", "source_type"),
        ("contacts", "source_url"),
        ("send_log", "user_id"),
        ("senders", "user_id"),
        ("senders", "group_id"),
        ("senders", "display_name"),
    ):
        op.alter_column(table_name, column_name, nullable=True)
