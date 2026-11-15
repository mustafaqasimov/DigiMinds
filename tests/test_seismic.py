import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend import seismic

H = {'X-Requested-With': 'DigiMinds'}


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / 'seismic.db'), demo=True)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def guest(c):
    c.cookies.clear()
    return {'Authorization': 'Bearer ' + c.post('/api/auth/guest', headers=H).json()['token']}


def login(c, role='dispatcher'):
    c.cookies.clear()
    r = c.post('/api/auth/login', headers=H, json={'username': 'demo-' + role, 'password': 'demo'})
    return {'Authorization': 'Bearer ' + r.json()['token']}


def reading(**kw):
    return {'label': 'Phone', 'lat': 40.3725, 'lng': 49.842, 'level': .05, **kw}


SHAKE = reading(level=3, peak=8, ratio=40, triggered=True)


def confirm(client, phones):
    for h in phones:
        r = client.post('/api/sensors/reading', headers=h, json=SHAKE).json()
    return r


def test_one_shaking_phone_is_not_an_earthquake_but_three_are(client):
    phones = [guest(client) for _ in range(4)]
    for i, h in enumerate(phones):
        assert client.post('/api/sensors/reading', headers=h, json=reading(label=f'P{i}')).status_code == 200
    assert len(client.get('/api/state', headers=login(client)).json()['sensors']) == 4
    r = client.post('/api/sensors/reading', headers=phones[0], json=SHAKE).json()
    assert r['seismic'] == [] and r['needed'] == 3
    client.post('/api/sensors/reading', headers=phones[0], json=SHAKE)  # same phone again: still one device
    assert client.get('/api/state', headers=guest(client)).json()['seismic'] == []
    r = confirm(client, phones[1:3])
    assert len(r['seismic']) == 1 and r['seismic'][0]['devices'] == 3
    assert client.get('/api/state', headers=guest(client)).json()['seismic'][0]['devices'] == 3  # public warning
    d = login(client)
    alert = next(a for a in client.get('/api/state', headers=d).json()['alerts'] if a['kind'] == 'seismic')
    assert alert['condition_active'] and alert['evidence']['peak'] == 8
    assert client.post(f"/api/alerts/{alert['id']}/dispatch", headers=d).status_code == 409


def test_confirmed_shake_rings_drill_alarm_in_connected_rooms(client):
    h = guest(client)
    device = str(uuid.uuid4())
    joined = client.post('/api/drills/devices', headers=h,
                         json={'device_id': device, 'room': 'DIGI26', 'label': 'Laptop', 'audio_ready': True})
    assert joined.status_code == 200
    confirm(client, [guest(client) for _ in range(3)])
    client.cookies.clear()
    event = client.get(f'/api/drills/poll?device_id={device}', headers=h).json()['event']
    assert event and event['source'] == 'DigiMinds sensors' and 5 <= event['magnitude'] <= 7.5


def test_citizen_checkin_reaches_dispatch_and_help_becomes_sos(client):
    confirm(client, [guest(client) for _ in range(3)])
    safe, help_, trapped = guest(client), guest(client), guest(client)
    client.cookies.clear()
    warning = client.get('/api/state', headers=safe).json()['seismic'][0]
    assert warning['my_status'] is None
    url = f"/api/seismic/{warning['id']}/checkin"
    assert client.post(url, headers=safe, json={'status': 'safe', 'lat': 40.37, 'lng': 49.84}).json()['sos'] is None
    assert client.post(url, headers=help_, json={'status': 'need_help', 'lat': 40.371, 'lng': 49.841}).json()['sos']
    assert client.post(url, headers=trapped, json={'status': 'trapped', 'lat': 40.372, 'lng': 49.842}).json()['sos']
    assert client.get('/api/state', headers=trapped).json()['seismic'][0]['my_status'] == 'trapped'
    snap = client.get('/api/state', headers=login(client)).json()
    q = snap['seismic'][0]
    assert q['checkins'] == {'safe': 1, 'need_help': 1, 'trapped': 1} and len(q['help_points']) == 2
    assert {i['type'] for i in snap['incidents']} >= {'medical', 'collapse'}
    # Citizens never see other people's check-in locations.
    assert 'help_points' not in client.get('/api/state', headers=guest(client)).json()['seismic'][0]


def test_checkin_validation_and_permissions(client):
    body = {'status': 'safe', 'lat': 40.37, 'lng': 49.84}
    assert client.post('/api/seismic/nope/checkin', headers=guest(client), json=body).status_code == 404
    confirm(client, [guest(client) for _ in range(3)])
    wid = client.get('/api/state', headers=guest(client)).json()['seismic'][0]['id']
    assert client.post(f'/api/seismic/{wid}/checkin', headers=guest(client), json={**body, 'status': 'fine'}).status_code == 422
    assert client.post(f'/api/seismic/{wid}/checkin', headers=login(client, 'observer'), json=body).status_code == 403
    assert client.post('/api/demo/seismic', headers=guest(client), json={'devices': 2}).status_code == 403
    d = login(client)
    assert client.post('/api/demo/seismic', headers=d, json={'devices': 2}).status_code == 200
    assert client.get('/api/state', headers=d).json()['config']['seismic_devices'] == 2
    assert client.post('/api/demo/seismic/reset', headers=d).status_code == 200
    assert client.get('/api/state', headers=d).json()['seismic'] == []


def test_triggers_must_be_close_in_time(app):
    store = app.state.store
    now = [1000.]
    store.clock = lambda: now[0]
    with store.lock, store.db:
        for i, t in enumerate((0, 4, 25)):
            store.db.execute('INSERT INTO seismic VALUES(?,?,?,?,?,?,?,?,?)',
                             (f'r{i}', f'd{i}', 'x', 40.3725, 49.842, 5, 30, 0, 1000 + t))
    now[0] = 1030.
    assert seismic.events(store, now[0], store.config()) == []
    assert len(seismic.events(store, now[0], {**store.config(), 'seismic_devices': 2})) == 1


def test_magnitude_hint_is_clamped():
    assert seismic.magnitude_hint(.5) == 5.0
    assert seismic.magnitude_hint(8) == 7.0
    assert seismic.magnitude_hint(100) == 7.5
