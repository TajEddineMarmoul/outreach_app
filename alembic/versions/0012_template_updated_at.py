"""Record template edits without inventing dates for existing templates."""

from alembic import op
import sqlalchemy as sa

revision = "0012_template_updated_at"
down_revision = "0011_campaign_timezone"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("templates", sa.Column("updated_at", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("templates") as batch:
        batch.drop_column("updated_at")
