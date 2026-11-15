import asyncio
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.circuit import CircuitBreaker
from test_engine import guest,login

URL='/api/routes?lat=40.37&lng=49.8385&mode=auto'


def provider_response(app,request):
    route=app.state.store.local_routes(40.37,49.8385)[0]
    return httpx.Response(200,request=request,json={'features':[{'geometry':{'coordinates':route['geometry']},'properties':{'summary':{'distance':route['meters'],'duration':route['minutes']*60}}}]})


def configured(tmp_path,monkeypatch):
    monkeypatch.setenv('ORS_API_KEY','fixture-key')
    return create_app(str(tmp_path/'fallback.db'),demo=True)


def test_503_falls_back_opens_after_three_and_short_circuits(tmp_path,monkeypatch):
    app=configured(tmp_path,monkeypatch);calls=[]
    def fail(req):calls.append(req);return httpx.Response(503,request=req)
    app.state.routing_transport=httpx.MockTransport(fail)
    with TestClient(app) as client:
        h=guest(client)
        for _ in range(3):
            result=client.get(URL,headers=h)
            assert result.status_code==200
            data=result.json()
            assert data['fallback_reason']=='provider_http_503'
            assert data['routes'][0]['source']=='local_graph'
            assert data['message']=='Oflayn/ehtiyat marşrut rejimində işləyir'
        start=time.monotonic();data=client.get(URL,headers=h).json()
        assert time.monotonic()-start<.5
        assert data['routing']['circuit']['state']=='open'
        assert not data['routing']['external_attempted']
        assert data['fallback_reason']=='circuit_open'
        assert len(calls)==3


def test_real_six_second_provider_is_cancelled_before_five_seconds(tmp_path,monkeypatch):
    app=configured(tmp_path,monkeypatch);cancelled=[]
    async def slow(req):
        try:await asyncio.sleep(6)
        except asyncio.CancelledError:cancelled.append(True);raise
        return provider_response(app,req)
    app.state.routing_transport=httpx.MockTransport(slow)
    with TestClient(app) as client:
        h=guest(client);start=time.monotonic();response=client.get(URL,headers=h)
        elapsed=time.monotonic()-start
        assert response.status_code==200
        assert 4.3<=elapsed<5.0
        assert cancelled
        data=response.json()
        assert data['fallback_reason']=='provider_timeout'
        assert data['routes'][0]['source']=='local_graph'
        assert data['routing']['deadline_ms']==4500


@pytest.mark.parametrize('failure',['network','read_timeout','bad_json','nan','bad_shape'])
def test_dependency_failures_do_not_escape_as_500(tmp_path,monkeypatch,failure):
    app=configured(tmp_path,monkeypatch)
    def bad(req):
        if failure=='network':raise httpx.ConnectError('unreachable',request=req)
        if failure=='read_timeout':raise httpx.ReadTimeout('slow stream',request=req)
        if failure=='bad_json':return httpx.Response(200,request=req,content=b'not-json')
        if failure=='nan':return httpx.Response(200,request=req,content=b'{"features":[{"geometry":{"coordinates":[[NaN,40],[49,40]]},"properties":{"summary":{"distance":1,"duration":1}}}]}')
        return httpx.Response(200,request=req,json={'features':None})
    app.state.routing_transport=httpx.MockTransport(bad)
    with TestClient(app) as client:
        response=client.get(URL,headers=guest(client))
        assert response.status_code==200
        assert response.json()['routing']['mode']=='fallback'
        assert response.json()['routes'][0]['source']=='local_graph'


def test_recovery_allows_only_one_probe_and_ignores_late_success():
    now=[0.];breaker=CircuitBreaker(failures=1,clock=lambda:now[0])
    failed,_=breaker.acquire();late,_=breaker.acquire()
    breaker.finish(failed,False,'provider_http_503')
    breaker.finish(late,True)
    assert breaker.snapshot()['state']=='open'
    now[0]=31.
    probe,reason=breaker.acquire();assert probe.probe and reason is None
    for _ in range(20):assert breaker.acquire()[1]=='recovery_probe_in_progress'
    breaker.finish(probe,False,'provider_timeout')
    assert breaker.snapshot()['state']=='open'
    now[0]=62.;probe,_=breaker.acquire();breaker.finish(probe,True)
    assert breaker.snapshot()['state']=='closed'
    assert breaker.snapshot()['in_flight']==0


