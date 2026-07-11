from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_sender_is_default"
down_revision = "0001_application_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("senders")}
    if "is_default" not in columns:
        op.add_column("senders", sa.Column("is_default", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("senders")}
    if "is_default" in columns:
        op.drop_column("senders", "is_default")
