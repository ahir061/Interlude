"""Phase 1 metadata and analysis tables. No media binaries."""
from alembic import op
import sqlalchemy as sa

revision = "0001_phase1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("videos", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("path", sa.Text, nullable=False), sa.Column("metadata_json", sa.JSON, nullable=False),
                    sa.Column("created_at", sa.DateTime, nullable=False))
    op.create_table("analysis_jobs", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("video_id", sa.String(36), sa.ForeignKey("videos.id"), nullable=False),
                    sa.Column("status", sa.String(32), nullable=False), sa.Column("error_code", sa.String(120)),
                    sa.Column("error_stage", sa.String(32)), sa.Column("created_at", sa.DateTime, nullable=False),
                    sa.Column("updated_at", sa.DateTime, nullable=False))
    op.create_index("ix_analysis_jobs_video_id", "analysis_jobs", ["video_id"])
    op.create_index("ix_analysis_jobs_status_created", "analysis_jobs", ["status", "created_at"])
    for table in ("scenes", "transcript_segments", "break_candidates", "break_decisions"):
        op.create_table(table, sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False))
        op.create_index(f"ix_{table}_job_id", table, ["job_id"])
    op.create_table("brands", sa.Column("id", sa.String(96), primary_key=True),
                    sa.Column("payload", sa.JSON, nullable=False))
    op.create_table("creatives", sa.Column("brand_id", sa.String(96), sa.ForeignKey("brands.id"), primary_key=True),
                    sa.Column("id", sa.String(96), primary_key=True), sa.Column("payload", sa.JSON, nullable=False))
    op.create_table("artifacts", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False), sa.Column("path", sa.Text, nullable=False))
    op.create_index("ix_artifacts_job_id", "artifacts", ["job_id"])


def downgrade():
    for table in ("artifacts", "creatives", "brands", "break_decisions", "break_candidates",
                  "transcript_segments", "scenes", "analysis_jobs", "videos"):
        op.drop_table(table)