def test_bulkhead_skips_excess_in_flight_requests():
    breaker=CircuitBreaker(max_in_flight=2)
    one,_=breaker.acquire();two,_=breaker.acquire()
    assert breaker.acquire()==(None,'provider_busy')
    breaker.finish(one,None);breaker.finish(two,None)
    assert breaker.snapshot()['in_flight']==0
    assert breaker.snapshot()['consecutive_failures']==0


def test_twenty_parallel_requests_keep_only_four_provider_calls(tmp_path,monkeypatch):
    app=configured(tmp_path,monkeypatch)
    async def run():
        active=0;peak=0;calls=0
        release=asyncio.Event()
        async def slow_fail(req):
            nonlocal active,peak,calls
            active+=1;calls+=1;peak=max(peak,active)
            try:
                await release.wait()
                return httpx.Response(503,request=req)
            finally:active-=1
        app.state.routing_transport=httpx.MockTransport(slow_fail)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
            identity=await client.post('/api/auth/guest',headers={'X-Requested-With':'DigiMinds'})
            headers={'Authorization':'Bearer '+identity.json()['token']}
            tasks=[asyncio.create_task(client.get(URL,headers=headers)) for _ in range(20)]
            try:
                # Excess requests must finish while the four provider calls are held.
                async with asyncio.timeout(2):
                    while sum(t.done() for t in tasks)<16:await asyncio.sleep(.001)
            finally:release.set()
            responses=await asyncio.gather(*tasks)
            assert all(r.status_code==200 and r.json()['routes'] for r in responses)
            assert sum(r.json()['fallback_reason']=='provider_busy' for r in responses)==16
            assert peak==calls==4
            assert app.state.routing_circuit.snapshot()['state']=='open'
    asyncio.run(run())


def test_local_fallback_rechecks_current_closures_and_occupancy(tmp_path,monkeypatch):
    app=configured(tmp_path,monkeypatch);store=app.state.store
    first=store.local_routes(40.37,49.8385)[0]
    def change_and_fail(req):
        with store.lock,store.db:
            road=store.get('road',first['edges'][0]);road['blocked']=True;store.put('road',road)
            shelter=store.get('shelter',first['shelter_id']);shelter['occupancy']=shelter['capacity'];store.put('shelter',shelter)
            store.audit('test','closure','road')
        return httpx.Response(503,request=req)
    app.state.routing_transport=httpx.MockTransport(change_and_fail)
    with TestClient(app) as client:
        data=client.get(URL,headers=guest(client)).json()
        assert data['fallback_reason']=='state_changed_local_recalculation'
        assert data['routes']
        assert all(r['shelter_id']!=first['shelter_id'] and first['edges'][0] not in r['edges'] for r in data['routes'])


def test_no_route_never_invents_straight_line_and_manual_local_skips_provider(tmp_path,monkeypatch):
    app=configured(tmp_path,monkeypatch)
    def forbidden(req):raise AssertionError('provider must not be called')
    app.state.routing_transport=httpx.MockTransport(forbidden)
    with TestClient(app) as client:
        h=guest(client)
        assert client.get(URL.replace('auto','local'),headers=h).status_code==200
        with app.state.store.lock,app.state.store.db:
            for road in app.state.store.objects('road'):
                road['blocked']=True;app.state.store.put('road',road)
        data=client.get(URL,headers=h).json()
        assert data['no_route'] and data['routes']==[]


def test_demo_failure_modes_work_without_key_and_require_operator(tmp_path,monkeypatch):
    monkeypatch.delenv('ORS_API_KEY',raising=False)
    app=create_app(str(tmp_path/'demo.db'),demo=True)
    with TestClient(app) as client:
        citizen=guest(client)
        assert client.post('/api/demo/routing-provider',headers=citizen,json={'mode':'http_503'}).status_code==403
        operator=login(client)
        assert client.post('/api/demo/routing-provider',headers=operator,json={'mode':'http_503'}).status_code==200
        data=client.get(URL,headers=citizen).json()
        assert data['fallback_reason']=='provider_http_503'
        assert data['routing']['demo_provider']
        client.post('/api/demo/routing-provider',headers=operator,json={'mode':'healthy'})
        data=client.get(URL,headers=citizen).json()
        assert data['routing']['mode']=='online'
        assert data['routes'][0]['source']=='simulated_provider'
