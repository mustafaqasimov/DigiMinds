import time
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend import events as ev
from backend.store import Store

H={'X-Requested-With':'DigiMinds'}

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path/'events.db'),demo=True)) as c:yield c

def login(c,role='dispatcher'):
    c.cookies.clear()
    r=c.post('/api/auth/login',headers=H,json={'username':'demo-'+role,'password':'demo'})
    return {'Authorization':'Bearer '+r.json()['token']}

def guest(c):
    c.cookies.clear()
    return {'Authorization':'Bearer '+c.post('/api/auth/guest',headers=H).json()['token']}

def test_presence_timeline():
    e={'start':10000,'end':20000}
    assert ev.presence(e,10000-ev.ARRIVAL_S-1)==(0.,'upcoming')
    assert ev.presence(e,10000-ev.ARRIVAL_S/2)==(.5,'arrival')
    assert ev.presence(e,15000)==(1.,'live')
    assert ev.presence(e,20000+ev.DEPARTURE_S/2)==(.5,'departure')
    assert ev.presence(e,20000+ev.DEPARTURE_S)[1]=='ended'

def test_forecast_conserves_people_and_prefers_nearest_shelter():
    s=Store(':memory:');snap=s.snapshot()
    football=next(e for e in snap['events'] if e['id']=='ev-football')
    assert football['phase']=='live' and football['on_site']==12000
    assert abs(sum(r['incoming'] for r in football['shelters'])-football['seekers'])<=len(football['shelters'])
    assert football['shelters'][0]['id']=='s2'  # North Stadium is the closest open shelter
    assert football['shelters'][0]['incoming']==max(r['incoming'] for r in football['shelters'])
    # Only events on site now add load to the combined shelter forecast.
    stadium=next(x for x in snap['shelters'] if x['id']=='s2')
    assert stadium['event_percent']==football['shelters'][0]['potential_percent']
    assert all(x['status']!='standby' for r in football['shelters'] for x in snap['shelters'] if x['id']==r['id'])

def test_overflow_recommends_nearest_reserve_and_closed_roads_change_forecast():
    s=Store(':memory:')
    festival=next(e for e in s.snapshot()['events'] if e['id']=='ev-festival')
    assert festival['worst']>100 and festival['deficit']>0 and festival['reserve']['id'] in ('s5','s6')
    plan=festival['reserves']
    assert sum(r['absorbs'] for r in plan)+festival['uncovered']==festival['deficit']+festival['unplaced']
    assert festival['reserve']['direction'] in ev.COMPASS and festival['risks'] and festival['description']
    with s.lock,s.db:
        for r in s.objects('road'):
            if 'n1_6' in (r['a'],r['b']):r['blocked']=True;s.put('road',r)
    isolated=next(e for e in s.snapshot()['events'] if e['id']=='ev-festival')
    assert isolated['shelters']==[] and isolated['unplaced']==isolated['seekers'] and isolated['worst'] is None

def test_event_api_permissions_and_validation(client):
    now=time.time()
    body={'name':'Konsert','kind':'concert','node':'n3_5','attendance':8000,'start':now+3600,'end':now+3*3600}
    assert client.post('/api/events',headers=guest(client),json=body).status_code==403
    d=login(client)
    assert client.post('/api/events',headers=d,json={**body,'end':body['start']}).status_code==422
    assert client.post('/api/events',headers=d,json={**body,'node':'x'}).status_code==422
    assert client.post('/api/events',headers=d,json={**body,'start':now-10*3600,'end':now-5*3600}).status_code==422
    created=client.post('/api/events',headers=d,json=body).json()
    names=[e['name'] for e in client.get('/api/state',headers=guest(client)).json()['events']]
    assert 'Konsert' in names  # public planning information
    assert client.delete('/api/events/'+created['id'],headers=login(client,'observer')).status_code==403
    assert client.delete('/api/events/'+created['id'],headers=login(client)).status_code==200

def test_prepare_opens_recommended_reserve(client):
    d=login(client)
    before=next(e for e in client.get('/api/state',headers=d).json()['events'] if e['id']=='ev-festival')
    r=client.post('/api/events/ev-festival/prepare',headers=d)
    assert r.status_code==200
    opened=r.json()['opened']
    snap=client.get('/api/state',headers=d).json()
    assert next(s for s in snap['shelters'] if s['id']==opened)['status']=='open'
    festival=next(e for e in snap['events'] if e['id']=='ev-festival')
    # The opened reserve now receives part of the crowd and relieves the worst shelter.
    assert opened in [x['id'] for x in festival['shelters']] and festival['worst']<before['worst']
    assert client.post('/api/events/ev-festival/prepare',headers=login(client,'observer')).status_code==403
    assert client.post('/api/demo/events',headers=login(client)).status_code==200

def test_bearing_and_risk_level():
    a={'lat':40.37,'lng':49.84}
    assert ev.bearing(a,{'lat':40.38,'lng':49.84})=='N'
    assert ev.bearing(a,{'lat':40.37,'lng':49.85})=='E'
    assert ev.bearing(a,{'lat':40.36,'lng':49.83})=='SW'
    assert ev.risk_level(12000,50)=='high' and ev.risk_level(800,101)=='high'
    assert ev.risk_level(6000,None)=='elevated' and ev.risk_level(800,40)=='moderate'

def test_reserves_cover_shortfall_in_order_and_report_what_is_left():
    s=Store(':memory:')
    with s.lock,s.db:
        s.put('event',{'id':'ev-huge','name':'Mitinq','kind':'rally','node':'n3_5','attendance':60000,'start':s.clock()-60,'end':s.clock()+3600})
    huge=next(e for e in s.snapshot()['events'] if e['id']=='ev-huge')
    assert [r['id'] for r in huge['reserves']]==sorted([r['id'] for r in huge['reserves']],key=lambda i:[r['meters'] for r in huge['reserves'] if r['id']==i][0])
    assert len(huge['reserves'])==2 and huge['uncovered']>0
    assert huge['risks']==list(ev.RISKS['rally'])
