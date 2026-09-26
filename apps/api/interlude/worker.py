import json
import logging
import time
import signal
from threading import Event, Thread
from pathlib import Path

from interlude.config import get_settings
from interlude.db import sessions
from interlude.domain import JobStatus
from interlude.phase2_pipeline import Phase2Pipeline
from interlude.providers.base import ProviderError
from interlude.repository import Repository
from interlude.services.manifest import ManifestService
from interlude.services.media import MediaError

logger = logging.getLogger("interlude.worker")


def process_job(repository: Repository, pipeline: Phase2Pipeline, claimed: tuple):
    job_id, video_id, path, token = claimed
    stopped, lost = Event(), Event()
    def heartbeat():
        while not stopped.wait(pipeline.settings.worker_heartbeat_sec):
            try:
                repository.heartbeat(job_id, token)
            except Exception:
                lost.set()
                return
    pulse = Thread(target=heartbeat, daemon=True)
    pulse.start()
    try:
        def progress(stage):
            if lost.is_set():
                raise ValueError("job_ownership_lost")
            repository.progress(job_id, stage, token=token)
            logger.info(json.dumps({"event": "job_stage", "job_id": job_id, "stage": stage.value}))
        result = pipeline.run(video_id, Path(path), progress,
                              lambda kind, items: repository.checkpoint(job_id, kind, items, token=token), job_id=job_id)
        repository.heartbeat(job_id, token)
        artifact_started = time.perf_counter()
        output = pipeline.settings.data_dir / "outputs" / job_id
        artifacts = ManifestService(pipeline.settings.media_base_url).write(result, output)
        result.run_metadata["processing_timings_sec"]["artifact_generation"] = time.perf_counter()-artifact_started
        result.run_metadata["processing_timings_sec"]["total_runtime"] = (
            result.run_metadata["processing_timings_sec"]["total_pipeline"] + time.perf_counter()-artifact_started)
        ManifestService(pipeline.settings.media_base_url).write(result, output)
        repository.artifacts(job_id, artifacts, token=token)
        repository.progress(job_id, JobStatus.COMPLETED, token=token)
        logger.info(json.dumps({"event": "job_completed", "job_id": job_id,
                               "summary": ManifestService().build(result).summary}))
    except Exception as exc:
        code = exc.code if isinstance(exc, ProviderError) else (
            str(exc) if isinstance(exc, MediaError) else f"pipeline_{type(exc).__name__}")
        try:
            repository.progress(job_id, JobStatus.FAILED, code, token=token)
        except Exception:
            logger.error(json.dumps({"event": "job_failure_persistence_failed", "job_id": job_id}))
        # Never serialize exception text, provider payloads, request headers or connection details.
        logger.error(json.dumps({"event": "job_failed", "job_id": job_id, "error_code": code}))
    finally:
        stopped.set()
        pulse.join(timeout=35)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    from interlude.runtime import validate_environment
    validate_environment(settings)
    repo = Repository(sessions(settings))
    pipeline = Phase2Pipeline(settings)
    shutdown = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: shutdown.set())
    while not shutdown.is_set():
        try:
            (settings.data_dir / "worker-heartbeat").write_text(str(time.time()))
            claimed = repo.claim(settings.worker_lease_sec)
            if claimed:
                process_job(repo, pipeline, claimed)
            else:
                shutdown.wait(1)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            logger.error(json.dumps({"event": "worker_error", "error_type": type(exc).__name__}))
            shutdown.wait(5)


if __name__ == "__main__":
    main()
