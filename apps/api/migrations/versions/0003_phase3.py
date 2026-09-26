"""Durable progress for episode processing."""
from alembic import op
import sqlalchemy as sa

revision = "0003_phase3"
down_revision = "0002_phase2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_jobs", sa.Column("progress_json", sa.JSON, nullable=True))


def downgrade():
    op.drop_column("analysis_jobs", "progress_json")
