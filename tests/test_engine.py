import concurrent.futures
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.store import Store
from backend.security import PERMISSIONS

H={'X-Requested-With':'DigiMinds'}

@pytest.fixture
def app(tmp_path):return create_app(str(tmp_path/'test.db'),demo=True)

@pytest.fixture
def client(app):
    with TestClient(app) as c:yield c

def guest(c):
    # New cookie-free identities for independent citizens.
    c.cookies.clear()
    r=c.post('/api/auth/guest',headers=H)
    assert r.status_code==200
    return {'Authorization':'Bearer '+r.json()['token']}

def login(c,role='dispatcher'):
    r=c.post('/api/auth/login',headers=H,json={'username':'demo-'+role,'password':'demo'})
    assert r.status_code==200
    return {'Authorization':'Bearer '+r.json()['token']}

def body(**kwargs):return {'event_key':str(uuid.uuid4()),'type':'collapse','lat':40.3725,'lng':49.8385,**kwargs}

def wave(c):
    for i in range(4):assert c.post('/api/sos',headers=guest(c),json=body()).status_code==201

def test_idempotency_and_same_incident_plus_one(client,app):
    h=guest(client);b=body()
    first=client.post('/api/sos',headers=h,json=b)
    assert first.status_code==201
    retry=client.post('/api/sos',headers=h,json=b)
    assert retry.status_code==200 and not retry.json()['created']
    own_again=client.post('/api/sos',headers=h,json=body())
    assert own_again.status_code==200
    other=client.post('/api/sos',headers=guest(client),json=body())
    assert other.json()['report']['incident_id']==first.json()['report']['incident_id']
    snap=app.state.store.snapshot()
    assert len(snap['incidents'])==1 and snap['incidents'][0]['count']==2

def test_idempotency_conflict(client):
    h=guest(client);b=body();client.post('/api/sos',headers=h,json=b)
    assert client.post('/api/sos',headers=h,json={**b,'type':'fire'}).status_code==409

def test_same_location_different_type_separate_incidents(client,app):
    for type in ['fire','medical']:
        client.post('/api/sos',headers=guest(client),json=body(type=type))
    assert len(app.state.store.snapshot()['incidents'])==2

def test_sos_rolling_window_crosses_clock_boundary():
    now=[600.]
    s=Store(':memory:',lambda:now[0])
    for i,at in enumerate([600,660,780]):
        now[0]=at;s.report(str(i),str(uuid.uuid4()),'fire',40.3725,49.8385)
    assert not s.objects('alert')
    now[0]=840;s.report('3',str(uuid.uuid4()),'fire',40.3725,49.8385)
    assert s.objects('alert')[0]['condition_active']
    now[0]=901;s.snapshot()
    assert not s.objects('alert')[0]['condition_active']
    assert len(s.objects('alert'))==1

def test_five_minutes_boundary_inclusive():
    now=[0.];s=Store(':memory:',lambda:now[0])
    s.report('a','event-a','fire',40.3725,49.8385)
    now[0]=300.
    for i in range(3):s.report(str(i),'event-'+str(i),'fire',40.3725,49.8385)
    assert s.objects('alert')[0]['evidence']['count']==4
    now[0]=300.001;s.snapshot()
    assert not s.objects('alert')[0]['condition_active']

def test_radius_across_zone_boundary():
    s=Store(':memory:')
    for i,lng in enumerate([49.8418,49.8419,49.8421,49.8422]):s.report(str(i),'event-'+str(i),'fire',40.3725,lng)
    alerts=s.objects('alert')
    assert len(alerts)==1 and alerts[0]['evidence']['rule']=='radius'

def test_no_transitive_incident_chain():
    s=Store(':memory:')
    for i,lng in enumerate([49.8385,49.8402,49.8419]):s.report(str(i),'event-'+str(i),'fire',40.3725,lng)
    assert len(s.snapshot()['incidents'])==2

def test_safe_preserves_historical_signal_count(client,app):
    wave(client);h=guest(client)
    client.post('/api/sos',headers=h,json=body())
    assert client.post('/api/me/safe',headers=h).status_code==200
    snap=app.state.store.snapshot()
    assert snap['stats']['active_sos']==4 and snap['incidents'][0]['count']==5
    assert app.state.store.objects('alert')[0]['evidence']['count']==5

def test_occupancy_exact_thresholds_and_reroute(client,app):
    h=login(client)
    for count,has_route,red in [(359,True,False),(360,False,False),(380,False,False),(381,False,True)]:
        r=client.patch('/api/shelters/s1/occupancy',headers=h,json={'occupancy':count})
        assert r.status_code==200
        paths=client.get('/api/routes?lat=40.3725&lng=49.842&mode=local',headers=h).json()['routes']
        assert any(p['shelter_id']=='s1' for p in paths)==has_route
        assert any(a['kind']=='capacity' and a['condition_active'] and a['severity']=='critical' for a in app.state.store.objects('alert'))==red

def test_closed_road_never_in_path_and_all_closed_no_route(client,app):
    h=login(client)
    first=client.get('/api/routes?lat=40.37&lng=49.8385&mode=local',headers=h).json()['routes'][0]
    edge=first['edges'][0]
    assert client.patch('/api/roads/'+edge,headers=h,json={'enabled':True}).status_code==200
    paths=client.get('/api/routes?lat=40.37&lng=49.8385&mode=local',headers=h).json()['routes']
    assert paths and all(edge not in p['edges'] for p in paths)
    with app.state.store.lock,app.state.store.db:
        for r in app.state.store.objects('road'):r['blocked']=True;app.state.store.put('road',r)
    result=client.get('/api/routes?lat=40.37&lng=49.8385&mode=local',headers=h).json()
    assert result['no_route'] and result['routes']==[]

