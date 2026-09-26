from fastapi.testclient import TestClient
from interlude.config import Settings
from interlude.main import create_app


def test_protected_workspace_requires_login_and_logout_revokes_cookie(tmp_path):
    app=create_app(Settings(_env_file=None,data_dir=tmp_path,workspace_password="a-strong-test-password",session_secret="s"*40))
    with TestClient(app) as client:
        assert client.get('/api/brands').status_code==401
        assert client.post('/api/session',json={'password':'wrong'}).status_code==401
        assert client.post('/api/session',json={'password':'a-strong-test-password'}).status_code==200
        assert client.get('/api/brands').status_code==200
        assert client.post('/api/session/logout',headers={'X-Interlude-Request':'1'}).status_code==200
        assert client.get('/api/brands').status_code==401


def test_cookie_authenticated_mutations_require_csrf_header(tmp_path):
    app=create_app(Settings(_env_file=None,data_dir=tmp_path,workspace_password="test-password",session_secret="s"*40))
    with TestClient(app) as client:
        client.post('/api/session',json={'password':'test-password'})
        assert client.post('/api/videos',files={'file':('x.mp4',b'x')}).status_code==403


def test_config_exposes_episode_limits_not_secrets(tmp_path):
    with TestClient(create_app(Settings(_env_file=None,data_dir=tmp_path))) as client:
        response=client.get('/api/config')
        assert response.status_code==200
        assert response.json()['max_video_duration_sec']>=3600
        assert 'session_secret' not in response.text
