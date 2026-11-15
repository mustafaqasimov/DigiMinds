import json
import wave
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.voice import VoiceService
from speech.intent import classify, pace

H = {'X-Requested-With': 'DigiMinds'}


@pytest.mark.parametrize(('text', 'expected'), [
    ('Evdə yanğın var, tüstü içəri dolur.', 'fire'),
    ('YANGIN var, kömək edin!', 'fire'),
    ('Bina uçub, dağıntı altında qalmışıq.', 'collapse'),
    ('Evimizin tavanı çöküb.', 'collapse'),
    ('Küçəni su basıb, çıxa bilmirik.', 'flood'),
    ('Anam nəfəs ala bilmir, təcili yardım çağırın.', 'medical'),
    ('Atam huşunu itirib.', 'medical'),
    ('Yanğın yoxdur, amma yaralı var.', 'medical'),
    ('Yanğın yoxdur. Su basmayıb.', None),
    ('Evimizi su basmayıb.', None),
    ('Yaralı adam yoxdur.', None),
    ('Yanğın olmayıb, bina uçmayıb.', None),
    ('Salam, mən evdəyəm.', None),
    ('Bu mətn yanğınsöndürənlər haqqındadır.', None),
    ('', None),
])
def test_azerbaijani_intent(text, expected):
    assert classify(text)['suggested_type'] == expected


def test_multiple_incidents_are_not_silently_prioritized():
    result = classify('Yanğın var və iki nəfər yaralıdır.')
    assert result['ambiguous'] and result['suggested_type'] is None
    assert set(result['candidates']) == {'fire', 'medical'}


def test_pace_is_only_descriptive_and_short_clips_are_unknown():
    assert pace('Evdə yanğın var, tüstü içəri dolur.', 3) == 120
    assert pace('Kömək edin', 3) is None
    assert pace('Bir iki üç dörd beş altı', 1) is None
    assert pace('', 0) is None


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.voice.available', lambda: True)
    application = create_app(str(tmp_path/'voice.db'), demo=True)
    async def fake_transcription(folder, request):
        assert (folder/'input.audio').read_bytes()
        return {'text': 'Evdə yanğın var.', **classify('Evdə yanğın var.'),
                'speech_seconds': 3, 'words_per_minute': None}
    monkeypatch.setattr(application.state.voice_service, 'execute', fake_transcription)
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def guest(client):
    client.cookies.clear()
    return {'Authorization': 'Bearer '+client.post('/api/auth/guest', headers=H).json()['token']}


def staff(client, role='dispatcher'):
    return {'Authorization': 'Bearer '+client.post('/api/auth/login', headers=H, json={
        'username': 'demo-'+role, 'password': 'demo'}).json()['token']}


def audio_headers(headers):
    return {**headers, 'Content-Type': 'audio/webm'}


def test_auth_csrf_role_and_missing_service(client, monkeypatch):
    path = '/api/voice/transcribe'
    assert client.post(path, content=b'x').status_code == 403
    assert client.post(path, headers=H, content=b'x').status_code == 401
    assert client.post(path, headers=audio_headers(staff(client)), content=b'x').status_code == 403
    h = audio_headers(guest(client))
    assert client.post(path, headers={**h, 'Origin': 'https://evil.test'}, content=b'x').status_code == 403
    monkeypatch.setattr('backend.voice.available', lambda: False)
    assert client.get('/api/voice/status').json()['available'] is False
    response = client.post(path, headers=h, content=b'x')
    assert response.status_code == 503 and response.json()['detail'] == 'voice_not_installed'


def test_transcription_does_not_send_sos_and_audio_is_removed(client, app):
    h = audio_headers(guest(client))
    before = app.state.store.db.execute('SELECT count(*) FROM reports').fetchone()[0]
    response = client.post('/api/voice/transcribe', headers=h, content=b'x'*70000)
    assert response.status_code == 200 and response.json()['suggested_type'] == 'fire'
    assert response.headers['cache-control'] == 'no-store'
    assert app.state.store.db.execute('SELECT count(*) FROM reports').fetchone()[0] == before
    assert not app.state.voice_service.active
    assert not list(app.state.voice_service.directory.iterdir())
    assert client.post('/api/voice/classify', headers={**h, 'Content-Type': 'application/json'}, json={'text': 'Anam nəfəs ala bilmir'}).json()['suggested_type'] == 'medical'


