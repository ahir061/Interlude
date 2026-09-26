import json
import logging
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, text

from interlude.config import Settings, get_settings
from interlude.db import (ArtifactRow, CandidateRow, DecisionRow, JobRow, SceneRow, TranscriptRow,
                          VideoRow, sessions)
from interlude.repository import Repository
from interlude.services.brands import load_brands
from interlude.services.media import MediaError, MediaProbeService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.prepare_dirs()
    session_factory = sessions(settings)
    repo = Repository(session_factory)
    app = FastAPI(title="Interlude", debug=False)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def safe_errors(request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            logging.getLogger("interlude.api").error(json.dumps({"event": "request_failed",
                                                                 "error_type": type(exc).__name__}))
            return JSONResponse({"detail": "internal_error"}, status_code=500)

    @app.get("/health")
    def health():
        return {"status": "alive"}

    @app.get("/ready")
    def ready():
        checks = {"ffmpeg": shutil.which(settings.ffmpeg_bin) is not None,
                  "ffprobe": shutil.which(settings.ffprobe_bin) is not None,
                  "groq_config": bool(settings.groq_api_key.get_secret_value()),
                  "qwen_config": bool(settings.llm_api_url and settings.llm_model and
                                      settings.llm_api_key.get_secret_value())}
        try:
            load_brands(settings.brands_path)
            checks["brands"] = True
        except Exception:
            checks["brands"] = False
        try:
            with session_factory() as session:
                checks["database"] = session.execute(text("SELECT 1")).scalar() == 1
                checks["migrations"] = session.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001_phase1"
        except Exception:
            checks["database"] = False
            checks["migrations"] = False
        return JSONResponse({"ready": all(checks.values()), "checks": checks},
                            status_code=200 if all(checks.values()) else 503)

    @app.post("/api/videos", status_code=202)
    def upload(file: UploadFile = File(...)):
        if not file.filename or Path(file.filename).suffix.lower() != ".mp4":
            raise HTTPException(415, "mp4_required")
        video_id = str(uuid4())
        path = settings.data_dir / "uploads" / f"{video_id}.mp4"
        try:
            total = 0
            with path.open("xb") as target:
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > settings.max_upload_mb * 1024 * 1024:
                        raise HTTPException(413, "upload_limit_exceeded")
                    target.write(chunk)
            try:
                metadata = MediaProbeService(settings).probe(path, video_id)
            except (MediaError, ValueError, KeyError):
                raise HTTPException(422, "invalid_mp4") from None
            if not metadata.has_audio:
                raise HTTPException(422, "audio_required_for_dialogue_safety")
            if metadata.duration_sec > settings.max_video_duration_sec:
                raise HTTPException(422, "video_exceeds_phase1_duration_limit")
            if metadata.codec != "h264":
                raise HTTPException(415, "phase1_requires_h264_mp4")
            with session_factory.begin() as session:
                session.add(VideoRow(id=video_id, path=str(path.resolve()), metadata_json=metadata.model_dump()))
                job = JobRow(id=str(uuid4()), video_id=video_id, status="QUEUED")
                session.flush()
                session.add(job)
            return {"video": metadata, "job": repo.serialize_job(job)}
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            file.file.close()

    @app.post("/api/videos/{video_id}/analyze", status_code=202)
    def analyze(video_id: UUID):
        try:
            return repo.enqueue(str(video_id))
        except KeyError:
            raise HTTPException(404, "video_not_found") from None

    @app.get("/api/jobs/{job_id}")
    def job(job_id: UUID):
        with session_factory() as session:
            row = session.get(JobRow, str(job_id))
            if not row:
                raise HTTPException(404, "job_not_found")
            return repo.serialize_job(row)

    @app.get("/api/videos/{video_id}/media")
    def media(video_id: UUID):
        with session_factory() as session:
            row = session.get(VideoRow, str(video_id))
            if not row or not Path(row.path).is_file():
                raise HTTPException(404, "video_not_found")
            return FileResponse(row.path, media_type="video/mp4")

    def artifact(video_id: UUID, kind: str):
        with session_factory() as session:
            row = session.scalars(select(JobRow).where(JobRow.video_id == str(video_id))
                                  .order_by(JobRow.created_at.desc(), JobRow.id.desc())).first()
            if not row:
                raise HTTPException(404, "analysis_not_found")
            if row.status != "COMPLETED":
                if kind != "debug":
                    raise HTTPException(409, "analysis_not_completed")
                return {"job": repo.serialize_job(row).model_dump(), **{name: [item.payload for item in
                    session.scalars(select(table).where(table.job_id == row.id)).all()] for name, table in
                    (("scenes", SceneRow), ("transcript_segments", TranscriptRow),
                     ("candidates", CandidateRow), ("decisions", DecisionRow))}}
            item = session.scalars(select(ArtifactRow).where(ArtifactRow.job_id == row.id,
                                                             ArtifactRow.kind == kind)).first()
            if not item or not Path(item.path).is_file():
                raise HTTPException(404, "artifact_not_found")
            return FileResponse(item.path, media_type="application/json")

    @app.get("/api/videos/{video_id}/analysis")
    def analysis(video_id: UUID):
        return artifact(video_id, "analysis")

    @app.get("/api/videos/{video_id}/debug")
    def debug(video_id: UUID):
        return artifact(video_id, "debug")

    @app.get("/api/brands")
    def brands():
        return [b.model_dump() for b in load_brands(settings.brands_path)]

    @app.get("/api/ads/{brand_id}/{creative_id}")
    def ad(brand_id: str, creative_id: str):
        import re
        if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", x) for x in (brand_id, creative_id)):
            raise HTTPException(404, "creative_not_found")
        target = (settings.data_dir / "ads" / brand_id / f"{creative_id}.mp4").resolve()
        if not target.is_relative_to((settings.data_dir / "ads").resolve()) or not target.is_file():
            raise HTTPException(404, "creative_not_found")
        return FileResponse(target, media_type="video/mp4")

    return app


app = create_app()