def test_out_of_area_rejected(client):
    assert client.get('/api/routes?lat=41&lng=50',headers=guest(client)).status_code==422

def test_provider_failure_falls_back(client,monkeypatch):
    monkeypatch.setenv('ORS_API_KEY','test-key-not-a-secret')
    h=login(client)
    client.post('/api/demo/provider',headers=h,json={'enabled':True})
    r=client.get('/api/routes?lat=40.37&lng=49.8385&mode=auto',headers=h).json()
    assert r['fallback_reason']=='provider_unavailable'
    assert r['routes'][0]['source']=='local_graph'

def test_dispatch_and_open_shelter_are_idempotent(client,app):
    wave(client);h=login(client);a=app.state.store.objects('alert')[0]['id']
    first=client.post('/api/alerts/'+a+'/dispatch',headers=h).json()
    again=client.post('/api/alerts/'+a+'/dispatch',headers=h).json()
    assert first['resource']==again['resource'] and again['duplicate']
    first=client.post('/api/alerts/'+a+'/open_shelter',headers=h).json()
    again=client.post('/api/alerts/'+a+'/open_shelter',headers=h).json()
    assert first['resource']==again['resource'] and again['duplicate']
    assert app.state.store.get('shelter',first['resource'])['status']=='open'

def test_concurrent_dispatch_single_assignment(client,app):
    wave(client);a=app.state.store.objects('alert')[0]['id'];s=app.state.store
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:s.execute(a,'dispatch','operator'),range(12)))
    assert len({r['resource'] for r in results})==1
    assert sum(t['status']=='en_route' for t in s.objects('team'))==1

def test_no_team_does_not_fake_success(client,app):
    wave(client);h=login(client);s=app.state.store
    with s.lock,s.db:
        for team in s.objects('team'):team['status']='on_scene';s.put('team',team)
    a=s.objects('alert')[0]['id']
    assert client.post('/api/alerts/'+a+'/dispatch',headers=h).status_code==409
    assert not s.db.execute('SELECT * FROM actions').fetchall()

def test_citizen_privacy_and_rbac(client):
    h=guest(client)
    client.post('/api/sos',headers=h,json=body())
    public=client.get('/api/state',headers=h).json()
    assert 'teams' not in public and 'reports' not in public and 'alerts' not in public
    assert 'lat' not in public['incidents'][0]
    assert client.patch('/api/shelters/s1/occupancy',headers=h,json={'occupancy':999}).status_code==403
    assert client.post('/api/roles',headers=h,json={'name':'hacker','permissions':['role:write']}).status_code==403
    h=login(client,'observer')
    assert 'teams' in client.get('/api/state',headers=h).json()
    assert client.patch('/api/roads/n0_0--n1_0',headers=h,json={'enabled':True}).status_code==403

def test_custom_role_ui_permissions_and_assignment(client):
    citizen=guest(client);me=client.get('/api/auth/me',headers=citizen).json()
    admin=login(client,'admin')
    assert client.post('/api/roles',headers=admin,json={'name':'coordinator','permissions':['dashboard:read']}).status_code==200
    assert client.patch('/api/users/'+me['id']+'/role',headers=admin,json={'role':'coordinator'}).status_code==200
    data=client.get('/api/state',headers=citizen).json()
    assert data['viewer']['role']=='coordinator' and 'teams' in data
    assert client.post('/api/sos',headers=citizen,json=body()).status_code==403

def test_csrf_and_validation(client):
    assert client.post('/api/auth/guest').status_code==403
    assert client.post('/api/auth/guest',headers={**H,'Origin':'https://attacker.invalid'}).status_code==403
    h=guest(client)
    assert client.post('/api/sos',headers=h,json=body(lat=91)).status_code==422
    assert client.post('/api/sos',headers=h,json=body(role='admin')).status_code==422

def test_rate_limit_retry_after(client):
    h=guest(client)
    responses=[client.post('/api/sos',headers=h,json=body()) for _ in range(10)]
    assert responses[-1].status_code==429 and int(responses[-1].headers['Retry-After'])>0

def test_sensor_rejects_partial_and_stale(client,monkeypatch):
    monkeypatch.setenv('SENSOR_KEY','sensor-test')
    h={**H,'X-Sensor-Key':'sensor-test'}
    assert client.patch('/api/shelters/s1/occupancy',headers=h,json={'occupancy':4,'source':'yolo','coverage':'partial'}).status_code==422
    assert client.patch('/api/shelters/s1/occupancy',headers=h,json={'occupancy':4,'source':'yolo','observed_at':time.time()-500}).status_code==422
    assert client.patch('/api/shelters/s1/occupancy',headers=h,json={'occupancy':4,'source':'yolo'}).status_code==200

def test_websocket_authenticated_and_role_filtered(client):
    h=guest(client)
    with client.websocket_connect('/ws',headers=h) as ws:
        msg=ws.receive_json();assert msg['type']=='state' and 'reports' not in msg['data']
    client.cookies.clear()
    with pytest.raises(Exception):
        with client.websocket_connect('/ws'):pass

def test_persistence_across_restart(tmp_path):
    path=str(tmp_path/'persist.db');s=Store(path);s.report('u','unique-event','fire',40.3725,49.8385);s.db.close()
    s=Store(path);assert s.snapshot()['incidents'][0]['count']==1

def test_guest_identity_survives_operator_switch(client):
    client.post('/api/auth/guest',headers=H);first=client.get('/api/auth/me').json()['id']
    login(client);client.post('/api/auth/logout',headers=H)
    client.post('/api/auth/guest',headers=H)
    assert client.get('/api/auth/me').json()['id']==first