def test_audio_declared_chunked_limits_and_failure_cleanup(client, app, monkeypatch):
    h = audio_headers(guest(client));path = '/api/voice/transcribe'
    assert client.post(path, headers={**h, 'Content-Length': str(9*1024*1024)}, content=b'x').status_code == 413
    assert client.post(path, headers={**h, 'Content-Type': 'text/html'}, content=b'x').status_code == 415
    monkeypatch.setattr('backend.voice.MAX_UPLOAD', 8)
    assert client.post(path, headers=h, content=iter([b'12345', b'67890'])).status_code == 413
    assert client.post(path, headers=h, content=b'').status_code == 422
    async def fail(folder, request):
        raise HTTPException(504, 'voice_timeout')
    monkeypatch.setattr(app.state.voice_service, 'execute', fail)
    assert client.post(path, headers=h, content=b'audio').status_code == 504
    assert not app.state.voice_service.active and not list(app.state.voice_service.directory.iterdir())


def test_single_active_request_and_stale_audio_cleanup(tmp_path):
    directory = tmp_path/'voice';stale = directory/('a'*32);stale.mkdir(parents=True)
    (stale/'input.audio').write_bytes(b'private')
    service = VoiceService(tmp_path, directory)
    assert not stale.exists()
    folder = service.reserve()
    with pytest.raises(HTTPException) as exc:service.reserve()
    assert exc.value.status_code == 409
    service.release(folder)
    assert not folder.exists()
    service.close()
    with pytest.raises(HTTPException):service.reserve()


def test_confirmed_voice_notes_are_private_and_retry_cannot_replace_them(client, app):
    h = guest(client)
    note = {'text': 'PRIVATE VOICE TEST. Evdə yanğın var.', 'speech_seconds': 3,
            'words_per_minute': 120, 'suggested_type': 'fire'}
    body = {'event_key': 'voice-report-event', 'type': 'fire', 'lat': 40.3725, 'lng': 49.8385, 'voice_note': note}
    response = client.post('/api/sos', headers=h, json=body)
    assert response.status_code == 201
    incident_id = response.json()['report']['incident_id']
    path = f'/api/incidents/{incident_id}/voice-notes'
    assert client.get(path, headers=h).status_code == 403
    assert client.get(path, headers=staff(client, 'observer')).status_code == 403
    assert client.get(path, headers=staff(client, 'responder')).status_code == 403
    for role in ('observer', 'dispatcher'):
        assert 'PRIVATE VOICE TEST' not in client.get('/api/state', headers=staff(client, role)).text
    assert 'PRIVATE VOICE TEST' not in client.get('/api/map').text
    notes = client.get(path, headers=staff(client)).json()['notes']
    assert len(notes) == 1 and notes[0]['text'] == note['text'] and notes[0]['user_confirmed']
    body['voice_note']['text'] = 'Replacement'
    assert client.post('/api/sos', headers=h, json=body).status_code == 200
    assert client.get(path, headers=staff(client)).json()['notes'][0]['text'] == notes[0]['text']
    assert 'PRIVATE VOICE TEST' not in json.dumps(app.state.store.objects('audit'))


@pytest.mark.parametrize('note', [
    {'text': 'x'*2001}, {'text': ''}, {'text': 'test', 'words_per_minute': -1},
    {'text': 'test', 'speech_seconds': 100}, {'text': 'test', 'suggested_type': 'panic'},
])
def test_voice_note_validation(client, note):
    r = client.post('/api/sos', headers=guest(client), json={
        'event_key': 'invalid-voice-note', 'type': 'fire', 'lat': 40.37, 'lng': 49.8385, 'voice_note': note})
    assert r.status_code == 422


def test_decoder_limits_and_silence_without_model(tmp_path):
    pytest.importorskip('imageio_ffmpeg')
    pytest.importorskip('numpy')
    from speech.transcribe import decode, AudioError
    path = tmp_path/'test.wav'
    path.write_bytes(b'#EXTM3U\nhttps://127.0.0.1/internal')
    with pytest.raises(AudioError, match='invalid_audio'):decode(path)
    def wav(seconds):
        with wave.open(str(path), 'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
            f.writeframes(b'\0\0'*int(seconds*16000))
    wav(1)
    assert len(decode(path)) == 16000
    wav(22)
    with pytest.raises(AudioError, match='too_long'):decode(path)
