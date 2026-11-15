"""Requirements audit: measured occupancy, atomic response and repeat episodes."""
import concurrent.futures
import pytest
from backend.store import Store
from backend.security import PERMISSIONS
from test_engine import app, client, guest, login, wave


def set_occupancy(store,count):
    with store.lock,store.db:
        s=store.get('shelter','s1');s['occupancy']=count;store.put('shelter',s);store.evaluate()
    return [a for a in store.objects('alert') if a['kind']=='capacity' and a['condition_active']]


def test_thresholds_preparation_escalation_and_new_episode():
    store=Store(':memory:')
    assert set_occupancy(store,359)==[]
    alert=set_occupancy(store,360)[0]
    assert alert['severity']=='warning'
    assert all(r['shelter_id']!='s1' for r in store.local_routes(40.3725,49.842))
    assert set_occupancy(store,380)[0]['severity']=='warning'
    red=set_occupancy(store,381)[0]
    assert red['id']==alert['id'] and red['severity']=='critical'
    assert set_occupancy(store,360)[0]['severity']=='warning'
    assert set_occupancy(store,359)==[]
    again=set_occupancy(store,360)[0]
    assert again['id']!=alert['id']
    assert not store.get('alert',alert['id'])['condition_active']


def test_90_percent_open_reserve_is_reachable_idempotent_and_routable(client,app):
    h=login(client)
    assert client.patch('/api/shelters/s1/occupancy',headers=h,json={'occupancy':360}).status_code==200
    state=client.get('/api/state',headers=h).json()
    a=next(a for a in state['alerts'] if a['kind']=='capacity')
    assert a['severity']=='warning' and a['actions']=={}
    option=a['options']['open_shelter']
    assert option and option['meters']>=0
    assert client.post('/api/alerts/'+a['id']+'/dispatch',headers=h).status_code==409
    url='/api/alerts/'+a['id']+'/open_shelter'
    result=client.post(url,headers=h).json()
    assert result['resource']==option['id'] and not result['duplicate']
    assert client.post(url,headers=h).json()['duplicate']
    routes=client.get('/api/routes?lat=40.3725&lng=49.842&mode=local',headers=h).json()['routes']
    assert any(r['shelter_id']==option['id'] for r in routes)
    assert all(r['shelter_id']!='s1' for r in routes)
    a=next(item for item in client.get('/api/state',headers=h).json()['alerts'] if item['id']==a['id'])
    assert a['actions']['open_shelter']==option['id']
    public=client.get('/api/state',headers=guest(client)).json()
    assert 'alerts' not in public and 'teams' not in public


def test_one_click_response_concurrent_and_repeat():
    store=Store(':memory:');alert=set_occupancy(store,384)[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:store.execute(alert['id'],'respond','operator'),range(12)))
    assert sum(not r['duplicate'] for r in results)==1
    assert len({r['resources']['dispatch'] for r in results})==1
    assert len({r['resources']['open_shelter'] for r in results})==1
    assert sum(t['status']=='en_route' for t in store.objects('team'))==1
    assert store.db.execute('SELECT count(*) FROM actions').fetchone()[0]==2


def test_critical_response_api_and_rbac(client,app):
    wave(client)
    a=next(a for a in app.state.store.objects('alert') if a['kind']=='sos')
    url='/api/alerts/'+a['id']+'/respond'
    assert client.post(url,headers=guest(client)).status_code==403
    assert client.post(url,headers=login(client,'observer')).status_code==403
    h=login(client)
    result=client.post(url,headers=h)
    assert result.status_code==200
    assert set(result.json()['resources'])=={'dispatch','open_shelter'}
    assert client.post(url,headers=h).json()['duplicate']


@pytest.mark.parametrize('missing,error',[('team','no_available_team'),('shelter','no_reserve_shelter')])
def test_combined_response_never_partially_executes(missing,error):
    store=Store(':memory:');a=set_occupancy(store,384)[0]
    with store.lock,store.db:
        for r in store.objects(missing):
            if missing=='shelter' and r['status']!='standby':continue
            r['status']='on_scene' if missing=='team' else 'closed';store.put(missing,r)
    teams=store.objects('team');shelters=store.objects('shelter')
    with pytest.raises(ValueError,match=error):store.execute(a['id'],'respond','operator')
    assert store.objects('team')==teams and store.objects('shelter')==shelters
    assert not store.db.execute('SELECT * FROM actions').fetchall()


def test_escalation_reuses_reserve_opened_at_90_percent():
    store=Store(':memory:');a=set_occupancy(store,360)[0]
    first=store.execute(a['id'],'open_shelter','operator')
    set_occupancy(store,384)
    response=store.execute(a['id'],'respond','operator')
    assert response['resources']['open_shelter']==first['resource']
    assert sum(s['status']=='standby' for s in store.objects('shelter'))==1
    assert store.db.execute('SELECT count(*) FROM actions').fetchone()[0]==2


def test_expired_alert_rejects_new_action_and_rearms():
    store=Store(':memory:');a=set_occupancy(store,360)[0]
    store.execute(a['id'],'open_shelter','operator')
    set_occupancy(store,200)
    assert store.execute(a['id'],'open_shelter','operator')['duplicate']
    with pytest.raises(ValueError,match='alert_unavailable'):store.execute(a['id'],'dispatch','operator')
    new=set_occupancy(store,360)[0]
    assert not store.execute(new['id'],'open_shelter','operator')['duplicate']


def test_full_or_disconnected_standby_cannot_be_opened():
    store=Store(':memory:');a=set_occupancy(store,360)[0]
    with store.lock,store.db:
        for s in store.objects('shelter'):
            if s['status']=='standby':
                s['occupancy']=s['capacity'];store.put('shelter',s)
    assert store.response_options(a)['open_shelter'] is None
    with pytest.raises(ValueError,match='no_reserve_shelter'):store.execute(a['id'],'open_shelter','operator')
    with store.lock,store.db:
        for s in store.objects('shelter'):
            if s['status']=='standby':s['occupancy']=0;store.put('shelter',s)
        for road in store.objects('road'):road['blocked']=True;store.put('road',road)
    with pytest.raises(ValueError,match='no_reserve_shelter'):store.execute(a['id'],'open_shelter','operator')


def test_sos_window_rearms_with_new_action_identity():
    now=[1000.];store=Store(':memory:',lambda:now[0])
    for i in range(4):store.report(str(i),'wave1-'+str(i),'fire',40.3725,49.8385)
    old=store.objects('alert')[0];store.execute(old['id'],'dispatch','operator')
    now[0]+=301;store.snapshot()
    for i in range(4):store.report('new'+str(i),'wave2-'+str(i),'fire',40.3725,49.8385)
    active=[a for a in store.objects('alert') if a['condition_active']]
    assert len(active)==1 and active[0]['id']!=old['id']
    assert not store.execute(active[0]['id'],'dispatch','operator')['duplicate']


def test_reserve_opening_keeps_measurement_timestamp():
    now=[1000.];store=Store(':memory:',lambda:now[0]);a=set_occupancy(store,360)[0]
    now[0]+=400
    result=store.execute(a['id'],'open_shelter','operator')
    s=next(s for s in store.snapshot()['shelters'] if s['id']==result['resource'])
    assert s['stale'] and s['observed_at']==1000
