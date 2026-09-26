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


def test_oversized_chunked_upload_is_rejected_before_full_multipart_spooling(tmp_path):
    app=create_app(Settings(_env_file=None,data_dir=tmp_path,max_upload_mb=1))
    def body():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="video.mp4"\r\nContent-Type: video/mp4\r\n\r\n'
        for _ in range(4):
            yield b'x'*(1024*1024)
        yield b'\r\n--boundary--\r\n'
    with TestClient(app) as client:
        response=client.post('/api/videos',content=body(),headers={'Content-Type':'multipart/form-data; boundary=boundary'})
    assert response.status_code==413
    assert not list((tmp_path/'uploads').iterdir())


def test_episode_library_returns_latest_job_and_source_availability(tmp_path,monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from interlude.db import Base,VideoRow,JobRow
    from datetime import datetime,timedelta
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    with factory.begin() as session:
        session.add(VideoRow(id='video',path=str(tmp_path/'missing.mp4'),metadata_json={'duration_sec':1800}))
        session.flush()
        session.add_all([JobRow(id='old',video_id='video',status='FAILED',created_at=datetime(2026,1,1)),
                         JobRow(id='new',video_id='video',status='COMPLETED',created_at=datetime(2026,1,1)+timedelta(days=1))])
    monkeypatch.setattr('interlude.main.sessions',lambda _:factory)
    with TestClient(create_app(Settings(_env_file=None,data_dir=tmp_path))) as client:
        result=client.get('/api/videos').json()['items']
        assert len(result)==1 and result[0]['job']['id']=='new'
        assert result[0]['media_available'] is False
        assert client.get('/api/videos?limit=101').status_code==422
