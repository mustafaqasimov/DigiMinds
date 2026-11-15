"""Ownership, consent lifecycle and disclosure boundaries for safety profiles."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.profiles import SafetyProfile
from backend.store import Store

H = {'X-Requested-With': 'DigiMinds'}

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path/'profiles.db'), demo=True)) as c:
        yield c

def guest(c):
    c.cookies.clear()
    return {'Authorization': 'Bearer '+c.post('/api/auth/guest', headers=H).json()['token']}

def staff(c, role='dispatcher'):
    result = c.post('/api/auth/login', headers=H, json={'username': 'demo-'+role, 'password': 'demo'})
    return {'Authorization': 'Bearer '+result.json()['token']}

def save(c, h, version=0, **changes):
    profile = {**SafetyProfile().model_dump(), 'full_name': 'PRIVATE-TEST-PERSON', 'age': 68,
               'mobility': 'wheelchair', 'accessibility': ['hearing'], 'transport': 'needed', **changes}
    return c.put('/api/me/profile', headers=h, json={'version': version, 'profile': profile})

def sos(c, h, key='profile-test-event'):
    result = c.post('/api/sos', headers=h, json={'event_key': key, 'type': 'collapse', 'lat': 40.3725, 'lng': 49.8385})
    assert result.status_code == 201
    return result.json()['report']['incident_id']

def test_profile_ownership_and_persistence(client):
    a = guest(client)
    assert save(client, a).status_code == 200
    assert client.get('/api/me/profile', headers=a).json()['profile']['age'] == 68
    b = guest(client)
    assert client.get('/api/me/profile', headers=b).json()['profile']['full_name'] == ''
    assert client.get('/api/me/profile', headers=a).json()['profile']['full_name'] == 'PRIVATE-TEST-PERSON'
    record = client.get('/api/me/profile', headers=a).json()
    assert record['plan']['needs'] == ['step_free', 'hearing', 'transport']
    assert record['plan']['route_accessibility'] == 'unverified'
    db = client.app.state.store
    other = Store(db.db.execute('PRAGMA database_list').fetchone()[2])
    assert other.objects('profile')[0]['profile']['age'] == 68
    other.db.close()

def test_auth_and_citizen_only(client):
    client.cookies.clear()
    assert client.get('/api/me/profile').status_code == 401
    for role in ('dispatcher','observer','admin','responder'):
        h = staff(client, role)
        assert client.get('/api/me/profile', headers=h).status_code == 403
        assert save(client, h).status_code == 403
        assert client.delete('/api/me/profile?version=0', headers=h).status_code == 403

@pytest.mark.parametrize('change', [
    {'age': -1}, {'age': 121}, {'age': 32.5}, {'age': True},
    {'mobility': 'flying'}, {'accessibility': ['invented']}, {'phone': 'abc'},
    {'phone': '123'}, {'medical_notes': 'a'*501}, {'dependents': 21},
    {'contact_name': 'Missing phone'}, {'contact_phone': '+994501234567'}, {'owner_id': 'someone-else'}
])
def test_validation(client, change):
    assert save(client, guest(client), **change).status_code == 422

def test_conflict_and_delete_tombstone(client):
    h = guest(client)
    assert save(client,h).status_code == 200
    assert save(client,h).status_code == 409
    assert client.delete('/api/me/profile?version=0',headers=h).status_code == 409
    assert client.delete('/api/me/profile?version=1',headers=h).status_code == 200
    r = client.get('/api/me/profile',headers=h).json()
    assert r['version'] == 2 and r['profile']['full_name'] == '' and r['updated_at'] is None
    assert save(client,h,version=1).status_code == 409
    assert save(client,h,version=2).status_code == 200

def test_sharing_opt_in_revoke_safe_delete(client):
    h = guest(client);save(client,h)
    incident = sos(client,h)
    d = staff(client)
    url = f'/api/incidents/{incident}/assistance'
    assert client.get(url,headers=d).json()['people'] == []
    save(client,h,version=1,share_on_sos=True)
    rows = client.get(url,headers=d).json()['people']
    assert len(rows) == 1 and rows[0]['profile']['full_name'] == 'PRIVATE-TEST-PERSON'
    assert 'district' not in rows[0]['profile'] and 'user_id' not in rows[0]
    save(client,h,version=2,share_on_sos=False)
    assert client.get(url,headers=d).json()['people'] == []
    save(client,h,version=3,share_on_sos=True)
    assert client.post('/api/me/safe',headers=h).status_code == 200
    assert client.get(url,headers=d).json()['people'] == []
    assert client.delete('/api/me/profile?version=4',headers=h).status_code == 200
    assert client.get(url,headers=d).json()['people'] == []

def test_observer_other_citizen_and_unassigned_responder_cannot_read(client):
    h = guest(client);save(client,h,share_on_sos=True);incident=sos(client,h)
    url=f'/api/incidents/{incident}/assistance'
    for token in (guest(client),staff(client,'observer'),staff(client,'responder')):
        assert client.get(url,headers=token).status_code == 403
    r=staff(client,'responder');db=client.app.state.store
    with db.lock,db.db:
        t=db.get('team','t1');t.update(incident_id=incident,status='en_route');db.put('team',t)
    assert len(client.get(url,headers=r).json()['people']) == 1
    with db.lock,db.db:
        t['status']='available';db.put('team',t)
    assert client.get(url,headers=r).status_code == 403

def test_never_leaks_in_state_websocket_or_audit(client):
    h=guest(client);save(client,h,share_on_sos=True,medical_notes='PRIVATE-MEDICAL-NOTE')
    incident=sos(client,h)
    for role in ('observer','dispatcher','admin','responder'):
        token=staff(client,role)
        assert 'PRIVATE-' not in client.get('/api/state',headers=token).text
        with client.websocket_connect('/ws',headers=token) as ws:
            assert 'PRIVATE-' not in json.dumps(ws.receive_json())
    assert 'PRIVATE-' not in client.get('/api/map').text
    d=staff(client)
    client.get(f'/api/incidents/{incident}/assistance',headers=d)
    assert 'profile.accessed' in client.get('/api/me/profile',headers=h).text
    admin=staff(client,'admin')
    assert 'PRIVATE-' not in client.get('/api/audit',headers=admin).text
    assert client.get('/api/me/profile',headers=h).headers['cache-control'] == 'no-store'

def test_csrf_protection_and_active_deletion(client):
    h=guest(client);save(client,h,share_on_sos=True);incident=sos(client,h)
    # Cookie auth, no required CSRF header.
    assert client.put('/api/me/profile',json={'version':1,'profile':SafetyProfile().model_dump()}).status_code == 403
    assert client.delete('/api/me/profile?version=1',headers=h).status_code == 200
    assert client.get(f'/api/incidents/{incident}/assistance',headers=staff(client)).json()['people'] == []
