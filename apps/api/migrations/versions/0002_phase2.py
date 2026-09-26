"""Persist raw shots/semantic observations and fenced worker ownership."""
from alembic import op
import sqlalchemy as sa

revision = "0002_phase2"
down_revision = "0001_phase1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_jobs", sa.Column("state", sa.String(16), nullable=False, server_default="QUEUED"))
    op.add_column("analysis_jobs", sa.Column("lease_token", sa.String(36)))
    op.add_column("analysis_jobs", sa.Column("heartbeat_at", sa.DateTime))
    op.execute("UPDATE analysis_jobs SET state = CASE WHEN status IN ('QUEUED','COMPLETED','FAILED') THEN status ELSE 'PROCESSING' END")
    for table in ("raw_shots", "semantic_observations"):
        op.create_table(table, sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False))
        op.create_index(f"ix_{table}_job_id", table, ["job_id"])


def downgrade():
    for table in ("semantic_observations", "raw_shots"):
        op.drop_table(table)
    for column in ("heartbeat_at", "lease_token", "state"):
        op.drop_column("analysis_jobs", column)
