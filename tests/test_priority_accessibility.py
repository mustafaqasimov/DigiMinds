"""Priority is server-owned and accessibility constraints survive all fallbacks."""
import sqlite3
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.accessibility import accessible
from backend.profiles import SafetyProfile
from backend.store import Store

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path/'priority.db'),demo=True)) as c:
        yield c

def guest(c):
    return {'Authorization':'Bearer '+c.post('/api/auth/guest',headers={'X-Requested-With':'DigiMinds'}).json()['token']}

def login(c,role):
    return {'Authorization':'Bearer '+c.post('/api/auth/login',headers={'X-Requested-With':'DigiMinds'},json={'username':'demo-'+role,'password':'demo','cookie_session':False}).json()['token']}

def report(c,h,**extra):
    return c.post('/api/sos',headers=h,json={'event_key':str(uuid4()),'type':'medical','lat':40.37,'lng':49.8385,**extra})

def routes(c,h,**extra):
    return c.get('/api/routes',headers=h,params={'lat':40.37,'lng':49.8385,**extra}).json()

def test_self_declaration_priority_and_immediate_private_alert(client):
    h=guest(client)
    r=client.put('/api/me/priority',headers=h,json={'enabled':True})
    assert r.status_code==200 and r.json()['role']=='priority_citizen'
    assert set(r.json()['permissions'])=={'sos:create','sos:own','route:read'}
    response=report(client,h);assert response.status_code==201
    assert response.json()['report']['priority']==1
    s=client.get('/api/state',headers=login(client,'dispatcher')).json()
    assert s['incidents'][0]['priority']==1
    assert len([a for a in s['alerts'] if a['priority']==1 and a['condition_active']])==1
    public=client.get('/api/map').json()
    assert 'alerts' not in public and 'reports' not in public
    assert 'priority' not in public['incidents'][0]
    assert client.get('/api/state',headers=h).json()['mine'][0]['priority']==1
    assert client.get('/api/me/profile',headers=h).status_code==200
    assert client.get('/api/users',headers=h).status_code==403


def test_ordinary_sos_no_priority_injection_and_retry_retains_priority(client):
    h=guest(client)
    assert report(client,h,priority=1).status_code==422
    key=str(uuid4());r=report(client,h,event_key=key).json()
    assert r['report']['priority']==2
    client.put('/api/me/priority',headers=h,json={'enabled':True})
    repeat=report(client,h,event_key=key)
    assert repeat.status_code==200 and repeat.json()['report']['priority']==2
    assert len(client.get('/api/state',headers=h).json()['mine'])==1
    assert report(client,h).json()['report']['priority']==1
    assert len(client.get('/api/state',headers=h).json()['mine'])==1

@pytest.mark.parametrize('mobility',['limited','wheelchair','assisted'])
def test_profile_promotes_role_without_sharing_private_profile(client,mobility):
    h=guest(client)
    p=SafetyProfile(mobility=mobility).model_dump()
    assert client.put('/api/me/profile',headers=h,json={'version':0,'profile':p}).status_code==200
    assert client.get('/api/auth/me',headers=h).json()['role']=='priority_citizen'
    assert report(client,h).json()['report']['priority']==1
    assert client.put('/api/me/priority',headers=h,json={'enabled':False}).status_code==409


def test_safe_deactivates_priority_alert_without_rewriting_history(client):
    h=login(client,'priority_citizen');report(client,h)
    assert client.post('/api/me/safe',headers=h).status_code==200
    s=client.get('/api/state',headers=login(client,'dispatcher')).json()
    assert not any(a['condition_active'] for a in s['alerts'] if a['priority']==1)
    assert s['incidents'][0]['priority']==2
    assert client.get('/api/state',headers=h).json()['mine'][0]['priority']==1


def test_verified_routes_bypass_unverified_walking_provider(client,monkeypatch):
    monkeypatch.setenv('ORS_API_KEY','test-only')
    def forbidden(req):raise AssertionError('Walking provider must never be used for priority routes')
    client.app.state.routing_transport=httpx.MockTransport(forbidden)
    h=login(client,'priority_citizen');result=routes(client,h)
    assert result['routes'] and result['routing']['reason']=='accessible_local_only'
    assert not result['routing']['external_attempted']
    store=client.app.state.store
    for r in result['routes']:
        assert r['accessible'] and r['accessibility_scope']=='simulation'
        assert accessible(store.get('shelter',r['shelter_id']))
        assert all(accessible(store.get('road',e)) for e in r['edges'])

@pytest.mark.parametrize('key',['accessibility_verified','step_free','ramp_access','obstacle_free','wheelchair_accessible','medical_vehicle_accessible'])
def test_missing_required_metadata_never_falls_back_to_ordinary_route(client,key):
    h=login(client,'priority_citizen');store=client.app.state.store
    with store.lock,store.db:
        for r in store.objects('road'):
            r.pop(key,None);store.put('road',r)
    result=routes(client,h)
    assert result['routes']==[] and result['no_route']
    assert result['fallback_reason']=='no_accessible_route'
    assert routes(client,guest(client))['routes']


def test_closed_full_inaccessible_shelters_and_unverified_connector(client):
    h=login(client,'priority_citizen');store=client.app.state.store
    assert routes(client,h,lat=40.3701)['routes']==[]
    with store.lock,store.db:
        for s in store.objects('shelter'):
            if accessible(s):s['occupancy']=s['capacity'];store.put('shelter',s)
    assert routes(client,h)['routes']==[]


def test_non_citizen_cannot_self_grant_priority(client):
    assert client.put('/api/me/priority',headers=login(client,'observer'),json={'enabled':True}).status_code==403
    assert client.put('/api/me/priority',headers={'X-Requested-With':'DigiMinds'},json={'enabled':True}).status_code==401


def test_upgrade_preserves_existing_records_and_is_repeatable(tmp_path):
    path=str(tmp_path/'legacy.db');store=Store(path)
    with store.db:
        # Model the old schema and metadata, including a customized unverified road.
        store.db.execute('ALTER TABLE reports DROP COLUMN priority')
        store.db.execute("DELETE FROM objects WHERE kind='role' AND id='priority_citizen'")
        road=store.objects('road')[0];rid=road['id']
        for k in list(road):
            if k.startswith('accessibility_') or k in ('step_free','ramp_access','obstacle_free','wheelchair_accessible','medical_vehicle_accessible'):road.pop(k)
        road['name']='Custom surveyed road';road['blocked']=True;store.put('road',road)
        store.db.execute("INSERT INTO users VALUES('old','old','citizen',NULL,NULL)")
    store.db.close()
    for _ in range(2):
        upgraded=Store(path)
        assert upgraded.get('role','priority_citizen')
        assert 'priority' in [r['name'] for r in upgraded.db.execute('PRAGMA table_info(reports)')]
        assert upgraded.get('road',rid)['blocked']
        assert not accessible(upgraded.get('road',rid))
        assert upgraded.db.execute("SELECT role FROM users WHERE id='old'").fetchone()[0]=='citizen'
        upgraded.db.close()
