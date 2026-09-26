"""Conservative retention cleanup; active jobs protect both sources and scratch data."""
import argparse
import json
import shutil
import time
from pathlib import Path

from sqlalchemy import select
from interlude.config import get_settings
from interlude.db import JobRow, VideoRow, sessions


def cleanup_media(settings, session_factory, apply=False, now_sec=None):
    now_sec = time.time() if now_sec is None else now_sec
    targets = []
    # Hold video rows while choosing/removing sources so enqueue cannot race deletion.
    with session_factory.begin() as session:
        videos = session.scalars(select(VideoRow).with_for_update()).all()
        active = set(session.scalars(select(JobRow.video_id).where(JobRow.status.not_in(["COMPLETED", "FAILED"]))).all())
        for video in videos:
            path = Path(video.path)
            if video.id in active or not path.exists() or path.is_symlink():
                continue
            if not path.resolve().is_relative_to((settings.data_dir/"uploads").resolve()):
                continue
            if now_sec-path.stat().st_mtime > settings.upload_retention_hours*3600:
                targets.append(str(path))
                if apply:
                    path.unlink()
        for path in (settings.data_dir/"work").iterdir():
            if path.is_symlink() or any(path.name.startswith(video) for video in active):
                continue
            if now_sec-path.stat().st_mtime > settings.work_retention_hours*3600:
                targets.append(str(path))
                if apply:
                    shutil.rmtree(path) if path.is_dir() else path.unlink()
    return {"applied": apply, "paths": targets}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Delete expired inactive uploads/scratch; default is dry-run")
    args = parser.parse_args()
    settings = get_settings()
    settings.prepare_dirs()
    try:
        print(json.dumps(cleanup_media(settings, sessions(settings), args.apply)))
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
