from fastapi.testclient import TestClient
from interlude.main import create_app
from interlude.config import Settings


def test_health_and_invalid_upload_do_not_need_database(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "alive"}
        assert client.post("/api/videos", files={"file": ("script.py", b"x", "text/plain")}).status_code == 415
        assert client.get("/api/videos/not-a-uuid/media").status_code == 422


def test_upload_limit_rejects_and_removes_partial_file(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, max_upload_mb=1))
    with TestClient(app) as client:
        response = client.post("/api/videos", files={"file": ("video.mp4", b"x" * (1024*1024+1), "video/mp4")})
    assert response.status_code == 413
    assert not list((tmp_path / "uploads").glob("*"))
