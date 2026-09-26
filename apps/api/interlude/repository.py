from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from interlude.db import (ArtifactRow, BrandRow, CandidateRow, CreativeRow, DecisionRow, JobRow,
                          SceneRow, TranscriptRow, VideoRow, now)
from interlude.domain import AnalysisJob, JobStatus
from interlude.pipeline import transition_allowed


class Repository:
    def __init__(self, sessions):
        self.sessions = sessions

    def enqueue(self, video_id: str) -> AnalysisJob:
        with self.sessions.begin() as session:
            video = session.get(VideoRow, video_id, with_for_update=True)
            if video is None:
                raise KeyError("video_not_found")
            existing = session.scalars(select(JobRow).where(JobRow.video_id == video_id,
                JobRow.status.not_in(["COMPLETED", "FAILED"]))).first()
            if existing:
                return self.serialize_job(existing)
            job = JobRow(id=str(uuid4()), video_id=video_id, status="QUEUED")
            session.add(job)
            session.flush()
            return self.serialize_job(job)

    @staticmethod
    def serialize_job(row):
        return AnalysisJob(id=row.id, video_id=row.video_id, status=row.status,
                           error_code=row.error_code, error_stage=row.error_stage)

    def claim(self, lease_sec: int):
        with self.sessions.begin() as session:
            stale = session.scalars(select(JobRow).where(JobRow.status.not_in(["QUEUED", "COMPLETED", "FAILED"]),
                JobRow.updated_at < now() - timedelta(seconds=lease_sec)).with_for_update(skip_locked=True)).all()
            for row in stale:
                row.error_stage, row.error_code, row.status = row.status, "worker_lease_expired", "FAILED"
            job = session.scalars(select(JobRow).where(JobRow.status == "QUEUED").order_by(JobRow.created_at)
                                  .with_for_update(skip_locked=True).limit(1)).first()
            if job is None:
                return None
            job.status, job.updated_at = "INGESTING", now()
            video = session.get(VideoRow, job.video_id)
            return job.id, video.id, video.path

    def progress(self, job_id: str, status: JobStatus, error: str | None = None):
        with self.sessions.begin() as session:
            job = session.get(JobRow, job_id, with_for_update=True)
            if not transition_allowed(JobStatus(job.status), status):
                raise ValueError("invalid_job_transition")
            if error:
                job.error_code, job.error_stage = error, job.status
            job.status, job.updated_at = status.value, now()

    def checkpoint(self, job_id: str, kind: str, items: list):
        with self.sessions.begin() as session:
            if kind == "brands":
                for brand in items:
                    session.merge(BrandRow(id=brand.brand_id, payload=brand.model_dump(mode="json")))
                    session.flush()
                    for creative in brand.creatives:
                        session.merge(CreativeRow(id=creative.creative_id, brand_id=brand.brand_id,
                                                 payload=creative.model_dump(mode="json")))
            else:
                table = {"scenes": SceneRow, "transcript": TranscriptRow,
                         "candidates": CandidateRow, "decisions": DecisionRow}[kind]
                session.execute(delete(table).where(table.job_id == job_id))
                session.add_all([table(job_id=job_id, payload=item.model_dump(mode="json")) for item in items])

    def artifacts(self, job_id: str, paths: dict):
        with self.sessions.begin() as session:
            for kind, path in paths.items():
                session.add(ArtifactRow(job_id=job_id, kind=kind, path=str(path.resolve())))
