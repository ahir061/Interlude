from datetime import datetime, timezone
import time
import pymysql

from sqlalchemy import (JSON, DateTime, ForeignKey, Index, Integer, String, Text,
                        create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from interlude.config import Settings


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class VideoRow(Base):
    __tablename__ = "videos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    path: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class JobRow(Base):
    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    state: Mapped[str] = mapped_column(String(16), default="QUEUED", server_default="QUEUED")
    lease_token: Mapped[str | None] = mapped_column(String(36))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_stage: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_analysis_jobs_status_created", "status", "created_at"),)


class AnalysisItem:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class SceneRow(AnalysisItem, Base):
    __tablename__ = "scenes"


class ShotRow(AnalysisItem, Base):
    __tablename__ = "raw_shots"


class ObservationRow(AnalysisItem, Base):
    __tablename__ = "semantic_observations"


class TranscriptRow(AnalysisItem, Base):
    __tablename__ = "transcript_segments"


class CandidateRow(AnalysisItem, Base):
    __tablename__ = "break_candidates"


class DecisionRow(AnalysisItem, Base):
    __tablename__ = "break_decisions"


class BrandRow(Base):
    __tablename__ = "brands"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class CreativeRow(Base):
    __tablename__ = "creatives"
    brand_id: Mapped[str] = mapped_column(ForeignKey("brands.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(Text)


def connect_with_retry(connect, sleep=time.sleep):
    """Retry only opening a connection; never replay an ambiguous transaction."""
    for attempt in range(3):
        try:
            return connect()
        except pymysql.OperationalError as exc:
            if not exc.args or exc.args[0] not in (2002, 2003, 2006, 2013) or attempt == 2:
                raise
            sleep(2**attempt)


def make_engine(settings: Settings):
    engine = create_engine(settings.database_url(), pool_pre_ping=True, pool_recycle=1800,
                         connect_args={"connect_timeout": 10, "read_timeout": 30, "write_timeout": 30},
                         hide_parameters=True)
    @event.listens_for(engine, "do_connect")
    def connect(dialect, connection_record, args, kwargs):
        return connect_with_retry(lambda: dialect.connect(*args, **kwargs))
    return engine


def sessions(settings: Settings):
    return sessionmaker(bind=make_engine(settings), expire_on_commit=False)
