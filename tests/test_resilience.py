import asyncio
import hashlib
import time
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.store import Store
from test_engine import H, guest, body, login


def test_chunked_body_limit_without_content_length(tmp_path):
    with TestClient(create_app(str(tmp_path/'body.db'), demo=True)) as client:
        response = client.post('/api/auth/guest', headers=H,
                               content=iter([b' ' * 40000, b' ' * 40000]))
        assert response.status_code == 413


def test_alert_evidence_updates_revision_without_new_sos():
    now = [1000.]
    store = Store(':memory:', lambda: now[0])
    for i in range(5):
        now[0] = 1000.+i*10
        store.report(str(i), str(uuid.uuid4()), 'fire', 40.37, 49.8385)
    revision = store.revision
    now[0] = 1301.
    snapshot = store.snapshot()
    assert snapshot['revision'] > revision
    assert store.objects('alert')[0]['evidence']['count'] == 4


def test_responder_only_sees_assigned_incident(tmp_path):
    with TestClient(create_app(str(tmp_path/'privacy.db'), demo=True)) as client:
        client.post('/api/sos', headers=guest(client), json=body())
        response = client.get('/api/state', headers=login(client, 'responder')).json()
        assert response['incidents'] == []
        assert len(response['teams']) == 1
        assert 'reports' not in response


def test_logout_revokes_bearer_even_with_other_identity_cookie(tmp_path):
    with TestClient(create_app(str(tmp_path/'logout.db'), demo=True)) as client:
        citizen=guest(client)
        dispatcher=login(client)
        assert client.post('/api/auth/logout',headers=citizen).status_code==200
        assert client.get('/api/auth/me',headers=citizen).status_code==401
        assert client.get('/api/auth/me',headers=dispatcher).status_code==200


def test_zone_dispatch_targets_largest_incident():
    store=Store(':memory:')
    first,_=store.report('first','first-event','collapse',40.37,49.8385)
    for i in range(4):
        latest,_=store.report(str(i),'other-'+str(i),'collapse',40.38,49.8385)
    alert=store.objects('alert')[0]
    assert alert['target']==latest['incident_id']
    assert alert['target']!=first['incident_id']


def test_mass_unique_sos_then_replay(tmp_path):
    """200 distinct identities through ASGI, not 200 retries of one message.

    Fixture provisioning bypasses guest-signup IP quota, never SOS quotas.
    Separate live HTTP script measures sockets/latencies and retry bursts.
    """
    app = create_app(str(tmp_path/'burst.db'), demo=True)
    store = app.state.store
    tokens = []
    with store.lock, store.db:
        for i in range(200):
            token = uuid.uuid4().hex
            tokens.append(token)
            store.db.execute('INSERT INTO users VALUES(?,?,?,NULL,NULL)', (str(i), 'load-'+str(i), 'citizen'))
            store.db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), str(i), time.time()+3600))

    async def burst():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            semaphore = asyncio.Semaphore(40)
            events = [body() for _ in tokens]
            async def send(i):
                async with semaphore:
                    return await client.post('/api/sos', headers={'Authorization': 'Bearer '+tokens[i]}, json=events[i])
            first = await asyncio.gather(*(send(i) for i in range(200)))
            second = await asyncio.gather(*(send(i) for i in range(200)))
            assert all(r.status_code == 201 for r in first)
            assert all(r.status_code == 200 for r in second)
    asyncio.run(burst())
    snapshot = store.snapshot()
    assert len(snapshot['incidents']) == 1
    assert snapshot['incidents'][0]['count'] == 200
    assert store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0] == 200
    assert any(a['condition_active'] and a['evidence']['count'] == 200 for a in store.objects('alert'))


def test_external_route_invalidated_if_capacity_changes_while_waiting(tmp_path, monkeypatch):
    monkeypatch.setenv('ORS_API_KEY', 'fixture-key')
    app = create_app(str(tmp_path/'race.db'), demo=True)
    store = app.state.store
    original = store.local_routes(40.37, 49.8385)[0]
    class Provider:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            with store.lock, store.db:
                shelter = store.get('shelter', original['shelter_id'])
                shelter['occupancy'] = shelter['capacity']
                store.put('shelter', shelter)
                store.audit('sensor', 'occupancy.updated', shelter['id'])
            return httpx.Response(200, request=httpx.Request('POST', 'https://provider.invalid'),
                                  json={'features': [{'geometry': {'coordinates': original['geometry']},
                                       'properties': {'summary': {'distance': 200, 'duration': 100}}}]})
    with TestClient(app) as client:
        h = guest(client)
        monkeypatch.setattr('backend.app.httpx.AsyncClient', lambda **kwargs: Provider())
        response = client.get('/api/routes?lat=40.37&lng=49.8385&mode=auto', headers=h).json()
        assert response['fallback_reason'] == 'state_changed_local_recalculation'
        assert all(r['shelter_id'] != original['shelter_id'] for r in response['routes'])
