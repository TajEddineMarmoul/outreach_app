"""Make imported campaign recipients immediately eligible.

Revision ID: 0008_import_ready
Revises: 0007_platform_nullability
"""

from alembic import op


revision = "0008_import_ready"
down_revision = "0007_platform_nullability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE contacts AS c
        SET status = 'approved', updated_at = now()
        WHERE c.status = 'pending'
          AND EXISTS (
              SELECT 1
              FROM campaign_recipients AS cr
              WHERE cr.contact_id = c.id
                AND cr.status = 'pending'
          )
        """
    )
    op.execute(
        """
        UPDATE campaign_recipients AS cr
        SET status = 'approved', updated_at = now()
        FROM contacts AS c
        WHERE cr.contact_id = c.id
          AND cr.status = 'pending'
          AND c.status IN ('approved', 'sent')
        """
    )


def downgrade() -> None:
    pass
