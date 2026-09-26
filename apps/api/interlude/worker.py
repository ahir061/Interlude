import json
import logging
import time
from pathlib import Path

from interlude.config import get_settings
from interlude.db import sessions
from interlude.domain import JobStatus
from interlude.pipeline import AnalysisPipeline
from interlude.providers.base import ProviderError
from interlude.repository import Repository
from interlude.services.manifest import ManifestService
from interlude.services.media import MediaError

logger = logging.getLogger("interlude.worker")


def process_job(repository: Repository, pipeline: AnalysisPipeline, claimed: tuple):
    job_id, video_id, path = claimed
    try:
        def progress(stage):
            repository.progress(job_id, stage)
            logger.info(json.dumps({"event": "job_stage", "job_id": job_id, "stage": stage.value}))
        result = pipeline.run(video_id, Path(path), progress,
                              lambda kind, items: repository.checkpoint(job_id, kind, items))
        artifacts = ManifestService().write(result, pipeline.settings.data_dir / "outputs" / job_id)
        repository.artifacts(job_id, artifacts)
        repository.progress(job_id, JobStatus.COMPLETED)
        logger.info(json.dumps({"event": "job_completed", "job_id": job_id,
                               "summary": ManifestService().build(result).summary}))
    except Exception as exc:
        code = exc.code if isinstance(exc, ProviderError) else (
            str(exc) if isinstance(exc, MediaError) else f"pipeline_{type(exc).__name__}")
        repository.progress(job_id, JobStatus.FAILED, code)
        # Never serialize exception text, provider payloads, request headers or connection details.
        logger.error(json.dumps({"event": "job_failed", "job_id": job_id, "error_code": code}))


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    repo = Repository(sessions(settings))
    pipeline = AnalysisPipeline(settings)
    while True:
        try:
            claimed = repo.claim(settings.worker_lease_sec)
            if claimed:
                process_job(repo, pipeline, claimed)
            else:
                time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            logger.error(json.dumps({"event": "worker_error", "error_type": type(exc).__name__}))
            time.sleep(5)


if __name__ == "__main__":
    main()
