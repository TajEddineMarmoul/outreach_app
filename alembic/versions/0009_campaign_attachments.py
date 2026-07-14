"""Store campaign attachments durably.

Revision ID: 0009_attachments
Revises: 0008_import_ready
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_attachments"
down_revision = "0008_import_ready"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_attachments",
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("campaign_attachments")
