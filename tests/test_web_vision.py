import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.vision_jobs import VisionJobs

H = {'X-Requested-With': 'DigiMinds'}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.vision_jobs.available', lambda: True)
    application = create_app(str(tmp_path/'app.db'), demo=True)
    monkeypatch.setattr(application.state.vision_jobs, 'start',
                        lambda job_id: application.state.vision_jobs.jobs[job_id].update(state='queued'))
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def login(client, role='dispatcher'):
    result = client.post('/api/auth/login', headers=H,
                         json={'username': 'demo-'+role, 'password': 'demo', 'cookie_session': False})
    assert result.status_code == 200
    return {'Authorization': 'Bearer '+result.json()['token']}


def test_upload_requires_operator_and_csrf(client):
    assert client.post('/api/vision/jobs?filename=x.mp4', content=b'video').status_code == 403
    assert client.post('/api/vision/jobs?filename=x.mp4', headers=H, content=b'video').status_code == 401
    guest = client.post('/api/auth/guest', headers=H).json()
    assert client.post('/api/vision/jobs?filename=x.mp4', content=b'video',
                       headers={'Authorization': 'Bearer '+guest['token']}).status_code == 403
    h = login(client)
    assert client.post('/api/vision/jobs?filename=x.mp4', headers={**h, 'Origin': 'https://other.test'},
                       content=b'video').status_code == 403


def test_video_stream_bypasses_only_small_json_limit(client, app):
    h = login(client)
    response = client.post('/api/vision/jobs?filename=clip.mp4', headers=h, content=b'x'*70000)
    assert response.status_code == 202
    job = response.json()
    assert 'owner' not in job and job['state'] == 'queued'
    assert (app.state.vision_jobs.directory/job['id']/'input.video').stat().st_size == 70000
    assert client.post('/api/auth/login', headers=H, content=b'x'*70000).status_code == 413
    assert client.post('/api/vision/jobs?filename=next.mp4', headers=h, content=b'x').status_code == 409


def test_declared_and_chunked_size_limits_release_slot(client, app, monkeypatch):
    h = login(client)
    assert client.post('/api/vision/jobs?filename=x.mp4', headers={**h, 'Content-Length': str(101*1024*1024)}, content=b'x').status_code == 413
    monkeypatch.setattr('backend.vision_jobs.MAX_UPLOAD', 8)
    def body():
        yield b'12345'
        yield b'67890'
    assert client.post('/api/vision/jobs?filename=x.mp4', headers=h, content=body()).status_code == 413
    assert app.state.vision_jobs.active is None
    assert not list(app.state.vision_jobs.directory.iterdir())
    assert client.post('/api/vision/jobs?filename=x.mp4', headers=h, content=b'').status_code == 422
    assert app.state.vision_jobs.active is None


@pytest.mark.parametrize('filename', ['../../x.mp4', 'x\\y.mp4', 'x.html', 'x.mp4\x00'])
def test_invalid_upload_names(client, filename):
    response = client.post('/api/vision/jobs', params={'filename': filename},
                           headers=login(client), content=b'x')
    assert response.status_code in {415, 422}


def test_missing_dependencies_are_actionable(client, monkeypatch):
    monkeypatch.setattr('backend.vision_jobs.available', lambda: False)
    assert client.get('/api/vision/status').json()['available'] is False
    result = client.post('/api/vision/jobs?filename=x.mp4', headers=login(client), content=b'x')
    assert result.status_code == 503 and result.json()['detail'] == 'vision_not_installed'


def test_results_owner_scope_range_and_no_cache(client, app):
    h = login(client)
    job_id = client.post('/api/vision/jobs?filename=clip.mp4', headers=h, content=b'video').json()['id']
    folder = app.state.vision_jobs.directory/job_id
    (folder/'result.mp4').write_bytes(b'0123456789')
    (folder/'report.json').write_text('{}')
    other = login(client, 'observer')
    for path in (f'/api/vision/jobs/{job_id}', f'/api/vision/jobs/{job_id}/video'):
        assert client.get(path, headers=other).status_code == 404
    assert client.delete(f'/api/vision/jobs/{job_id}', headers=other).status_code == 404
    assert client.get(f'/api/vision/jobs/{job_id}/video', headers=h).status_code == 404
    app.state.vision_jobs.jobs[job_id].update(state='completed')
    response = client.get(f'/api/vision/jobs/{job_id}/video', headers={**h, 'Range': 'bytes=2-5'})
    assert response.status_code == 206 and response.content == b'2345'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['content-type'] == 'video/mp4'
    download = client.get(f'/api/vision/jobs/{job_id}/report?download=true', headers=h)
    assert 'attachment' in download.headers['content-disposition']
    assert client.get(f'/api/vision/jobs/{job_id}/input.video', headers=h).status_code == 404


def test_cancel_and_terminal_progress_cannot_be_overwritten(client, app):
    h = login(client)
    job_id = client.post('/api/vision/jobs?filename=x.mp4', headers=h, content=b'video').json()['id']
    manager = app.state.vision_jobs
    assert client.delete(f'/api/vision/jobs/{job_id}', headers=h).json()['state'] == 'cancelled'
    (manager.directory/job_id/'status.json').write_text(json.dumps({'state': 'completed'}))
    manager.read_progress(job_id)
    assert manager.snapshot(job_id, manager.jobs[job_id]['owner'])['state'] == 'cancelled'


def test_retention_never_removes_active_job(tmp_path):
    manager = VisionJobs(tmp_path, tmp_path/'jobs')
    job_id, folder = manager.reserve('owner', 'x.mp4')
    manager.jobs[job_id].update(state='completed', created_at=time.time()-4000)
    manager.prune()
    assert folder.is_dir()
    manager.active = None
    manager.prune()
    assert not folder.exists() and job_id not in manager.jobs


def test_video_metadata_limits_without_model_loading():
    pytest.importorskip('cv2')
    from vision.web_job import metadata, VideoError
    import cv2
    class Capture:
        values = {cv2.CAP_PROP_FRAME_WIDTH: 1920, cv2.CAP_PROP_FRAME_HEIGHT: 1080,
                  cv2.CAP_PROP_FPS: 25, cv2.CAP_PROP_FRAME_COUNT: 250}
        def get(self, key): return self.values[key]
        def isOpened(self): return True
    capture = Capture()
    assert metadata(capture) == (1920, 1080, 25, 250)
    capture.values[cv2.CAP_PROP_FRAME_COUNT] = 1600
    with pytest.raises(VideoError, match='duration_limit'): metadata(capture)
    capture.values[cv2.CAP_PROP_FRAME_COUNT] = 250
    capture.values[cv2.CAP_PROP_FRAME_WIDTH] = 3840
    with pytest.raises(VideoError, match='resolution_limit'): metadata(capture)
    capture.values[cv2.CAP_PROP_FPS] = float('nan')
    with pytest.raises(VideoError, match='invalid_video'): metadata(capture)


def test_decoder_rejects_remote_playlists_and_accepts_container_headers(tmp_path):
    from vision.web_job import validate_container, VideoError
    path = tmp_path/'input.video'
    path.write_bytes(b'#EXTM3U\nhttp://127.0.0.1/internal')
    with pytest.raises(VideoError, match='invalid_video'):
        validate_container(path)
    path.write_bytes(b'\x00\x00\x00\x20ftypisom\x00\x00\x00\x00')
    validate_container(path)
