from datetime import timedelta
import os
import time
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from interlude.db import Base, JobRow, VideoRow, ArtifactRow, now
from interlude.repository import Repository
from interlude.config import Settings
from interlude.domain import JobStatus
from interlude.runtime import validate_environment, StartupError
from interlude.cleanup import cleanup_media


@pytest.fixture
def database(tmp_path):
    # Transaction/ownership unit tests only. Actual schema/locking also verified on hosted MySQL.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(VideoRow(id="video", path=str(tmp_path/"source.mp4"), metadata_json={}))
    yield factory
    engine.dispose()


def test_job_cannot_be_claimed_twice_and_old_owner_cannot_write(database):
    repo = Repository(database)
    job = repo.enqueue("video")
    claim = repo.claim(900)
    assert claim[0] == job.id and repo.claim(900) is None
    with pytest.raises(ValueError, match="ownership"):
        repo.checkpoint(job.id, "scenes", [], token="not-owner")
    repo.heartbeat(job.id, claim[3])


def test_completed_enqueue_is_idempotent_unless_explicitly_forced(database):
    repo = Repository(database)
    first = repo.enqueue("video")
    with database.begin() as session:
        row = session.get(JobRow, first.id)
        row.status, row.state = "COMPLETED", "COMPLETED"
    assert repo.enqueue("video").id == first.id
    assert repo.enqueue("video", force=True).id != first.id


def test_crashed_job_expires_without_unsafe_reprocessing(database):
    repo = Repository(database)
    job = repo.enqueue("video")
    claim = repo.claim(900)
    with database.begin() as session:
        session.get(JobRow, job.id).updated_at = now()-timedelta(hours=2)
    assert repo.claim(900) is None
    with database() as session:
        row = session.get(JobRow, job.id)
        assert row.status == "FAILED" and row.error_code == "worker_lease_expired"
    with pytest.raises(ValueError):
        repo.progress(job.id, JobStatus.SCENE_DETECTION, token=claim[3])


def test_artifact_registration_is_idempotent(database, tmp_path):
    repo = Repository(database)
    job = repo.enqueue("video")
    claim = repo.claim(900)
    for _ in range(2):
        repo.artifacts(job.id, {"analysis": tmp_path/"analysis.json"}, token=claim[3])
    with database() as session:
        assert len(session.scalars(select(ArtifactRow)).all()) == 1


def test_startup_rejects_missing_service_configuration_without_secrets(tmp_path):
    s = Settings(_env_file=None, data_dir=tmp_path/"data", reports_dir=tmp_path/"reports")
    with pytest.raises(StartupError, match="qwen_configuration_invalid") as error:
        validate_environment(s)
    assert "groq_key_missing" in str(error.value)


def test_cleanup_preserves_active_job_media_and_persistent_ads(database, tmp_path):
    s = Settings(_env_file=None, data_dir=tmp_path, upload_retention_hours=1, work_retention_hours=1)
    s.prepare_dirs()
    source = tmp_path/"uploads"/"video.mp4"
    source.write_bytes(b"video")
    ad = tmp_path/"ads"/"ad.mp4"
    ad.write_bytes(b"ad")
    expired = time.time()-7200
    os.utime(source, (expired, expired))
    os.utime(ad, (expired, expired))
    with database.begin() as session:
        session.get(VideoRow, "video").path = str(source)
    repo = Repository(database)
    job = repo.enqueue("video")
    assert cleanup_media(s, database, apply=True)["paths"] == []
    assert source.exists() and ad.exists()
    with database.begin() as session:
        session.get(JobRow, job.id).status = "FAILED"
    assert str(source) in cleanup_media(s, database, apply=True)["paths"]
    assert not source.exists() and ad.exists()
