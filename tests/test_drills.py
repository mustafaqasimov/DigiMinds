from uuid import uuid4

from fastapi.testclient import TestClient
from backend.app import create_app
from test_engine import app, client, guest, login, H


def join(client, auth, room='DIGI26'):
    device = {'device_id': str(uuid4()), 'room': room,
              'label': 'Phone', 'audio_ready': True}
    assert client.post('/api/drills/devices', headers=auth, json=device).status_code == 200
    return device['device_id']


def publish(client, auth, **values):
    body = {'event_key': str(uuid4()), 'room': 'DIGI26', 'location': 'Bakı',
            'magnitude': 5.8, 'duration': 30, **values}
    return client.post('/api/drills/earthquake', headers=auth, json=body)


def test_drill_authorization_and_device_ownership(client):
    citizen = guest(client)
    device = join(client, citizen)
    stranger = guest(client)
    assert publish(client, citizen).status_code == 403
    assert client.get('/api/drills/rooms/DIGI26', headers=citizen).status_code == 403
    assert client.get('/api/drills/poll', params={'device_id': device}, headers=stranger).status_code == 404
    assert client.post('/api/drills/devices', headers=stranger, json={
        'device_id': device, 'room': 'DIGI26', 'label': 'stolen'}).status_code == 404
    assert client.delete('/api/drills/devices/'+device, headers=stranger).status_code == 404


def test_message_fanout_room_isolation_and_receipts(client, app):
    first, second, outsider = guest(client), guest(client), guest(client)
    one, two, other = join(client, first), join(client, second), join(client, outsider, 'OTHER')
    dispatcher = login(client)
    event = publish(client, dispatcher).json()
    for auth, device in ((first, one), (second, two)):
        packet = client.get('/api/drills/poll', headers=auth, params={'device_id': device}).json()
        assert packet['event']['id'] == event['id']
        assert packet['event']['simulated'] is True
        assert packet['connected'] == 2
        assert 'owner' not in packet['event']
        for state in ('received', 'audio_started'):
            assert client.post('/api/drills/earthquake/'+event['id']+'/receipts', headers=auth,
                               json={'device_id': device, 'status': state}).status_code == 200
    assert client.get('/api/drills/poll', headers=outsider, params={'device_id': other}).json()['event'] is None
    assert client.post('/api/drills/earthquake/'+event['id']+'/receipts', headers=outsider,
                       json={'device_id': other, 'status': 'received'}).status_code == 404
    overview = client.get('/api/drills/rooms/DIGI26', headers=dispatcher).json()
    assert len(overview['devices']) == 2
    assert all('audio_started' in d['receipt'] for d in overview['devices'])
    assert app.state.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0] == 0


def test_retry_cancel_expiry_and_liveness(client, app):
    now = [1000.]
    app.state.drills.clock = lambda: now[0]
    citizen = guest(client)
    device = join(client, citizen)
    dispatcher = login(client)
    key = str(uuid4())
    original = publish(client, dispatcher, event_key=key).json()
    assert publish(client, dispatcher, event_key=key).json()['id'] == original['id']
    assert publish(client, dispatcher, event_key=key, magnitude=6.1).status_code == 409
    assert publish(client, dispatcher).status_code == 409
    assert client.post('/api/drills/earthquake/'+original['id']+'/cancel', headers=citizen).status_code == 403
    assert client.post('/api/drills/earthquake/'+original['id']+'/cancel', headers=dispatcher).status_code == 200
    assert client.get('/api/drills/poll', headers=citizen, params={'device_id': device}).json()['event'] is None
    assert publish(client, dispatcher, event_key=key).json()['cancelled'] is True
    event = publish(client, dispatcher).json()
    now[0] += 31
    assert client.get('/api/drills/poll', headers=citizen, params={'device_id': device}).json()['event'] is None
    assert client.post('/api/drills/earthquake/'+event['id']+'/receipts', headers=citizen,
                       json={'device_id': device, 'status': 'audio_started'}).status_code == 409
    now[0] += 16
    assert client.get('/api/drills/rooms/DIGI26', headers=dispatcher).json()['devices'][0]['online'] is False
    now[0] += 121
    assert client.get('/api/drills/rooms/DIGI26', headers=dispatcher).json()['devices'] == []


def test_websocket_authenticated_delivery_and_cancellation(client):
    citizen = guest(client)
    device = join(client, citizen)
    dispatcher = login(client)
    with client.websocket_connect('/ws/drills?device_id='+device, headers=citizen) as ws:
        assert ws.receive_json()['event'] is None
        event = publish(client, dispatcher).json()
        assert ws.receive_json()['event']['id'] == event['id']
        assert client.post('/api/drills/earthquake/'+event['id']+'/cancel', headers=dispatcher).status_code == 200
        assert ws.receive_json()['event'] is None


def test_drills_disabled_outside_demo(tmp_path, monkeypatch):
    monkeypatch.setenv('ADMIN_PASSWORD', 'a-long-enough-test-password')
    with TestClient(create_app(str(tmp_path/'production.db'), demo=False)) as client:
        assert client.post('/api/drills/earthquake', headers=H, json={
            'event_key': str(uuid4()), 'room': 'DIGI26', 'location': 'Baku',
            'magnitude': 5.8}).status_code == 404
        assert client.get('/api/drills/rooms/DIGI26').status_code == 404


def test_limits_csrf_and_invalid_payloads(client):
    dispatcher = login(client)
    assert publish(client, dispatcher, duration=3600).status_code == 422
    assert publish(client, dispatcher, room='../../other').status_code == 422
    assert publish(client, dispatcher, source='Google').status_code == 422
    assert client.post('/api/drills/earthquake', json={}).status_code == 403
