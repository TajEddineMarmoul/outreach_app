"""Allow multiple attachments per campaign.

Revision ID: 0010_multi_attachments
Revises: 0009_attachments
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_multi_attachments"
down_revision = "0009_attachments"
branch_labels = None
depends_on = None


def _attachment_columns(*, primary_key: str) -> list[sa.Column]:
    return [
        sa.Column(primary_key, sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table("campaign_attachments_multi", *_attachment_columns(primary_key="id"))
    op.execute(
        """
        INSERT INTO campaign_attachments_multi
            (campaign_id, filename, content_type, size_bytes, sha256, content, created_at, updated_at)
        SELECT campaign_id, filename, content_type, size_bytes, sha256, content, created_at, updated_at
        FROM campaign_attachments
        """
    )
    op.drop_table("campaign_attachments")
    op.rename_table("campaign_attachments_multi", "campaign_attachments")
    op.create_index("ix_campaign_attachments_campaign", "campaign_attachments", ["campaign_id"])


def downgrade() -> None:
    op.create_table(
        "campaign_attachments_single",
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
    op.execute(
        """
        INSERT INTO campaign_attachments_single
            (campaign_id, filename, content_type, size_bytes, sha256, content, created_at, updated_at)
        SELECT DISTINCT ON (campaign_id)
            campaign_id, filename, content_type, size_bytes, sha256, content, created_at, updated_at
        FROM campaign_attachments
        ORDER BY campaign_id, id
        """
    )
    op.drop_table("campaign_attachments")
    op.rename_table("campaign_attachments_single", "campaign_attachments")
